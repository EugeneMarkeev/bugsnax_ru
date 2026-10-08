"""Build a small installer and an independent, authenticated voice archive."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from build_release import digest
from fsb5_layout import validate_pcm_bank

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.2'
SOUND_VERSION='0.1.1'

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
    parser.add_argument('--version',default=VERSION)
    parser.add_argument('--sound-version',default=SOUND_VERSION)
    parser.add_argument('--include-legacy-repair',action='store_true',help='Only for the original header-only repair release')
    args=parser.parse_args()
    version=args.version
    sound_version=args.sound_version
    if args.source:
        quality=json.loads((args.source/'quality_summary.json').read_text(encoding='utf-8'))
        assert quality['ready_to_install']
        banks=json.loads((args.source/'bank_validation.json').read_text(encoding='utf-8'))
        assert all(b.get('builder_revision')==2 and b.get('native_pcm_verified') for b in banks), 'Native packed-PCM verification required'
        previous_path=ROOT/'previous-manifest.tsv'
        historical=[]
        for manifest in (previous_path,ROOT/'manifest.tsv'):
            if manifest.exists():
                with manifest.open(encoding='utf-8',newline='') as f:historical.extend(csv.DictReader(f,delimiter='\t'))
        historical={tuple(r[k] for k in ('name','original_sha256','patched_sha256','bytes')) for r in historical}
        previous_path.write_text('name\toriginal_sha256\tpatched_sha256\tbytes\n'+''.join('\t'.join(r)+'\n' for r in sorted(historical)),encoding='utf-8')
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
    for bank in banks:
        path=ROOT/'payload'/bank['name']
        assert digest(path)==bank['patched_sha256'],bank['name']
        validate_pcm_bank(path.read_bytes())
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    sound=dist/f'Bugsnax-Sound-Pack-v{sound_version}.zip'
    pack(sound,['payload/'+b['name'] for b in banks])
    sound_sha=digest(sound)
    url=f'https://github.com/EugeneMarkeev/bugsnax_ru/releases/download/v{version}/{sound.name}'
    (ROOT/'sound-pack.tsv').write_bytes(f'filename\turl\tsha256\n{sound.name}\t{url}\t{sound_sha}\n'.encode())
    meta=json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
    meta.update(version=version,sound_pack_version=sound_version)
    if args.source:
        meta.update(fragments=quality['speech_files'],voices=len(quality['cast']),banks=len(banks),validation=quality['validation_note'])
    (ROOT/'release.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    installer=dist/f'Bugsnax-Installer-v{version}.zip'
    files=['Install.cmd','Uninstall.cmd','Install.command','Uninstall.command','README.md','CHANGELOG.md','manifest.tsv','previous-manifest.tsv','release.json','sound-pack.tsv','docs/voices.txt']
    if args.include_legacy_repair:files.append('Repair.command')
    files += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'scripts').glob('*') if p.is_file()]
    pack(installer,files,'Bugsnax-Russian-Voice/')
    sums=f'{digest(installer)}  {installer.name}\n{sound_sha}  {sound.name}\n'
    if args.include_legacy_repair:
        repair=dist/f'Bugsnax-Mac-Audio-Repair-v{version}.zip'
        pack(repair,['Repair.command','Uninstall.command','README.md','manifest.tsv','previous-manifest.tsv','scripts/macos.sh','scripts/repair_bank.pl'],'Bugsnax-Russian-Voice/')
        sums+=f'{digest(repair)}  {repair.name}\n'
    (dist/f'SHA256SUMS-v{version}.txt').write_bytes(sums.encode())
    print(f'Installer: {installer.stat().st_size} bytes; voices: {sound.stat().st_size/1024**2:.1f} MiB',flush=True)

if __name__=='__main__':main()
