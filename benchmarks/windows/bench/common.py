import os,sys,pathlib,json,platform,subprocess,datetime,hashlib,importlib.metadata,time,threading
ROOT=pathlib.Path(__file__).resolve().parent
sys.dont_write_bytecode=True
os.environ['LOCALAPPDATA']=str(ROOT/'.appdata');os.environ['HF_HOME']=str(ROOT/'.hf');os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['HF_HUB_OFFLINE']='1'
local=json.loads((ROOT/'machine.json').read_text()) if (ROOT/'machine.json').exists() else {}
DEFAULT_SRC=ROOT/'source_snapshot/src' if (ROOT/'source_snapshot/src/flowstate/text/pipeline.py').exists() else pathlib.Path.home()/'Desktop/AI builds/FlowState/src'
SRC=pathlib.Path(os.environ.get('FLOWSTATE_SRC',local.get('flowstate_src',str(DEFAULT_SRC))))
if sys.version_info[:2]!=(3,12):raise RuntimeError('Use the separate Python 3.12 benchmark environment.')
sys.path.insert(0,str(SRC))
def dump(path,obj):path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str)+'\n')
def command(args):
 try:return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT,timeout=20).strip()
 except Exception as e:return str(e)
def environment(tier):
 import psutil
 from flowstate import __version__
 d=dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),tier=tier,os=platform.platform(),cpu=platform.processor(),machine=platform.machine(),python=sys.version,flowstate_version=__version__,source_commit=command(['git','-C',str(SRC.parent),'rev-parse','HEAD']),source_status=command(['git','-C',str(SRC.parent),'status','--short']),ram_bytes=psutil.virtual_memory().total,cpu_logical=psutil.cpu_count(),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()},gpu=command(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader']),cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'))
 if sys.platform=='darwin':d['apple_hardware']=command(['sysctl','-n','machdep.cpu.brand_string']);d['gpu_metal']=command(['system_profiler','SPDisplaysDataType'])
 d['source_sha256']={p.relative_to(SRC).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (SRC/'flowstate').rglob('*.py')}
 d['source_resource_sha256']={name:hashlib.sha256((SRC/name).read_bytes()).hexdigest() for name in ['flowstate/resources/vocabulary_default.json'] if (SRC/name).exists()}
 snapshot=SRC.parent/'SNAPSHOT.json'
 if snapshot.exists():
  pinned=json.loads(snapshot.read_text())
  if d['source_resource_sha256']!=pinned.get('resource_sha256',{}):raise RuntimeError('Bundled vocabulary resource changed or is missing')
  if d['source_sha256']!=pinned['source_sha256']:raise RuntimeError('Bundled source snapshot changed; restore the original snapshot before comparing devices.')
  d['source_commit']=pinned['commit'];d['source_status']='Pinned source snapshot verified unchanged';d['source_kind']='read-only bundled snapshot'
 return d
def result_dir(tier,name):
 p=ROOT/'results'/platform.node().split('.')[0]/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+name);p.mkdir(parents=True);dump(p/'environment.json',environment(tier));return p
class MemorySampler:
 def __enter__(self):
  import psutil
  self.proc=psutil.Process();self.peak_rss=0;self.peak_tree_rss=0;self.peak_vram=None;self.done=threading.Event()
  try:
   import pynvml
   pynvml.nvmlInit();self.nvml=pynvml;self.handle=pynvml.nvmlDeviceGetHandleByIndex(0)
  except Exception:self.nvml=None
  def loop():
   while not self.done.is_set():
    try:
     rss=self.proc.memory_info().rss
     self.peak_rss=max(self.peak_rss,rss)
     child_rss=0
     for child in self.proc.children(recursive=True):
      try:child_rss+=child.memory_info().rss
      except Exception:pass
     self.peak_tree_rss=max(self.peak_tree_rss,rss+child_rss)
     if self.nvml:self.peak_vram=max(self.peak_vram or 0,self.nvml.nvmlDeviceGetMemoryInfo(self.handle).used)
    except Exception:pass
    self.done.wait(.02)
  self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
 def __exit__(self,*args):self.done.set();self.thread.join()
def append_jsonl(path,row):
 with pathlib.Path(path).open('a',encoding='utf8') as f:f.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')
def cases(full=False):
 rows=[json.loads(x) for x in (ROOT/'data/format_cases.jsonl').read_text().splitlines()]
 if not full and (ROOT/'quick_profile.json').exists():
  ids=set(json.loads((ROOT/'quick_profile.json').read_text())['format_ids']);rows=[r for r in rows if r['id'] in ids]
 return rows
