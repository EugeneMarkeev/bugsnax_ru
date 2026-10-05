"""Maintainer check: repaired legacy banks must equal the independently rebuilt pack."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
from build_release import digest
ROOT=Path(__file__).resolve().parents[1]
def linux(path):
    path=Path(path).resolve()
    return '/mnt/'+path.drive[0].lower()+str(path)[2:].replace('\\','/')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True,type=Path);parser.add_argument('--wsl',default='Ubuntu-22.04');args=parser.parse_args()
    reports=json.loads((args.source/'bank_validation.json').read_text(encoding='utf-8'))
    with (ROOT/'previous-manifest.tsv').open(encoding='utf-8') as f:previous={r['name']:r for r in csv.DictReader(f,delimiter='\t')}
    result=[]
    with tempfile.TemporaryDirectory(prefix='repair actual ',dir=ROOT/'test-results') as temp:
        for report in reports:
            name=report['bank'];source=ROOT/'payload'/name;target=Path(temp)/name
            assert digest(source)==previous[name]['patched_sha256']
            if os.name=='nt':cmd=['wsl.exe','-d',args.wsl,'--','perl',linux(ROOT/'scripts/repair_bank.pl'),linux(source),linux(target)]
            else:cmd=['perl',str(ROOT/'scripts/repair_bank.pl'),str(source),str(target)]
            subprocess.run(cmd,check=True)
            actual=digest(target);assert actual==report['patched_sha256'],name
            result.append({'bank':name,'sha256':actual,'identical_to_rebuilt_bank':True})
            target.unlink();print(name,'repair is byte-identical to rebuilt bank',flush=True)
    (ROOT/'test-results/repair-actual-banks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if __name__=='__main__':main()
