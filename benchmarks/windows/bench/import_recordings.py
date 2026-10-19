import pathlib,json,argparse,hashlib
import av,numpy as np,soundfile as sf
p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--references',required=True);a=p.parse_args()
ROOT=pathlib.Path(__file__).resolve().parent;rows=[];out=ROOT/'data/recordings';out.mkdir(parents=True,exist_ok=True)
for c in json.loads(pathlib.Path(a.references).read_text()):
 if not c.get('verified'):print('Skipped unverified reference:',c['id']);continue
 files=list(pathlib.Path(a.folder).glob(c['id']+'.*'))
 if len(files)!=1:print('Expected one recording for',c['id'],'found',len(files));continue
 path=files[0];parts=[]
 with av.open(str(path)) as container:
  resampler=av.audio.resampler.AudioResampler(format='s16',layout='mono',rate=16000)
  for frame in container.decode(audio=0):
   for f in resampler.resample(frame):parts.append(f.to_ndarray().reshape(-1))
  for f in resampler.resample(None):parts.append(f.to_ndarray().reshape(-1))
 if not parts:raise RuntimeError('Empty recording: '+str(path))
 audio=np.concatenate(parts);wav=out/(c['id']+'.wav');sf.write(wav,audio,16000,subtype='PCM_16')
 rows.append(dict(id=c['id'],subset='D1-owner',path=str(wav.relative_to(ROOT)),reference=c['reference'],expected=c['expected'],duration=len(audio)/16000,original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),punctuation_reference=False,word_alignment_reference=False,terms=c.get('terms',[])))
(ROOT/'data/owner_manifest.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n');print('Imported',len(rows),'verified recordings locally. No upload performed.')
