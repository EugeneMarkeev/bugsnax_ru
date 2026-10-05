"""Record reviewable evidence without publishing game runtime binaries."""
import argparse
import difflib
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True,type=Path);args=parser.parse_args()
    load=lambda relative:json.loads((args.source/relative).read_text(encoding='utf-8'))
    native=load('native_pcm_validation.json');assert native['verified'] and native['banks']==16
    banks=load('bank_validation.json');assert all(b.get('native_pcm_verified') and b.get('builder_revision')==2 for b in banks)
    mixed=load('native_playback_check/report.json');mixed.pop('capture',None)
    normalize=lambda s:re.sub(r'[^а-яa-z0-9]+',' ',s.lower().replace('ё','е')).strip()
    ratio=difflib.SequenceMatcher(None,normalize(mixed['spoken_text']),normalize(mixed['mixed_transcript'])).ratio()
    assert mixed['native_decoded_pcm_matches_fitted'] and ratio>.9
    repair=json.loads((ROOT/'test-results/repair-actual-banks.json').read_text(encoding='utf-8'))
    assert len(repair)==16 and all(r['identical_to_rebuilt_bank'] for r in repair)
    events=load('studio_validation.json');assert len(events)==2469 and all(e['playing'] for e in events)
    report={'version':'0.1.2','native_pcm':native,'native_event_mapping_checked':len(events),'mixer_speech_check':mixed,'mixer_asr_similarity':ratio,'repair_results':repair,'interactive_walkthrough':False,'native_mac_playback_test':False}
    (ROOT/'docs/AUDIO_VALIDATION_v0.1.2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    quality=load('quality_summary.json')
    quality.update(native_pcm_samples=native['samples'],builder_revision=2,native_mixer_asr_similarity=ratio,macos_runtime_tested=False,validation_note='All 3993 packed samples decoded by Windows FMOD and matched byte for byte; 2469 event mappings checked; mixer speech recognized. Native Mac playback and full walkthrough not tested.')
    (args.source/'quality_summary.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Validated packed PCM, real mixer speech, event mappings and byte-identical repair.')
if __name__=='__main__':main()
