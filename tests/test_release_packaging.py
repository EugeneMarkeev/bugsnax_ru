"""Exercise the installer/sound-pack contract without real game assets."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_split_release
from test_fsb5_layout import riff_bank

class ReleasePackagingTests(unittest.TestCase):
    def test_split_pack_preserves_upgrade_history_and_certified_counts(self):
        (ROOT/'test-results').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='release test ',dir=ROOT/'test-results') as temporary:
            base=Path(temporary);package=base/'package';source=base/'certified audio'
            (source/'banks').mkdir(parents=True);(package/'docs').mkdir(parents=True)
            (package/'scripts').mkdir()
            for name in ('Install.cmd','Uninstall.cmd','Install.command','Uninstall.command','README.md','CHANGELOG.md','docs/voices.txt','scripts/macos.sh'):
                (package/name).write_text('fixture\n',encoding='utf-8')
            name='GameAudio_Filbo.bank';bank=riff_bank()
            (source/'banks'/name).write_bytes(bank)
            original='c'*64;broken='a'*64;previous='b'*64
            header='name\toriginal_sha256\tpatched_sha256\tbytes\n'
            (package/'previous-manifest.tsv').write_text(header+f'{name}\t{original}\t{broken}\t1\n',encoding='utf-8')
            (package/'manifest.tsv').write_text(header+f'{name}\t{original}\t{previous}\t1\n',encoding='utf-8')
            (package/'release.json').write_text(json.dumps({'version':'0.1.2'}),encoding='utf-8')
            (source/'quality_summary.json').write_text(json.dumps({'ready_to_install':True,'speech_files':3,'cast':{'Filbo':{},'Jamfoot':{}},'validation_note':'fixture proof'}),encoding='utf-8')
            (source/'bank_validation.json').write_text(json.dumps([{'bank':name,'builder_revision':2,'native_pcm_verified':True,'original_sha256':original,'patched_sha256':hashlib.sha256(bank).hexdigest()}]),encoding='utf-8')
            args=['build_split_release.py','--source',str(source),'--version','0.2.0','--sound-version','0.2.0']
            with patch.object(build_split_release,'ROOT',package),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                build_split_release.main()
            metadata=json.loads((package/'release.json').read_text(encoding='utf-8'))
            self.assertEqual((metadata['version'],metadata['fragments'],metadata['voices'],metadata['banks']),('0.2.0',3,2,1))
            history=(package/'previous-manifest.tsv').read_text(encoding='utf-8')
            self.assertIn(broken,history);self.assertIn(previous,history)
            dist=package/'dist'
            self.assertEqual(sorted(p.name for p in dist.iterdir()),['Bugsnax-Installer-v0.2.0.zip','Bugsnax-Sound-Pack-v0.2.0.zip','SHA256SUMS-v0.2.0.txt'])
            with zipfile.ZipFile(dist/'Bugsnax-Sound-Pack-v0.2.0.zip') as archive:
                self.assertEqual(archive.read('payload/'+name),bank)
            sound_digest=hashlib.sha256((dist/'Bugsnax-Sound-Pack-v0.2.0.zip').read_bytes()).hexdigest()
            self.assertIn(sound_digest,(package/'sound-pack.tsv').read_text(encoding='utf-8'))
            self.assertIn(sound_digest,(dist/'SHA256SUMS-v0.2.0.txt').read_text(encoding='utf-8'))
            with zipfile.ZipFile(dist/'Bugsnax-Installer-v0.2.0.zip') as archive:
                names=archive.namelist()
                self.assertFalse(any('payload/' in n or n.endswith('Repair.command') for n in names))
                command=archive.getinfo('Bugsnax-Russian-Voice/Install.command')
                self.assertTrue(command.external_attr>>16 & 0o111)
                self.assertIn(broken,archive.read('Bugsnax-Russian-Voice/previous-manifest.tsv').decode())
                self.assertIn(previous,archive.read('Bugsnax-Russian-Voice/previous-manifest.tsv').decode())
                self.assertIn('/download/v0.2.0/',archive.read('Bugsnax-Russian-Voice/sound-pack.tsv').decode())

if __name__=='__main__':unittest.main()
