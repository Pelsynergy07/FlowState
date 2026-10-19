import argparse,json,time,wave,traceback
import numpy as np
from common import *
from backends.asr import load,SPEECH
from backends.formatters import load as load_formatter
from flowstate.text.formatter import SmartFormatter,join_sections,capitalize_start
from flowstate.text.pipeline import CleanupPipeline,apply_rules
from flowstate.text.guard import preserves_words,repair
from flowstate.text.vocabulary import apply_vocabulary
from metrics import NORMALIZE,distance
from flowstate.text.formatter import needs_polish

class ObservedPipeline:
 def __init__(self,inner,backend):self.inner=inner;self.backend=backend;self.sections=[];self.phase="live"
 def __getattr__(self,name):return getattr(self.inner,name)
 def run(self,text,*args,**kwargs):
  ruled=apply_rules(apply_vocabulary(text));before=len(self.backend.calls) if self.backend else 0
  output=self.inner.run(text,*args,**kwargs)
  self.sections.append(dict(phase=self.phase,input=text,after_rules=ruled,needs_polish_after_rules=needs_polish(ruled),llm_calls=(len(self.backend.calls)-before) if self.backend else 0))
  return output

def simulate(c,engine,pipe,out):
 from streaming_core import WindowProcessor,STEP_SECONDS,LOOKAHEAD_SECONDS,LIVE_BUDGET_SECONDS,FINISH_BUDGET_SECONDS
 pipe.sections=[];pipe.phase="live"
 path=ROOT/c['path']
 with wave.open(str(path),'rb') as f:
  if f.getnchannels()!=1 or f.getsampwidth()!=2 or f.getframerate()!=16000:raise ValueError('Use 16kHz mono PCM16 WAV')
  rate=f.getframerate();audio=np.frombuffer(f.readframes(f.getnframes()),np.int16)
 duration=len(audio)/rate;proc=WindowProcessor(engine,pipe,out);virtual_time=0.;windows=[];failed=None;failure_context=None
 while proc._cursor+STEP_SECONDS+LOOKAHEAD_SECONDS<=duration:
  available=proc._cursor+STEP_SECONDS+LOOKAHEAD_SECONDS;start_virtual=max(virtual_time,available)
  if start_virtual>=duration:break
  begin=proc._window_begin();end=proc._cursor+STEP_SECONDS+LOOKAHEAD_SECONDS;before=proc._cursor;start=time.perf_counter()
  try:proc._process(audio[int(begin*rate):int(end*rate)],rate,begin,proc._cursor+STEP_SECONDS,budget=LIVE_BUDGET_SECONDS)
  except Exception as e:
   failed=str(e);failure_context=dict(begin=begin,end=end,cursor=before,clean_cut=proc._clean_cut,prior_words=proc._words[-20:],pending_words=proc._pending,new_words=getattr(engine,'last_words',None),new_words_path=getattr(engine,'last_path',None));break
  elapsed=time.perf_counter()-start;virtual_time=start_virtual+elapsed
  windows.append(dict(begin=begin,end=end,cursor=proc._cursor,seconds=elapsed,virtual_start=start_virtual,virtual_end=virtual_time))
  if proc._cursor<=before:failed='Cursor failed to advance';break
 # This event simulation measures actual processing durations, models audio arrival and backlog,
 # but does not claim measured wall-clock stop latency under capture/thread cancellation.
 backlog=max(0.,virtual_time-duration);start=time.perf_counter();recovered=bool(failed)
 pipe.phase="full_recovery" if recovered else "final"
 if recovered:
  recovered_segments,text=proc._recover(path);raw=' '.join(x[2] for x in recovered_segments)
 else:
  try:
   begin=proc._window_begin()
   if duration>proc._cursor:proc._process(audio[int(begin*rate):],rate,begin,duration,budget=FINISH_BUDGET_SECONDS,final=True,deadline=start+FINISH_BUDGET_SECONDS)
   text=join_sections(proc._cleaned)
   if pipe.grammar_enabled:
    text=apply_rules(text);raw=apply_rules(apply_vocabulary(' '.join(x[2] for x in proc._segments)))
    if not preserves_words(raw,text):text=repair(raw,text) or raw
   raw=' '.join(x[2] for x in proc._words)
  except Exception as e:
   failed=str(e);recovered=True;pipe.phase='full_recovery';recovered_segments,text=proc._recover(path);raw=' '.join(x[2] for x in recovered_segments)
 final_s=time.perf_counter()-start;ref=NORMALIZE(c['reference']).split()
 return dict(failure_context=failure_context,cleanup_sections=pipe.sections,id=c['id'],subset=c['subset'],duration=duration,reference=c['reference'],raw_output=raw,output=text,wer=distance(ref,NORMALIZE(raw).split()),formatted_lexical_error=distance(ref,NORMALIZE(text).split()),windows=windows,simulated_stop_seconds=backlog+final_s,measured_final_processing_seconds=final_s,simulated_backlog_seconds=backlog,recovered_full_recording=recovered,error=failed,raw_committed_words=None if recovered else proc._words,timing_limitation='event-driven simulation; no live recorder/thread cancellation measurement',seam_metric_limitation='Per-boundary dropped/duplicate words require reference word alignments; not inferred from whole-file WER')
def run(model,tier,manifest,formatter='rules',threads=6):
 out=result_dir(tier,'stream-'+model+'-'+formatter)
 with MemorySampler() as mem:
  start=time.perf_counter();engine=load(model,tier,threads);fm=SmartFormatter();fm._backend=load_formatter(formatter,tier,threads=threads);pipe=ObservedPipeline(CleanupPipeline(formatter=fm),fm._backend);load_s=time.perf_counter()-start
  for c in [json.loads(x) for x in pathlib.Path(manifest).read_text().splitlines()]:
   if c['duration']<=60:continue
   r=simulate(c,engine,pipe,out);r.update(model=model,tier=tier,formatter=formatter,backend_metadata=getattr(engine,'metadata',{}));append_jsonl(out/'streaming.jsonl',r);print(model,c['id'],r['wer'],flush=True)
 dump(out/'resources.json',dict(load_seconds=load_s,peak_process_rss_bytes=mem.peak_rss,peak_process_tree_rss_bytes=mem.peak_tree_rss,peak_device_vram_bytes=mem.peak_vram,scope='ASR and formatter loaded together; Apple XPC allocations outside this process tree may be missed'))
 dump(out/'FINISHED.json',dict(status='Streaming run ended'))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',required=True,choices=list(SPEECH));p.add_argument('--tier',default='t3');p.add_argument('--formatter',default='rules');p.add_argument('--manifest',default=str(ROOT/'data/audio_manifest.jsonl'));p.add_argument('--threads',type=int,default=6);a=p.parse_args();run(a.model,a.tier,a.manifest,a.formatter,a.threads)
