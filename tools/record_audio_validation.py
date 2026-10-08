"""Record reviewable evidence without publishing game runtime binaries."""
import argparse
import difflib
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True,type=Path);parser.add_argument('--version',required=True);args=parser.parse_args()
    load=lambda relative:json.loads((args.source/relative).read_text(encoding='utf-8'))
    native=load('native_pcm_validation.json');assert native['verified']
    banks=load('bank_validation.json');assert all(b.get('native_pcm_verified') and b.get('builder_revision')==2 for b in banks)
    mixed=load('native_playback_check/report.json');mixed.pop('capture',None)
    normalize=lambda s:re.sub(r'[^а-яa-z0-9]+',' ',s.lower().replace('ё','е')).strip()
    ratio=difflib.SequenceMatcher(None,normalize(mixed['spoken_text']),normalize(mixed['mixed_transcript'])).ratio()
    assert mixed['native_decoded_pcm_matches_fitted'] and ratio>.9
    quality=load('quality_summary.json')
    assert quality['ready_to_install'] and native['banks']==len(banks)
    events=load('studio_validation.json');assert len(events)==quality['speech_files'] and all(e['playing'] or (e.get('sample_only') and e.get('mapping_verified')) for e in events)
    report={'version':args.version,'native_pcm':native,'native_event_mapping_checked':sum(e['playing'] for e in events),'physical_sample_fragments':sum(bool(e.get('sample_only')) for e in events),'mixer_speech_check':mixed,'mixer_asr_similarity':ratio,'interactive_walkthrough':False,'native_mac_playback_test':False}
    (ROOT/f'docs/AUDIO_VALIDATION_v{args.version}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Validated packed PCM, real mixer speech and event mappings.')
if __name__=='__main__':main()
