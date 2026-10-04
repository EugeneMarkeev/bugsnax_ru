"""Package certified audio; Python is for maintainers, not players."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    with path.open('rb') as stream:
        value=hashlib.sha256()
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
        return value.hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True,type=Path,help='Certified campaign folder')
    args=parser.parse_args()
    quality=json.loads((args.source/'quality_summary.json').read_text(encoding='utf-8'))
    assert quality['ready_to_install'],'Audio quality gate has not passed'
    banks=json.loads((args.source/'bank_validation.json').read_text(encoding='utf-8'))
    payload=ROOT/'payload';payload.mkdir(exist_ok=True)
    manifest=['name\toriginal_sha256\tpatched_sha256\tbytes']
    for bank in banks:
        name=bank['bank']
        assert Path(name).name==name and name.endswith('.bank')
        source=args.source/'banks'/name
        assert digest(source)==bank['patched_sha256'],f'Stale audio: {name}'
        shutil.copyfile(source,payload/name)
        manifest.append(f"{name}\t{bank['original_sha256']}\t{bank['patched_sha256']}\t{source.stat().st_size}")
    (ROOT/'manifest.tsv').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
    (ROOT/'release.json').write_text(json.dumps({'version':'0.1.0','steam_app_id':674140,
        'reference_windows_build':25460845,'fragments':quality['speech_files'],
        'voices':len(quality['cast']),'banks':len(banks),'windows':'native audio validated',
        'macos':'experimental; requires matching original bank checksums and Mac playback test',
        'validation':quality['validation_note']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    cast=ROOT/'docs';cast.mkdir(exist_ok=True)
    shutil.copyfile(args.source.parent/'voices/cast_ru.txt',cast/'voices.txt')
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    output=dist/'Bugsnax-Russian-Voice-v0.1.0.zip'
    files=['Install.cmd','Uninstall.cmd','Install.command','Uninstall.command','README.md','manifest.tsv','release.json']
    files += [str(p.relative_to(ROOT)).replace('\\','/') for folder in ('scripts','docs') for p in (ROOT/folder).rglob('*') if p.is_file()]
    files += ['payload/'+b['bank'] for b in banks]
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for relative in files:
            path=ROOT/relative
            info=zipfile.ZipInfo('Bugsnax-Russian-Voice/'+relative)
            info.create_system=3
            info.external_attr=((0o100755 if path.suffix in ('.sh','.command') else 0o100644)<<16)
            info.compress_type=zipfile.ZIP_DEFLATED
            with path.open('rb') as source,archive.open(info,'w',force_zip64=True) as dest:shutil.copyfileobj(source,dest,1024*1024)
            print('Packed:',relative,flush=True)
    (dist/(output.name+'.sha256')).write_text(digest(output)+'  '+output.name+'\n',encoding='ascii')
    print(f'Release: {output} ({output.stat().st_size/1024**2:.1f} MiB)',flush=True)

if __name__=='__main__':main()
