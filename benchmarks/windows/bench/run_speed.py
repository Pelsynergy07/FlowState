import argparse,time,json,statistics,wave,hashlib,os
import numpy as np
from common import *
from flowstate.text.formatter import SmartFormatter,_build_messages
from flowstate.text.pipeline import CleanupPipeline
from backends.formatters import load as load_formatter
from backends.asr import load as load_asr

def run(model,tier,kind='formatter',threads=6,mode='shipped',audio=None,repetitions=10,protocol='speed-v2-natural-prose'):
 out=result_dir(tier,'speed-'+model+'-'+mode)
 with MemorySampler() as mem:
  start=time.perf_counter();backend=load_formatter(model,tier,mode,threads) if kind=='formatter' else load_asr(model,tier,threads);load_s=time.perf_counter()-start
  if kind=='formatter':
   fm=SmartFormatter();fm._backend=backend;pipe=CleanupPipeline(formatter=fm)
   s60=next(c['input'] for c in [json.loads(line) for line in (ROOT/'data/format_cases.jsonl').read_text().splitlines()] if c['category']=='window60')
   text='';prose=json.loads((ROOT/'data/recording_references.json').read_text())[22]['reference']
   # A chunk near 220 model tokens, measured with this candidate's own tokenizer.
   for w in prose.split():
    if backend.count_tokens(text+' '+w)>220:break
    text=(text+' '+w).strip()
   inputs={'60_words':s60,'220_tokens':text}
   for label,text in inputs.items():
    for i in range(3+repetitions):
     backend.calls.clear();cpu_start=time.process_time();start=time.perf_counter();output=pipe.run(text,allow_load=False,budget_seconds=600);elapsed=time.perf_counter()-start
     if i>=3:
      calls=list(backend.calls)
      if any(c.get('error') for c in calls):raise RuntimeError('Backend inference failed; this fallback latency is not a valid model speed result: '+str([c['error'] for c in calls if c.get('error')]))
      tokens=sum(c['output_tokens'] for c in calls);gen_s=sum(c['seconds'] for c in calls)
      append_jsonl(out/'speed.jsonl',dict(protocol=protocol,input_sha256=hashlib.sha256(text.encode()).hexdigest(),input_text=text,process_cpu_seconds=time.process_time()-cpu_start,system_load_average=os.getloadavg() if hasattr(os,'getloadavg') else None,raw_calls=calls,kind=kind,model=model,tier=tier,mode=mode,input_label=label,iteration=i-3,seconds=elapsed,input_words=len(text.split()),input_tokens=backend.count_tokens(text),llm_calls=len(calls),output_tokens=tokens,generation_seconds=gen_s,tokens_per_second=tokens/gen_s if gen_s else None,inside_3_5=elapsed<=3.5,inside_4=elapsed<=4,inside_8=elapsed<=8,output=output))
  else:
   if not audio:raise ValueError('Pass a real speech WAV for ASR speed measurements; silence is not a speech-speed proxy.')
   import soundfile as sf
   data,rate=sf.read(audio,dtype='int16');data=data[:14*rate]
   if rate!=16000 or data.ndim!=1 or len(data)!=224000:raise ValueError('ASR speed input must contain at least 14 seconds of 16kHz mono speech.')
   path=out/'speed_14s.wav';sf.write(path,data,rate,subtype='PCM_16')
   for i in range(3+repetitions):
    start=time.perf_counter();words=backend.transcribe_words(path);elapsed=time.perf_counter()-start
    if i>=3:append_jsonl(out/'speed.jsonl',dict(kind=kind,model=model,tier=tier,iteration=i-3,seconds=elapsed,rtf=elapsed/14,output=' '.join(w[2] for w in words)))
 dump(out/'resources.json',dict(load_seconds=load_s,load_cache_state='OS filesystem cache uncontrolled; NOT cold-after-reboot',warmups=3,timed_repetitions=repetitions,peak_process_rss_bytes=mem.peak_rss,peak_process_tree_rss_bytes=mem.peak_tree_rss,peak_device_vram_bytes=mem.peak_vram,threads=threads))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--tier',default='t3');p.add_argument('--kind',default='formatter',choices=['formatter','asr']);p.add_argument('--threads',type=int,default=6);p.add_argument('--mode',default='shipped');p.add_argument('--audio');p.add_argument('--repetitions',type=int,default=10);p.add_argument('--protocol',default='speed-v2-natural-prose');a=p.parse_args();run(a.model,a.tier,a.kind,a.threads,a.mode,a.audio,a.repetitions,a.protocol)
