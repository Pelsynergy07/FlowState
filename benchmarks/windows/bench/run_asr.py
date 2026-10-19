import argparse,json,time,csv,traceback
from common import *
from backends.asr import load,SPEECH
from metrics import NORMALIZE,punctuation_scores,distance
from flowstate.text.formatter import needs_polish
from flowstate.text.vocabulary import apply_vocabulary

def run(model,tier,manifest,threads=6,reuse=False):
 out=result_dir(tier,'asr-'+model);data=[json.loads(x) for x in pathlib.Path(manifest).read_text().splitlines()];start=time.perf_counter()
 cached={}
 if reuse:
  current=json.loads((out/'environment.json').read_text())
  for f in sorted((ROOT/'results'/out.parent.name).glob('*/asr.jsonl')):
   if f.parent==out:continue
   env=json.loads((f.parent/'environment.json').read_text())
   if env.get('source_sha256')!=current.get('source_sha256') or env.get('packages')!=current.get('packages'):continue
   for line in f.read_text().splitlines():
    try:r=json.loads(line)
    except json.JSONDecodeError:continue
    if r['model']==model and r['tier']==tier:cached[r['id']]=(r,str(f.relative_to(ROOT)))
 reused=0
 try:
  with MemorySampler() as mem:
   engine=load(model,tier,threads);load_s=time.perf_counter()-start
   dump(out/'backend.json',dict(model=model,backend=type(engine).__name__,metadata=getattr(engine,'metadata',{}),threads=threads,onnx_providers=getattr(engine,'providers',None),load_seconds=load_s))
   for c in data:
    if c['id'] in cached:
     saved,origin=cached[c['id']];saved=dict(saved,measurement_reused_from=origin);append_jsonl(out/'asr.jsonl',saved);reused+=1;continue
    path=ROOT/c['path'];start=time.perf_counter();w=engine.transcribe_words(path);seconds=time.perf_counter()-start;text=' '.join(x[2] for x in w)
    ref=c['reference'];a=NORMALIZE(ref).split();b=NORMALIZE(text).split()
    from jiwer import process_words
    edits=process_words(' '.join(a),' '.join(b))
    r=dict(backend_metadata=getattr(engine,'metadata',{}),model=model,tier=tier,id=c['id'],subset=c['subset'],reference=ref,output=text,words=w,decoding_method=getattr(engine,'last_method','runtime-default-whole-file'),seconds=seconds,duration=c['duration'],rtf=seconds/c['duration'] if c['duration'] else None,wer=distance(a,b),ref_words=len(a),substitutions=edits.substitutions,deletions=edits.deletions,insertions=edits.insertions,formatted_wer=distance(ref.split(),text.split()),needs_polish=needs_polish(text),load_seconds=load_s)
    r.update(punctuation_scores(ref,text) if c.get('punctuation_reference',True) else dict(punctuation_f1=None,punct_tp=None,punct_fp=None,punct_fn=None));r['punctuation_reference']=c.get('punctuation_reference',True)
    if not c.get('punctuation_reference',True):r['formatted_wer']=None
    if not a:r['wer']=None;r['formatted_wer']=None
    terms=c.get('terms',[]);r['terms_exact_before']=sum(t in text for t in terms);r['terms_exact_after']=sum(t in apply_vocabulary(text) for t in terms);r['terms_total']=len(terms)
    append_jsonl(out/'asr.jsonl',r);print(model,c['id'],'WER',r['wer'],flush=True)
  dump(out/'resources.json',dict(reused_accuracy_rows=reused,new_accuracy_rows=len(data)-reused,memory_scope='New runner process; reused rows retain original timings and their source resource files',peak_process_rss_bytes=mem.peak_rss,peak_process_tree_rss_bytes=mem.peak_tree_rss,peak_device_vram_bytes=mem.peak_vram))
 except Exception as e:dump(out/'FAILED.json',dict(error=str(e),traceback=traceback.format_exc()));raise
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',choices=list(SPEECH),required=True);p.add_argument('--tier',default='t3');p.add_argument('--manifest',default=str(ROOT/'data/audio_manifest.jsonl'));p.add_argument('--threads',type=int,default=6);p.add_argument('--reuse',action='store_true');a=p.parse_args();run(a.model,a.tier,a.manifest,a.threads,a.reuse)
