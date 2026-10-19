import argparse,time
from common import *
from backends.formatters import load
from flowstate.text.formatter import SmartFormatter
from flowstate.text.pipeline import CleanupPipeline,apply_rules
from flowstate.text.vocabulary import apply_vocabulary
from flowstate.text.guard import preserves_words

def run(model,tier,mode='shipped',threads=6):
 out=result_dir(tier,'robust-'+model+'-'+mode);fm=SmartFormatter();fm._backend=load(model,tier,mode,threads);pipe=CleanupPipeline(formatter=fm)
 base=next(c['input'] for c in cases() if c['category']=='window60');words=(base+' ')*18;items={'empty':'','1000_plus_words':words}
 for n in [59,60,61]:items[f'{n}_words']=' '.join(base.split()+['today']) if n==61 else ' '.join(base.split()[:n])
 for label,text in items.items():
  ruled=apply_rules(apply_vocabulary(text));start=time.perf_counter();actual=pipe.run(text,allow_load=False,budget_seconds=4);elapsed=time.perf_counter()-start
  append_jsonl(out/'robustness.jsonl',dict(model=model,tier=tier,mode=mode,label=label,input_words=len(text.split()),post_rules_words=len(ruled.split()),output=actual,seconds=elapsed,guard_preserves=preserves_words(ruled,actual)))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--tier',default='t3');p.add_argument('--mode',default='shipped');p.add_argument('--threads',type=int,default=6);a=p.parse_args();run(a.model,a.tier,a.mode,a.threads)
