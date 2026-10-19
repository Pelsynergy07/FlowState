import argparse,json,time,logging,traceback,gc
from common import *
from flowstate.text import formatter as fm,guard
from flowstate.text.pipeline import CleanupPipeline,apply_rules
from flowstate.text.vocabulary import apply_vocabulary
from backends.formatters import load,MODELS
from metrics import format_metrics
logging.basicConfig(level=logging.ERROR)
def run(model,tier,mode,budgets,repeats,limit=0,categories=None,threads=6,full_set=False):
 out=result_dir(tier,'format-'+model+'-'+mode);data=cases(full=full_set)
 if categories:data=[c for c in data if c['category'] in categories]
 if limit:data=data[:limit]
 dump(out/'run_manifest.json',dict(planned_cases=len(data)*len(budgets)*repeats,budgets=budgets,repeats=repeats,mode=mode,model=model,force_ai=mode=='forced',full_set=full_set))
 try:
  with MemorySampler() as memory:
   start=time.perf_counter();backend=load(model,tier,'unlimited' if mode=='forced' else mode,threads);load_s=time.perf_counter()-start
   formatter=fm.SmartFormatter();formatter._backend=backend;pipe=CleanupPipeline(formatter=formatter)
   # Pay prompt-cache/first-inference costs before scored data. Three warm-ups, not included in metrics.
   if backend:
    for _ in range(3):
     for x in backend.stream(fm._build_messages('please save the report before the team meeting starts tomorrow morning'),max_tokens=40):pass
   dump(out/'load.json',dict(model=model,mode=mode,load_seconds=load_s,threads=threads,warmups=3,physical_backend=type(backend.inner).__name__ if backend else 'rules',physical_runtime=backend.inner.runtime if backend else 'none',reported_runtime_for_cpu_skip=backend.runtime if backend else None))
   repair_original=fm.repair;salvage_original=fm.salvage_prefix
   events=[]
   def repair(source,output,*a,**kw):
    fixed=repair_original(source,output,*a,**kw);events.append(dict(kind='repair',source=source,raw=output,fixed=fixed,outcome='rejected' if fixed is None else 'accepted' if fixed==output.strip() else 'repaired'));return fixed
   def salvage(source,output):
    fixed=salvage_original(source,output);events.append(dict(kind='salvage',source=source,raw=output,fixed=fixed,outcome='salvaged' if fixed is not None else 'fallback'));return fixed
   fm.repair=repair;fm.salvage_prefix=salvage
   try:
    for budget in budgets:
     for repeat in range(repeats):
      for index,c in enumerate(data):
       events.clear()
       if backend:backend.calls.clear()
       ruled=apply_rules(apply_vocabulary(c['input']));start=time.perf_counter()
       actual=pipe.run(c['input'],budget_seconds=budget,allow_load=False,polish=False if model=='rules' else True if mode=='forced' else None)
       elapsed=time.perf_counter()-start
       r=dict(condition='forced-ai' if mode=='forced' else 'automatic',model=model,tier=tier,mode=mode,budget=budget,repeat=repeat,id=c['id'],base_id=c['base_id'],category=c['category'],variant=c['variant'],input=c['input'],expected=c['expected'],rules_output=ruled,output=actual,seconds=elapsed,needs_polish_after_rules=fm.needs_polish(ruled),cpu_skipped=bool(backend and mode=='shipped' and backend.runtime=='cpu' and len(ruled.split())>fm.CPU_MAX_WORDS),llm_calls=list(backend.calls) if backend else [],guard_events=list(events),guard_preserves=guard.preserves_words(ruled,actual))
       if mode=='forced' and not r['llm_calls']:raise RuntimeError('Forced mode failed to reach the backend: '+c['id'])
       r.update(format_metrics(c,actual,ruled));append_jsonl(out/'format.jsonl',r)
       if index%25==0:print(model,mode,'budget',budget,'repeat',repeat,'case',index+1,'/',len(data),flush=True)
   finally:fm.repair=repair_original;fm.salvage_prefix=salvage_original
  dump(out/'resources.json',dict(peak_process_rss_bytes=memory.peak_rss,peak_device_vram_bytes=memory.peak_vram,memory_scope='process RSS sampled 20ms; VRAM is total device use when NVML is available'))
 except Exception as e:dump(out/'FAILED.json',dict(error=str(e),traceback=traceback.format_exc()));raise
 print('Finished',out,flush=True);return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',default='rules',choices=['rules']+list(MODELS));p.add_argument('--tier',default='t3');p.add_argument('--mode',default='shipped',choices=['shipped','unlimited','forced']);p.add_argument('--budgets',nargs='+',type=float,default=[4,8,600]);p.add_argument('--repeats',type=int,default=2);p.add_argument('--full-set',action='store_true');p.add_argument('--limit',type=int,default=0);p.add_argument('--categories',nargs='+');p.add_argument('--threads',type=int,default=6);a=p.parse_args();run(a.model,a.tier,a.mode,a.budgets,a.repeats,a.limit,a.categories,a.threads,a.full_set)
