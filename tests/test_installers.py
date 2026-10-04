import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

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
    def run_action(self,action):
        if os.name=='nt':
            args=['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','env','BUGSNAX_PACKAGE_ROOT='+linux_path(self.package),
                  'bash',linux_path(ROOT/'scripts/macos.sh'),action,linux_path(self.game)]
        else:
            args=['env','BUGSNAX_PACKAGE_ROOT='+str(self.package),'bash',str(ROOT/'scripts/macos.sh'),action,str(self.game)]
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

    def test_shell_rollback(self):
        # Fail only the second live-bank rename after the first has succeeded.
        fake=self.base/'bin';fake.mkdir()
        wrapper=fake/'mv'
        wrapper.write_text('#!/bin/bash\ncase "$*" in *GameAudio_Wambus.bank.new*) exit 1;; esac\nexec /bin/mv "$@"\n')
        if os.name=='nt':
            subprocess.run(['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','chmod','+x',linux_path(wrapper)],check=True)
            args=['wsl.exe','-d',os.environ['BUGSNAX_TEST_WSL'],'--','env','BUGSNAX_PACKAGE_ROOT='+linux_path(self.package),
                  'PATH='+linux_path(fake)+':/usr/local/bin:/usr/bin:/bin','bash',linux_path(ROOT/'scripts/macos.sh'),'install',linux_path(self.game)]
        else:
            wrapper.chmod(0o755)
            args=['env','BUGSNAX_PACKAGE_ROOT='+str(self.package),'PATH='+str(fake)+':/usr/local/bin:/usr/bin:/bin','bash',str(ROOT/'scripts/macos.sh'),'install',str(self.game)]
        self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
        self.assertTrue(list((self.audio/'.bugsnax-russian-voice').glob('transaction.*/GameAudio_Filbo.bank.old')))
        self.assert_original()

if __name__=='__main__':
    (ROOT/'test-results').mkdir(exist_ok=True)
    unittest.main()
