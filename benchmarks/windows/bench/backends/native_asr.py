import json,subprocess,pathlib,time,atexit
from common import ROOT
class NativeParakeet:
 def __init__(self,model,tier,threads=6):
  if tier!='t3':raise RuntimeError('CoreML native condition is Mac-only')
  version={'parakeet-coreml-v2':'v2','parakeet-coreml-v3':'v3','parakeet-coreml-v3-int4':'v3-int4','parakeet-coreml-v3-int8v2':'v3-int8v2','parakeet-coreml-redux':'redux'}[model]
  repo='parakeet-redux-coreml' if version=='redux' else 'parakeet-tdt-0.6b-v2-coreml' if version=='v2' else 'parakeet-tdt-0.6b-v3-coreml'
  binary=ROOT/'native/.build/release/NativeBench'
  if not binary.exists():raise RuntimeError('Native Mac adapter has not built successfully')
  self.log=(ROOT/(model+'-native-runtime.log')).open('a');self.proc=subprocess.Popen([str(binary),str(ROOT/'native-models'/repo),version],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
  atexit.register(self.close);self.metadata=self._read()
  if not self.metadata.get('ready'):raise RuntimeError('Native runtime did not report ready: '+str(self.metadata))
 def _read(self):
  while True:
   line=self.proc.stdout.readline()
   if not line:raise RuntimeError('Native runtime exited; see native-runtime.log')
   try:r=json.loads(line)
   except json.JSONDecodeError:continue
   if 'error' in r:raise RuntimeError(r['error'])
   return r
 def _transcribe(self,path):
  self.proc.stdin.write(json.dumps(dict(path=str(pathlib.Path(path).resolve())))+'\n');self.proc.stdin.flush();return self._read()
 def transcribe_words(self,path,context=None,prompt=True):
  r=self._transcribe(path);timings=r.get('tokenTimings') or [];words=[];text='';start=end=0.
  for t in timings:
   token=t['token']
   if token[:1].isspace() and text:
    words.append((start,end,text.strip()));text=''
   if not text:start=t['startTime']
   text+=token;end=t['endTime']
  if text.strip():words.append((start,end,text.strip()))
  if r.get('text','').strip() and not words:raise RuntimeError('Native model returned text without word timings; no invented timestamps supplied')
  return words
 def transcribe_segments(self,path):
  r=self._transcribe(path);return [(0.,r.get('duration',0.),r['text'])] if r.get('text','').strip() else []
 def close(self):
  if getattr(self,'proc',None) and self.proc.poll() is None:self.proc.terminate()
