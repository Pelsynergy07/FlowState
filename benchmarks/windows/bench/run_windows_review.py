"""Actual NVIDIA GPU follow-up. Never replace CUDA failure with CPU results."""
import sys,pathlib,os,subprocess,json
ROOT=pathlib.Path(__file__).resolve().parent
if os.name!='nt':raise SystemExit('This runner requires the Windows NVIDIA machine; no Mac GPU substitute is permitted.')
from common import result_dir,dump
import ctranslate2
if ctranslate2.get_cuda_device_count()<1:raise SystemExit('No usable CUDA GPU found. Resolve GPU setup before benchmarking.')
out=result_dir('t1','review2-gpu');failed=[]
def step(script,*args):
 env=os.environ.copy()
 if script.startswith('download_'):env['HF_HUB_OFFLINE']='0'
 print('START',script,*args,flush=True);r=subprocess.run([sys.executable,str(ROOT/script),*map(str,args)],cwd=ROOT,env=env)
 row=dict(script=script,args=list(map(str,args)),exit_code=r.returncode)
 with (out/'steps.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 if r.returncode:failed.append(row)
 return r.returncode==0
step('download_models.py','--repo','jncraton/Qwen2.5-1.5B-Instruct-ct2-int8','Qwen/Qwen2.5-3B-Instruct','deepdml/faster-whisper-large-v3-turbo-ct2','istupakov/parakeet-tdt-0.6b-v2-onnx','--quick')
step('download_vad.py')
step('convert_ct2.py','--model','qwen25-3-ct2')
manifest=ROOT/'data/quick_audio_manifest.jsonl'
ready=manifest.exists() and all((ROOT/json.loads(line)['path']).is_file() for line in manifest.read_text().splitlines() if line.strip())
if not ready:
 step('prepare_audio.py','--download');step('make_quick_profile.py')
for model in ['qwen15-ct2','qwen25-3-ct2']:
 for mode in ['shipped','forced']:
  step('run_format.py','--model',model,'--tier','t1','--mode',mode,'--full-set','--budgets',4,600,'--repeats',1)
 step('run_speed.py','--model',model,'--tier','t1')
step('build_streaming.py')
for speech,formatter in [('whisper-turbo','qwen15-ct2'),('parakeet-v2-int8','qwen15-ct2'),('whisper-turbo','qwen25-3-ct2')]:
 step('run_streaming.py','--model',speech,'--formatter',formatter,'--tier','t1','--manifest',manifest)
step('analyze.py');step('validate_report.py')
dump(out/'FINISHED.json',dict(status='Windows review queue ended',failed_steps=failed))
print('Finished. Keep the entire results folder; inspect any reported failed steps.')
