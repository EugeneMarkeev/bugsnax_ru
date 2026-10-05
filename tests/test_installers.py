import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def sha(data):return hashlib.sha256(data).hexdigest()

def linux_path(path):
    path=Path(path).resolve()
    return '/mnt/'+path.drive[0].lower()+str(path)[2:].replace('\\','/')

class InstallerContract:
    def setUp(self):
        (ROOT/'test-results').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='voice test ',dir=ROOT/'test-results')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.package=self.base/'release folder';(self.package/'payload').mkdir(parents=True)
        self.game=self.base/'game folder'
        self.audio=self.game/'Content/Audio/Build/Desktop';self.audio.mkdir(parents=True)
        self.originals={'GameAudio_Filbo.bank':b'original filbo','GameAudio_Wambus.bank':b'original wambus'}
        rows=['name\toriginal_sha256\tpatched_sha256\tbytes']
        for name,data in self.originals.items():
            patched=b'russian '+data
            (self.audio/name).write_bytes(data);(self.package/'payload'/name).write_bytes(patched)
            rows.append(f'{name}\t{sha(data)}\t{sha(patched)}\t{len(patched)}')
        (self.package/'manifest.tsv').write_text('\n'.join(rows)+'\n',encoding='utf-8')

    def assert_original(self):
        for name,data in self.originals.items():self.assertEqual((self.audio/name).read_bytes(),data)

    def test_roundtrip_and_repeat(self):
        self.assertEqual(self.run_action('check').returncode,0)
        self.assert_original()
        for _ in range(2):self.assertEqual(self.run_action('install').returncode,0)
        for name,data in self.originals.items():
            self.assertEqual((self.audio/name).read_bytes(),b'russian '+data)
            self.assertEqual((self.audio/'.bugsnax-russian-voice/backup'/name).read_bytes(),data)
        for _ in range(2):self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_corrupt_payload_does_not_touch_game(self):
        (self.package/'payload/GameAudio_Wambus.bank').write_bytes(b'bad download')
        self.assertNotEqual(self.run_action('install').returncode,0)
        self.assert_original()

    def prepare_previous_pack(self,backup=True):
        rows=['name\toriginal_sha256\tpatched_sha256\tbytes']
        for name,data in self.originals.items():
            previous=b'old broken pack '+data
            (self.audio/name).write_bytes(previous)
            rows.append(f'{name}\t{sha(data)}\t{sha(previous)}\t{len(previous)}')
            if backup:
                saved=self.audio/'.bugsnax-russian-voice/backup'/name
                saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(data)
        (self.package/'previous-manifest.tsv').write_bytes(('\n'.join(rows)+'\n').encode())

    def test_upgrade_preserves_original_backup(self):
        self.prepare_previous_pack()
        result=self.run_action('install')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        for name,data in self.originals.items():
            self.assertEqual((self.audio/name).read_bytes(),b'russian '+data)
            self.assertEqual((self.audio/'.bugsnax-russian-voice/backup'/name).read_bytes(),data)
        self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_previous_pack_without_backup_is_rejected(self):
        self.prepare_previous_pack(backup=False)
        self.assertNotEqual(self.run_action('install').returncode,0)
        for name,data in self.originals.items():self.assertEqual((self.audio/name).read_bytes(),b'old broken pack '+data)

    def test_uninstall_previous_pack(self):
        self.prepare_previous_pack()
        self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_unknown_game_version_does_not_touch_other_banks(self):
        (self.audio/'GameAudio_Wambus.bank').write_bytes(b'new game version')
        self.assertNotEqual(self.run_action('install').returncode,0)
        self.assertEqual((self.audio/'GameAudio_Filbo.bank').read_bytes(),self.originals['GameAudio_Filbo.bank'])

    def test_missing_payload(self):
        shutil.rmtree(self.package/'payload')
        self.assertNotEqual(self.run_action('install').returncode,0)
        self.assert_original()

    def test_empty_manifest(self):
        (self.package/'manifest.tsv').write_text('name\toriginal_sha256\tpatched_sha256\tbytes\n')
        self.assertNotEqual(self.run_action('install').returncode,0)
        self.assert_original()

    def make_sound_archive(self,corrupt=False):
        archive=self.package/'Bugsnax-Sound-Pack-v0.1.0.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for path in (self.package/'payload').glob('*.bank'):z.write(path,'payload/'+path.name)
        checksum=sha(archive.read_bytes()) if not corrupt else '0'*64
        (self.package/'sound-pack.tsv').write_bytes(('filename\turl\tsha256\n'+archive.name+'\thttps://github.com/EugeneMarkeev/bugsnax_ru/releases/download/v0.1.1/'+archive.name+'\t'+checksum+'\n').encode())
        shutil.rmtree(self.package/'payload')
        return archive

    def test_offline_sound_pack_install(self):
        self.make_sound_archive()
        self.assertEqual(self.run_action('install').returncode,0)
        for name,data in self.originals.items():self.assertEqual((self.audio/name).read_bytes(),b'russian '+data)
        self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_bad_sound_pack_checksum(self):
        self.make_sound_archive(corrupt=True)
        self.assertNotEqual(self.run_action('install').returncode,0)
        self.assert_original()

    def test_uninstall_without_audio_files(self):
        self.assertEqual(self.run_action('install').returncode,0)
        shutil.rmtree(self.package/'payload')
        self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_download_resume_path(self):
        archive=self.make_sound_archive()
        server=self.base/'server.zip'
        shutil.move(archive,server)
        Path(str(archive)+'.partial').write_bytes(server.read_bytes()[:20])
        result=self.run_download(server)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(archive.read_bytes(),server.read_bytes())
        self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_corrupt_backup_blocks_uninstall(self):
        self.assertEqual(self.run_action('install').returncode,0)
        (self.audio/'.bugsnax-russian-voice/backup/GameAudio_Wambus.bank').write_bytes(b'damaged backup')
        self.assertNotEqual(self.run_action('uninstall').returncode,0)
        for name,data in self.originals.items():self.assertEqual((self.audio/name).read_bytes(),b'russian '+data)

    def test_manifest_path_traversal_rejected(self):
        path=self.package/'manifest.tsv'
        path.write_text(path.read_text().replace('GameAudio_Wambus.bank','../outside.bank'))
        self.assertNotEqual(self.run_action('install').returncode,0)
        self.assert_original()

    def test_lock_blocks_concurrent_installer(self):
        (self.audio/'.bugsnax-russian-voice/lock').mkdir(parents=True)
        self.assertNotEqual(self.run_action('install').returncode,0)
        self.assert_original()

@unittest.skipUnless(os.name=='nt','Windows only')
class WindowsInstaller(InstallerContract,unittest.TestCase):
    def run_download(self,server):
        quote=lambda path:"'"+str(path).replace("'","''")+"'"
        script=self.base/'mock download.ps1'
        script.write_text('''function curl.exe {
    $items=@($args); $at=[Array]::IndexOf($items,'--output'); $resume=[Array]::IndexOf($items,'--continue-at')
    if ($at -lt 0 -or $resume -lt 0 -or $items[$resume+1] -ne '-') { throw 'Missing resume option' }
    $out=$items[$at+1]
    if ((Get-Item -LiteralPath $out).Length -ne 20) { throw 'Partial download not reused' }
    Copy-Item -LiteralPath $env:TEST_PACK_SOURCE -Destination $out -Force
    $global:LASTEXITCODE=0
}
'''+'& '+quote(ROOT/'scripts/windows.ps1')+' -Action Install -GamePath '+quote(self.game)+' -PackagePath '+quote(self.package)+' -NoDialog\n',encoding='utf-8-sig')
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],env=dict(os.environ,TEST_PACK_SOURCE=str(server)),capture_output=True,text=True,encoding='utf-8',errors='replace')

    def run_action(self,action):
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/windows.ps1'),
            '-Action',action,'-GamePath',str(self.game),'-PackagePath',str(self.package),'-NoDialog'],capture_output=True,text=True,encoding='utf-8',errors='replace')
        if action=='install' and result.returncode:print(result.stdout+result.stderr)
        return result

    def test_rollback_after_late_file_lock(self):
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.CreateFileW(str(self.audio/'GameAudio_Wambus.bank'),0x80000000,1,None,3,0,None)
        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
        try:self.assertNotEqual(self.run_action('install').returncode,0)
        finally:kernel.CloseHandle(handle)
        self.assertTrue((self.audio/'.bugsnax-russian-voice/backup/GameAudio_Filbo.bank').exists())
        self.assertTrue(list((self.audio/'.bugsnax-russian-voice').glob('transaction-*/GameAudio_Filbo.bank.old')))
        self.assert_original()

@unittest.skipUnless(os.name!='nt' or os.environ.get('BUGSNAX_TEST_WSL'),'Set BUGSNAX_TEST_WSL to a WSL distribution to test shell installer')
class ShellInstaller(InstallerContract,unittest.TestCase):
    def run_download(self,server):
        fake=self.base/'download bin';fake.mkdir()
        curl=fake/'curl'
        curl.write_text('''#!/bin/bash
set -eu
out=''; resume=0
while [ "$#" -gt 0 ]; do
 case "$1" in
  --output) out="$2"; shift 2;;
  --continue-at) [ "$2" = - ]; resume=1; shift 2;;
  *) shift;;
 esac
done
[ "$resume" = 1 ]
[ "$(wc -c < "$out" | tr -d ' ')" = 20 ]
cp "$TEST_PACK_SOURCE" "$out"
''',newline='\n')
        if os.name=='nt':
            subprocess.run(['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','chmod','+x',linux_path(curl)],check=True)
            args=['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','env','BUGSNAX_PACKAGE_ROOT='+linux_path(self.package),
                  'TEST_PACK_SOURCE='+linux_path(server),'PATH='+linux_path(fake)+':/usr/local/bin:/usr/bin:/bin','bash',linux_path(ROOT/'scripts/macos.sh'),'install',linux_path(self.game)]
        else:
            curl.chmod(0o755)
            args=['env','BUGSNAX_PACKAGE_ROOT='+str(self.package),'TEST_PACK_SOURCE='+str(server),'PATH='+str(fake)+':/usr/local/bin:/usr/bin:/bin','/bin/bash',str(ROOT/'scripts/macos.sh'),'install',str(self.game)]
        return subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')

    def run_action(self,action):
        if os.name=='nt':
            args=['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','env','BUGSNAX_PACKAGE_ROOT='+linux_path(self.package),
                  'bash',linux_path(ROOT/'scripts/macos.sh'),action,linux_path(self.game)]
        else:
            args=['env','BUGSNAX_PACKAGE_ROOT='+str(self.package),'/bin/bash',str(ROOT/'scripts/macos.sh'),action,str(self.game)]
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
        if action=='install' and result.returncode:print(result.stdout+result.stderr)
        return result

    def test_app_bundle_location(self):
        nested=self.game/'Bugsnax.app/Contents/Resources/Content/Audio/Build/Desktop'
        nested.parent.mkdir(parents=True)
        shutil.move(str(self.audio),nested);self.audio=nested
        self.assertEqual(self.run_action('install').returncode,0)
        self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_repair_real_pcm_headers_without_download(self):
        from test_fsb5_layout import riff_bank
        old=riff_bank(legacy=True);new=riff_bank()
        current=['name\toriginal_sha256\tpatched_sha256\tbytes']
        previous=[current[0]]
        for name,data in self.originals.items():
            (self.audio/name).write_bytes(old)
            saved=self.audio/'.bugsnax-russian-voice/backup'/name
            saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(data)
            current.append(f'{name}\t{sha(data)}\t{sha(new)}\t{len(new)}')
            previous.append(f'{name}\t{sha(data)}\t{sha(old)}\t{len(old)}')
        (self.package/'manifest.tsv').write_bytes(('\n'.join(current)+'\n').encode())
        (self.package/'previous-manifest.tsv').write_bytes(('\n'.join(previous)+'\n').encode())
        shutil.rmtree(self.package/'payload')
        for _ in range(2):
            result=self.run_action('repair')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        for name in self.originals:self.assertEqual((self.audio/name).read_bytes(),new)
        self.assertEqual(self.run_action('uninstall').returncode,0)
        self.assert_original()

    def test_repair_rejects_unmodified_game(self):
        self.assertNotEqual(self.run_action('repair').returncode,0)
        self.assert_original()

    def test_shell_rollback(self):
        # Fail only the second live-bank rename after the first has succeeded.
        fake=self.base/'bin';fake.mkdir()
        wrapper=fake/'mv'
        wrapper.write_text('#!/bin/bash\ncase "$*" in *GameAudio_Wambus.bank.new*) exit 1;; esac\nexec /bin/mv "$@"\n',newline='\n')
        if os.name=='nt':
            subprocess.run(['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','chmod','+x',linux_path(wrapper)],check=True)
            args=['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','env','BUGSNAX_PACKAGE_ROOT='+linux_path(self.package),
                  'PATH='+linux_path(fake)+':/usr/local/bin:/usr/bin:/bin','bash',linux_path(ROOT/'scripts/macos.sh'),'install',linux_path(self.game)]
        else:
            wrapper.chmod(0o755)
            args=['env','BUGSNAX_PACKAGE_ROOT='+str(self.package),'PATH='+str(fake)+':/usr/local/bin:/usr/bin:/bin','/bin/bash',str(ROOT/'scripts/macos.sh'),'install',str(self.game)]
        self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
        self.assertTrue(list((self.audio/'.bugsnax-russian-voice').glob('transaction.*/GameAudio_Filbo.bank.old')))
        self.assert_original()

if __name__=='__main__':
    (ROOT/'test-results').mkdir(exist_ok=True)
    unittest.main()
