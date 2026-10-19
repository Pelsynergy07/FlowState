"""Download only explicitly selected, commit-pinned files. No private audio is read."""
import argparse,json,os,pathlib,hashlib,time
ROOT=pathlib.Path(__file__).resolve().parent
os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['HF_HOME']=str(ROOT/'.hf');os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ.pop('HF_HUB_OFFLINE',None)
from huggingface_hub import hf_hub_download
p=argparse.ArgumentParser();p.add_argument('--stage',default='First formatter tests');p.add_argument('--repo',nargs='+');p.add_argument('--quick',action='store_true');a=p.parse_args()
manifest=json.loads((ROOT/'model_manifest.json').read_text());catalogue=json.loads((ROOT/'model_catalogue.json').read_text())
records=[]
for m in manifest:
 if a.repo:
  if m['repo'] not in a.repo:continue
 elif m['stage']!=a.stage:continue
 if a.quick and m['repo']=='Systran/faster-distil-whisper-large-v3':continue
 target=ROOT/'models'/m['repo'].replace('/','--'); target.mkdir(parents=True,exist_ok=True)
 cat=next(x for x in catalogue['models'] if x['repo']==m['repo'])
 weights=m['weight_files']
 if a.quick and m['repo'].startswith('istupakov/parakeet'):
  weights=[f for f in weights if f.endswith('.int8.onnx') or f=='nemo128.onnx']
 files=weights+[x['path'] for x in cat['files'] if x['path'].endswith(('.json','.txt','.model')) and '/' not in x['path']]
 for name in dict.fromkeys(files):
  print('Downloading',m['repo'],name,flush=True)
  start=time.perf_counter()
  for attempt in range(5):
   try:path=pathlib.Path(hf_hub_download(m['repo'],name,revision=m['revision'],local_dir=target));break
   except Exception:
    if attempt==4:raise
    time.sleep(2)
  h=hashlib.sha256()
  with path.open('rb') as f:
   for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
  records.append({'repo':m['repo'],'revision':m['revision'],'file':name,'bytes':path.stat().st_size,'sha256':h.hexdigest(),'download_and_hash_seconds':time.perf_counter()-start})
 (target/'benchmark_download.json').write_text(json.dumps([r for r in records if r['repo']==m['repo']],indent=2))
print('Selected stage complete',flush=True)
