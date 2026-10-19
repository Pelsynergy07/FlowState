"""Convert pinned local Qwen2.5 checkpoints; record exact command and generated hashes."""
import argparse,subprocess,json,pathlib,hashlib,importlib.metadata,time,sys,os
ROOT=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--model',required=True,choices=['qwen05-ct2','qwen25-3-ct2']);a=p.parse_args()
repo={'qwen05-ct2':'Qwen/Qwen2.5-0.5B-Instruct','qwen25-3-ct2':'Qwen/Qwen2.5-3B-Instruct'}[a.model]
manifest=json.loads((ROOT/'model_manifest.json').read_text());entry=next(m for m in manifest if m['repo']==repo);source=ROOT/'models'/repo.replace('/','--');target=ROOT/'models'/(a.model+'-converted')
if (target/'conversion.json').exists():
 old=json.loads((target/'conversion.json').read_text())
 if old['source_revision']==entry['revision']:print('Pinned conversion already exists');raise SystemExit(0)
 raise SystemExit('Existing conversion has a different revision; preserve it and choose a new target directory.')
if not (source/'benchmark_download.json').exists():raise SystemExit('Download the pinned source repository first.')
command=[str(pathlib.Path(sys.executable).parent/('ct2-transformers-converter.exe' if os.name=='nt' else 'ct2-transformers-converter')),'--model',str(source),'--output_dir',str(target),'--quantization','int8','--copy_files','tokenizer.json','tokenizer_config.json']
start=time.perf_counter();subprocess.run(command,check=True)
files=[]
for path in target.rglob('*'):
 if path.is_file():
  h=hashlib.sha256()
  with path.open('rb') as f:
   for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
  files.append(dict(path=str(path.relative_to(target)),bytes=path.stat().st_size,sha256=h.hexdigest()))
(target/'conversion.json').write_text(json.dumps(dict(source_repo=repo,source_revision=entry['revision'],command=command,seconds=time.perf_counter()-start,ctranslate2=importlib.metadata.version('ctranslate2'),transformers=importlib.metadata.version('transformers'),generated_files=files),indent=2))
print('Conversion finished; generated sizes and hashes recorded')
