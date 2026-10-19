"""Public local evaluation data; no user recording ever leaves this machine."""
import argparse,pathlib,urllib.request,hashlib,tarfile,json,random,collections,wave
import numpy as np,soundfile as sf
import concurrent.futures,time,os
ROOT=pathlib.Path(__file__).resolve().parent;D=ROOT/'data';RAW=D/'public';RAW.mkdir(parents=True,exist_ok=True);seed=1729

def write(path,audio):
 path.parent.mkdir(parents=True,exist_ok=True);sf.write(path,audio,16000,subtype='PCM_16');return str(path.relative_to(ROOT))
def download_archive(url,archive):
 partial=archive.with_suffix('.partial');partial.touch(exist_ok=True)
 # Fetch fixed ranges with explicit timeouts, so one stalled socket cannot hang a run forever.
 chunk=8*1024*1024
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=0-0'}),timeout=45) as r:
  if r.status!=206:raise RuntimeError('Server did not support resumable byte ranges')
  total=int(r.headers['Content-Range'].split('/')[-1])
 start=partial.stat().st_size
 if start>total:raise RuntimeError('Partial archive exceeds published size')
 ranges=[(pos,min(pos+chunk,total)-1) for pos in range(start,total,chunk)]
 def fetch(bounds):
  lo,hi=bounds;request=urllib.request.Request(url,headers={'Range':f'bytes={lo}-{hi}'})
  for attempt in range(5):
   try:
    with urllib.request.urlopen(request,timeout=45) as response:
     if response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {lo}-'):raise RuntimeError('Unexpected byte range')
     data=response.read()
    if len(data)!=hi-lo+1:raise RuntimeError('Truncated byte range')
    return lo,data
   except Exception:
    if attempt==4:raise
    time.sleep(2)
 with partial.open('r+b') as f:
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
   for lo,data in pool.map(fetch,ranges):
    f.seek(lo);f.write(data);f.flush();print('Public archive',archive.name,'verified-through bytes',lo+len(data),'/',total,flush=True)
 if partial.stat().st_size!=total:raise RuntimeError('Incomplete archive')
 # tar parsing/CRC validates the gzip stream when it is extracted.
 partial.rename(archive)

def main(download=False):
 manifest=[];provenance=[];rng=random.Random(seed)
 for split in ['test-clean','test-other']:
  folder=RAW/'LibriSpeech'/split
  if not folder.exists():
   if not download:raise FileNotFoundError('Public audio absent. Run prepare_audio.py --download')
   url=f'https://www.openslr.org/resources/12/{split}.tar.gz';archive=RAW/(split+'.tar.gz');print('Downloading public archive',split,flush=True)
   if not archive.exists():
    download_archive(url,archive)
   h=hashlib.sha256()
   with archive.open('rb') as f:
    for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
   provenance.append(dict(url=url,sha256=h.hexdigest(),bytes=archive.stat().st_size,licence='CC BY 4.0',licence_source='https://www.openslr.org/12/'))
   with tarfile.open(archive) as tar:tar.extractall(RAW,filter='data')
  refs={}
  for p in folder.rglob('*.trans.txt'):
   for line in p.read_text().splitlines():
    uid,text=line.split(' ',1);refs[uid]=text
  files=sorted(folder.rglob('*.flac'));selected=sorted(rng.sample(files,300))
  for path in selected:
   uid=path.stem;a,rate=sf.read(path,dtype='float32');assert rate==16000
   wav=D/'audio'/split/(uid+'.wav');relative=write(wav,a)
   manifest.append(dict(id=uid,subset=split,path=relative,reference=refs[uid],duration=len(a)/rate,punctuation_reference=False,word_alignment_reference=False))
  if split=='test-clean':
   chapters=collections.defaultdict(list)
   for path in files:chapters[path.parent].append(path)
   long_count=0
   for chapter,paths in sorted(chapters.items()):
    audio=[];texts=[];components=[];offset=0.
    for p in sorted(paths):
     a,rate=sf.read(p,dtype='float32');components.append(dict(id=p.stem,start=offset,duration=len(a)/rate));offset+=len(a)/rate+.25;audio.extend([a,np.zeros(4000,np.float32)]);texts.append(refs[p.stem])
    joined=np.concatenate(audio)
    if len(joined)<=16000*60:continue
    uid=f'chapter-{long_count:02}';relative=write(D/'audio/longform'/(uid+'.wav'),joined)
    manifest.append(dict(id=uid,subset='concatenated-test-clean-chapters',path=relative,reference=' '.join(texts),duration=len(joined)/16000,components=components,punctuation_reference=False,word_alignment_reference=False,construction='sorted utterances from one chapter, 250ms digital silence between utterances'))
    long_count+=1
    if long_count==10:break
   if long_count<10:raise RuntimeError('Fewer than ten qualifying chapter recordings')
 # Synthetic stationary coloured noise, labelled honestly; not MUSAN or an accent test.
 noise_rng=np.random.default_rng(seed)
 for c in [x for x in manifest if x['subset']=='test-other']:
  a,rate=sf.read(ROOT/c['path'],dtype='float32');noise=noise_rng.normal(size=len(a));noise=np.convolve(noise,np.ones(5)/5,mode='same');noise/=np.sqrt(np.mean(noise**2))
  for snr in [10,5]:
   noise_scaled=noise*np.sqrt(np.mean(a**2))*10**(-snr/20);mixed=a+noise_scaled;peak=max(1.,float(np.max(np.abs(mixed)))/.99);mixed/=peak
   uid=c['id']+f'-noise-{snr}db';row=dict(c,id=uid,subset=f'synthetic-coloured-noise-{snr}db',path=write(D/'audio/noisy'/(uid+'.wav'),mixed),snr_db_measured=float(10*np.log10(np.mean((a/peak)**2)/np.mean((noise_scaled/peak)**2))),noise_seed=seed,noise_type='5-sample-smoothed Gaussian noise; NOT MUSAN')
   manifest.append(row)
 for seconds in [1,2,10]:
  uid=f'silence-{seconds}s';manifest.append(dict(id=uid,subset='silence',path=write(D/'audio/silence'/(uid+'.wav'),np.zeros(seconds*16000)),reference='',duration=seconds,punctuation_reference=False,word_alignment_reference=False))
 (D/'audio_manifest.jsonl').write_text('\n'.join(json.dumps(x) for x in manifest)+'\n')
 if provenance:(D/'public_downloads.json').write_text(json.dumps(provenance,indent=2)+'\n')
 (D/'audio_methodology.md').write_text('Seed 1729. Fixed 300 utterances each from test-clean/test-other. Ten chapter concatenations, each over one minute, with explicit 250ms gaps; construction components in manifest. No word-level ground truth is invented. LibriSpeech is read English, not the owner’s accent; references do not supply reliable punctuation/case. No punctuation or proper-noun accuracy claims on this set. Synthetic coloured-noise copies are supplementary, not recordings of real-world noise. CC BY 4.0: https://www.openslr.org/12/. Local evaluation only. Owner D1 recordings are still required for replacement decisions.\n')
 print('Prepared',len(manifest),'audio files',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');a=p.parse_args()
 try:main(a.download)
 except Exception as e:
  (D/'PREPARE_FAILED.json').write_text(json.dumps(dict(error=str(e)),indent=2));raise
