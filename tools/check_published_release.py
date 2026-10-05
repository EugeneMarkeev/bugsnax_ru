"""Verify public URLs and GitHub's SHA-256 digests after publication."""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
from build_release import digest
ROOT=Path(__file__).resolve().parents[1]
def main():
    version='0.1.2'
    raw=subprocess.check_output(['gh','release','view','v'+version,'--repo','EugeneMarkeev/bugsnax_ru','--json','url,isDraft,assets'],text=True,encoding='utf-8')
    release=json.loads(raw);assert not release['isDraft']
    assets={a['name']:a for a in release['assets']}
    names=['Bugsnax-Installer-v0.1.2.zip','Bugsnax-Sound-Pack-v0.1.1.zip','Bugsnax-Mac-Audio-Repair-v0.1.2.zip','SHA256SUMS-v0.1.2.txt']
    for name in names:
        asset=assets[name];assert asset['state']=='uploaded'
        expected=digest(ROOT/'dist'/name)
        assert asset['digest']=='sha256:'+expected
        assert '/download/v0.1.2/' in asset['url']
        request=urllib.request.Request(asset['url'],method='HEAD',headers={'User-Agent':'Bugsnax-Russian-Voice-Release-Check'})
        with urllib.request.urlopen(request,timeout=60) as response:assert response.status==200
        if asset['size']<100000:
            with urllib.request.urlopen(asset['url'],timeout=60) as response:assert hashlib.sha256(response.read()).hexdigest()==expected
        print(name,'public HTTP 200; SHA-256 verified',flush=True)
    (ROOT/'test-results/github-audio-fix-release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
