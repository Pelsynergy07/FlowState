"""One-command local runs. All timed inference is serialized."""
import argparse,subprocess,sys,time,json,traceback,pathlib,os
ROOT=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--tier',required=True,choices=['t1','t2','t3','t4']);p.add_argument('--matrix',default='shortlist',choices=['shortlist','full']);p.add_argument('--stage',default='all',choices=['format','audio','all']);p.add_argument('--download',action='store_true');p.add_argument('--wait-for-baseline',action='store_true');p.add_argument('--models',nargs='+');a=p.parse_args()
if a.tier in ['t2','t4']:os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['OMP_NUM_THREADS']='4'
from common import environment,dump,result_dir
quick=(ROOT/'quick_profile.json').exists()
out=result_dir(a.tier,'suite');threads=4 if a.tier in ['t2','t4'] else 6

def execute(script,*args):
 cmd=[sys.executable,str(ROOT/script),*map(str,args)];print('START',script,*args,flush=True)
 env=os.environ.copy()
 if script.startswith('download_'):env['HF_HUB_OFFLINE']='0'
 r=subprocess.run(cmd,cwd=ROOT,env=env)
 with (out/'steps.jsonl').open('a') as f:f.write(json.dumps(dict(script=script,args=list(map(str,args)),exit_code=r.returncode))+'\n')
 return r.returncode==0
if a.wait_for_baseline:
 while True:
  runs=list((ROOT/'results').glob('*/*format-qwen15-q4-shipped/resources.json'))
  if runs:break
  if list((ROOT/'results').glob('*/*format-qwen15-q4-shipped/FAILED.json')):raise RuntimeError('Baseline failed; inspect its FAILED.json')
  time.sleep(5)
if a.download:
 stages=[]
 if a.stage in ['format','all']:stages.append('First formatter tests')
 if a.stage in ['audio','all']:stages.append('Speech tests')
 for stage in stages:execute('download_models.py','--stage',stage,*(['--quick'] if quick else []))
 if a.stage in ['format','all'] and (a.tier=='t1' or a.matrix=='full'):
  if a.matrix=='full':execute('download_models.py','--stage','Extended formatter tests')
  else:execute('download_models.py','--repo','jncraton/Qwen2.5-1.5B-Instruct-ct2-int8','Qwen/Qwen2.5-0.5B-Instruct')
 if a.stage in ['audio','all']:execute('download_vad.py')
if a.stage in ['format','all']:
 models=a.models or (['qwen15-ct2','qwen05-ct2','qwen15-q4'] if a.tier=='t1' else ['qwen15-q4','qwen05-q4','qwen05-q8','qwen3-06-q8','t5-tiny'])
 if a.matrix=='full' and not a.models:models+=['qwen25-3-q4','qwen3-17-q8','qwen05-ct2','qwen25-3-ct2']
 models=list(dict.fromkeys(models))
 for model in ['qwen05-ct2','qwen25-3-ct2']:
  if model in models:execute('convert_ct2.py','--model',model)
 for model in models:
  for mode in (['shipped','forced'] if quick else ['shipped'] if a.tier=='t1' and model.endswith('ct2') else ['shipped','unlimited']):
   existing=[]
   for f in (ROOT/'results').glob('*/*/load.json'):
    try:
     d=json.loads(f.read_text());e=json.loads((f.parent/'environment.json').read_text())
     if d['model']==model and d['mode']==mode and e['tier']==a.tier and f.parent.parent.name==__import__('platform').node().split('.')[0] and (f.parent/'resources.json').exists():existing.append(f)
    except Exception:pass
   if not existing:execute('run_format.py','--model',model,'--tier',a.tier,'--mode',mode,'--threads',threads,'--full-set',*(['--budgets','4','600','--repeats','1'] if quick else []))
   execute('run_speed.py','--model',model,'--tier',a.tier,'--mode',mode,'--threads',threads)
   if not quick:execute('run_robustness.py','--model',model,'--tier',a.tier,'--mode',mode,'--threads',threads)
if a.stage in ['audio','all']:
 audio_manifest=ROOT/'data/audio_manifest.jsonl'
 audio_ready=audio_manifest.exists() and all((ROOT/json.loads(line)['path']).is_file() for line in audio_manifest.read_text().splitlines() if line.strip())
 if not audio_ready:execute('prepare_audio.py',*(['--download'] if a.download else []))
 manifest=ROOT/'data/evaluation_manifest.jsonl'
 merged=[]
 for file in ['audio_manifest.jsonl','owner_manifest.jsonl']:
  pth=ROOT/'data'/file
  if pth.exists():merged += [json.loads(line) for line in pth.read_text().splitlines() if line.strip()]
 if quick:
  quick_ids=set(json.loads((ROOT/'quick_profile.json').read_text())['audio_ids']);merged=[r for r in merged if r['id'] in quick_ids or r.get('subset','').startswith('owner')]
 manifest.write_text('\n'.join(json.dumps(row,ensure_ascii=False) for row in merged)+'\n')
 execute('build_streaming.py')
 for model in a.models or (['whisper-base','whisper-small','whisper-turbo','parakeet-v2-int8','parakeet-v3-int8'] if quick else ['whisper-base','whisper-small','whisper-distil','whisper-turbo','parakeet-v2-int8','parakeet-v3-int8','parakeet-v2-fp32','parakeet-v3-fp32']):
  execute('run_asr.py','--model',model,'--tier',a.tier,'--threads',threads,'--manifest',manifest)
  execute('run_streaming.py','--model',model,'--tier',a.tier,'--threads',threads,'--manifest',manifest)
  try:
   rows=[json.loads(x) for x in (ROOT/'data/audio_manifest.jsonl').read_text().splitlines()];long=next(c for c in rows if c['duration']>=14)
   execute('run_speed.py','--kind','asr','--model',model,'--tier',a.tier,'--threads',threads,'--audio',ROOT/long['path'])
  except Exception as e:print('ASR speed not run:',e,flush=True)
execute('analyze.py');dump(out/'FINISHED.json',dict(status='Suite ended; inspect individual exit codes and report limitations.'))
