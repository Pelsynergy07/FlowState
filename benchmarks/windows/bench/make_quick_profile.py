"""A fixed, varied 100-example screen for practical model choice; not certification."""
import json,random,collections
from common import ROOT,dump
rng=random.Random(1729)
rows=[json.loads(x) for x in (ROOT/'data/audio_manifest.jsonl').read_text().splitlines()]
by=collections.defaultdict(list)
for r in rows:by[r['subset']].append(r)
print({k:len(v) for k,v in by.items()})
selected=[]
for subset,n in [('test-clean',42),('test-other',40)]:selected+=rng.sample(sorted(by[subset],key=lambda r:r['id']),n)
noise=[r for r in rows if 'noise' in r['id']]
noise_ids=sorted(set(r['id'].split('-noise-')[0] for r in noise));chosen=set(rng.sample(noise_ids,6))
selected += [r for r in noise if r['id'].split('-noise-')[0] in chosen]
longs=sorted([r for r in rows if r['duration']>60],key=lambda r:r['duration'])
selected += [longs[0],longs[len(longs)//2],longs[-1]]
selected += [r for r in rows if r['subset']=='silence']
assert len(selected)==100 and len({r['id'] for r in selected})==100
(ROOT/'data/quick_audio_manifest.jsonl').write_text('\n'.join(json.dumps(r) for r in selected)+'\n')
formats=[json.loads(x) for x in (ROOT/'data/format_cases.jsonl').read_text().splitlines()];cats=collections.defaultdict(list)
for r in formats:
 if r['base_id'] not in cats[r['category']]:cats[r['category']].append(r['base_id'])
chosen_bases=[]
for cat,ids in sorted(cats.items()):chosen_bases+=rng.sample(sorted(ids),4 if cat in ['email','numbered_list','implicit_list','long_prose','injection'] else 3)
quick=[r for r in formats if r['base_id'] in chosen_bases]
assert len(quick)==100
(ROOT/'data/quick_format_cases.jsonl').write_text('\n'.join(json.dumps(r) for r in quick)+'\n')
dump(ROOT/'quick_profile.json',dict(name='quick-insight-100',seed=1729,audio_ids=[r['id'] for r in selected],format_ids=[r['id'] for r in quick],purpose='Fast directional decision requested by owner; smaller samples have wider uncertainty',speech_models=['whisper-base','whisper-small','whisper-turbo','parakeet-v2-int8','parakeet-v3-int8','parakeet-coreml-v2','parakeet-coreml-v3','parakeet-coreml-v3-int4','parakeet-coreml-v3-int8v2','parakeet-coreml-redux'],deferred=['portable fp32 Parakeet','distil Whisper','3B and 1.7B extra formatter sweeps','Mac CPU CT2 surrogate for Windows GPU','30-trial speed expansion','all-model streaming permutations']))
print('Quick profile: 100 audio examples; 100 text examples covering all 15 categories; 3 long recordings.')
