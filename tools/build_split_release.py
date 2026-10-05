"""Build a small installer and an independent, authenticated voice archive."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from build_release import digest

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.1'
SOUND_VERSION='0.1.0'

def pack(output,entries,prefix=''):
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for relative in entries:
            path=ROOT/relative
            info=zipfile.ZipInfo(prefix+relative)
            info.create_system=3
            info.external_attr=((0o100755 if path.suffix in ('.sh','.command') else 0o100644)<<16)
            info.compress_type=zipfile.ZIP_DEFLATED
            with path.open('rb') as source,archive.open(info,'w',force_zip64=True) as dest:shutil.copyfileobj(source,dest,1024*1024)
            print('Packed:',relative,flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,help='Optional certified campaign folder')
    args=parser.parse_args()
    if args.source:
        quality=json.loads((args.source/'quality_summary.json').read_text(encoding='utf-8'))
        assert quality['ready_to_install']
        banks=json.loads((args.source/'bank_validation.json').read_text(encoding='utf-8'))
        payload=ROOT/'payload';payload.mkdir(exist_ok=True)
        rows=['name\toriginal_sha256\tpatched_sha256\tbytes']
        for bank in banks:
            name=bank['bank'];assert Path(name).name==name
            source=args.source/'banks'/name
            assert digest(source)==bank['patched_sha256']
            target=payload/name
            if not target.exists() or digest(target)!=bank['patched_sha256']:shutil.copyfile(source,target)
            rows.append(f"{name}\t{bank['original_sha256']}\t{bank['patched_sha256']}\t{source.stat().st_size}")
        (ROOT/'manifest.tsv').write_bytes(('\n'.join(rows)+'\n').encode())
    with (ROOT/'manifest.tsv').open(encoding='utf-8',newline='') as f: banks=list(csv.DictReader(f,delimiter='\t'))
    for bank in banks:assert digest(ROOT/'payload'/bank['name'])==bank['patched_sha256'],bank['name']
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    sound=dist/f'Bugsnax-Sound-Pack-v{SOUND_VERSION}.zip'
    pack(sound,['payload/'+b['name'] for b in banks])
    sound_sha=digest(sound)
    url=f'https://github.com/EugeneMarkeev/bugsnax_ru/releases/download/v{VERSION}/{sound.name}'
    (ROOT/'sound-pack.tsv').write_bytes(f'filename\turl\tsha256\n{sound.name}\t{url}\t{sound_sha}\n'.encode())
    meta=json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
    meta.update(version=VERSION,sound_pack_version=SOUND_VERSION)
    (ROOT/'release.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    installer=dist/f'Bugsnax-Installer-v{VERSION}.zip'
    files=['Install.cmd','Uninstall.cmd','Install.command','Uninstall.command','README.md','CHANGELOG.md','manifest.tsv','release.json','sound-pack.tsv','docs/voices.txt']
    files += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'scripts').glob('*') if p.is_file()]
    pack(installer,files,'Bugsnax-Russian-Voice/')
    (dist/f'SHA256SUMS-v{VERSION}.txt').write_bytes(f'{digest(installer)}  {installer.name}\n{sound_sha}  {sound.name}\n'.encode())
    print(f'Installer: {installer.stat().st_size} bytes; voices: {sound.stat().st_size/1024**2:.1f} MiB',flush=True)

if __name__=='__main__':main()
