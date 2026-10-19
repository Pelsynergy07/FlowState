"""Local-only, read-only benchmark progress viewer. Bound to this Mac's loopback address."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import pathlib,json,datetime,collections
ROOT=pathlib.Path(__file__).resolve().parent
LABELS={'rules':'Built-in rules only','qwen15-q4':'Current formatter · Qwen 1.5B','qwen05-q4':'Smaller formatter · Qwen 0.5B (compact)','qwen05-q8':'Smaller formatter · Qwen 0.5B (higher precision)','qwen3-06-q8':'Newer formatter · Qwen3 0.6B','t5-tiny':'Tiny grammar model'}
CACHE={}
QUICK_IDS=set(json.loads((ROOT/'quick_profile.json').read_text())['audio_ids']) if (ROOT/'quick_profile.json').exists() else set()
def tail_progress(p):
 key=str(p);c=CACHE.setdefault(key,dict(offset=0,count=0,last=None,pending=b''))
 with p.open('rb') as f:
  f.seek(c['offset']);new=f.read();c['offset']=f.tell()
 if new:
  chunks=(c['pending']+new).split(b'\n');c['pending']=chunks.pop()
  c['count']+=len(chunks)
  if QUICK_IDS:
   for line in chunks:
    try:r=json.loads(line)
    except json.JSONDecodeError:continue
    if r.get('id') in QUICK_IDS:c.setdefault('selected_ids',set()).add(r['id'])
  if chunks:
   try:c['last']=json.loads(chunks[-1])
   except json.JSONDecodeError:pass
 return c['count'],c['last']
def status():
 runs=[];latest=None
 for p in sorted((ROOT/'results').glob('*/*/format.jsonl')):
  count,last=tail_progress(p)
  if last is None:continue
  done=(p.parent/'resources.json').exists();failed=(p.parent/'FAILED.json').exists();planned=300 if last['model']=='rules' else 1800
  config=p.parent/'run_manifest.json'
  if config.exists():planned=json.loads(config.read_text())['planned_cases']
  runs.append(dict(name=LABELS.get(last['model'],last['model']),model=last['model'],mode=last['mode'],tier=last['tier'],count=count,planned=planned,complete=done,failed=failed,last_category=last['category'],budget=last['budget'],repeat=last['repeat']+1,updated=p.stat().st_mtime))
  if latest is None or p.stat().st_mtime>latest['updated']:latest=dict(input=last['input'],output=last['output'],expected=last['expected'],model=LABELS.get(last['model'],last['model']),category=last['category'],seconds=last['seconds'],calls=len(last['llm_calls']),updated=p.stat().st_mtime)
 downloads=[]
 if (ROOT/'model_manifest.json').exists():
  for m in json.loads((ROOT/'model_manifest.json').read_text()):
   folder=ROOT/'models'/m['repo'].replace('/','--');size=sum((folder/f).stat().st_size for f in m['weight_files'] if (folder/f).exists())
   if size:downloads.append(dict(repo=m['repo'],bytes=size,total=m['weight_bytes'],complete=size==m['weight_bytes']))
 speeds=[]
 summary=ROOT/'results/speed_summary.csv'
 if summary.exists():
  import csv
  speeds=list(csv.DictReader(summary.open()))
 speech=[]
 for p in sorted((ROOT/'results').glob('*/*/asr.jsonl')):
  count,last=tail_progress(p)
  if last:speech.append(dict(model=last['model'],count=len(CACHE[str(p)].get('selected_ids',[])) if QUICK_IDS else count,planned=100 if QUICK_IDS else 1213,complete=(p.parent/'resources.json').exists(),failed=(p.parent/'FAILED.json').exists(),subset=last['subset']))
 speech=list({r['model']:r for r in speech}.values())
 judge=[]
 for p in sorted((ROOT/'results').glob('*/*/judge.jsonl')):
  count,last=tail_progress(p);judge.append(dict(count=count,complete=(p.parent/'FINISHED.json').exists()))
 return dict(speech=speech,judge=judge,speeds=speeds,updated=datetime.datetime.now().astimezone().isoformat(timespec='seconds'),machine='This Mac · Apple M2 Max · 32 GB',runs=runs,latest=latest,downloads=downloads,recordings='Your recordings: waiting for you',windows='Windows PC: runs still required',report_ready=(ROOT/'REPORT.md').exists())
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path.split('?')[0]=='/api/status':data=json.dumps(status(),ensure_ascii=False).encode();kind='application/json'
  elif self.path in ['/','/index.html']:data=(ROOT/'dashboard.html').read_bytes();kind='text/html; charset=utf-8'
  elif self.path=='/results-explained':data=(ROOT/'RESULTS_EXPLAINED.html').read_bytes();kind='text/html; charset=utf-8'
  elif self.path=='/HUMAN_REVIEW.csv':data=(ROOT/'HUMAN_REVIEW.csv').read_bytes();kind='text/csv; charset=utf-8'
  elif self.path in ['/REPORT.html','/report']:data=(ROOT/'REPORT.html').read_bytes();kind='text/html; charset=utf-8'
  elif self.path in ['/recording-sheet','/RECORDING_SHEET.html']:data=(ROOT/'data/RECORDING_SHEET.html').read_bytes();kind='text/html; charset=utf-8'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def log_message(self,*args):pass
if __name__=='__main__':
 print('FlowState benchmark progress: http://127.0.0.1:8765',flush=True);ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
