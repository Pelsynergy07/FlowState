import time,pathlib,json
from common import ROOT
from flowstate.text import llm
MODELS={
 't5-tiny':('rabden/t5-tiny-gec-hone',None),
 'qwen15-q4':('Qwen/Qwen2.5-1.5B-Instruct-GGUF','qwen2.5-1.5b-instruct-q4_k_m.gguf'),
 'qwen05-q4':('Qwen/Qwen2.5-0.5B-Instruct-GGUF','qwen2.5-0.5b-instruct-q4_k_m.gguf'),
 'qwen05-q8':('Qwen/Qwen2.5-0.5B-Instruct-GGUF','qwen2.5-0.5b-instruct-q8_0.gguf'),
 'qwen3-06-q8':('Qwen/Qwen3-0.6B-GGUF','Qwen3-0.6B-Q8_0.gguf'),
 'qwen3-17-q8':('Qwen/Qwen3-1.7B-GGUF','Qwen3-1.7B-Q8_0.gguf'),
 'qwen25-3-q4':('Qwen/Qwen2.5-3B-Instruct-GGUF','qwen2.5-3b-instruct-q4_k_m.gguf'),
 'qwen15-ct2':('jncraton/Qwen2.5-1.5B-Instruct-ct2-int8',None),
 'qwen05-ct2':('Qwen/Qwen2.5-0.5B-Instruct',None),
 'qwen25-3-ct2':('Qwen/Qwen2.5-3B-Instruct',None)}
class Ct2CPU(llm.Ct2Backend):
 runtime='cpu'
 def __init__(self,folder,threads=6):
  import ctranslate2,tokenizers
  self._tokenizer=tokenizers.Tokenizer.from_file(str(folder/'tokenizer.json'));self._generator=ctranslate2.Generator(str(folder),device='cpu',compute_type='int8',inter_threads=1,intra_threads=threads)
class NativeQwen3(llm.LlamaCppBackend):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  from jinja2.sandbox import ImmutableSandboxedEnvironment
  template=self._llm.metadata.get('tokenizer.chat_template')
  if not template:raise RuntimeError('Missing model-native Qwen3 chat template')
  self.template=ImmutableSandboxedEnvironment().from_string(template)
 def stream(self,messages,max_tokens):
  # Render model's embedded template with hard thinking-off; do not alter instruction/few-shot strings.
  prompt=self.template.render(messages=messages,add_generation_prompt=True,enable_thinking=False,tools=None,bos_token='',eos_token='<|im_end|>')
  if '<think>' not in prompt or '</think>' not in prompt:raise RuntimeError('Qwen3 template did not emit the thinking-disabled assistant prefix')
  events=self._llm.create_completion(prompt=prompt,max_tokens=max_tokens,temperature=0.0,stream=True,stop=['<|im_end|>','<|endoftext|>'])
  try:
   for event in events:
    text=event['choices'][0].get('text','')
    if text:yield text
  finally:events.close()
class TracedBackend:
 def __init__(self,backend,mode):self.inner=backend;self.runtime='cuda' if mode=='unlimited' else backend.runtime;self.calls=[]
 def count_tokens(self,text):return self.inner.count_tokens(text)
 def stream(self,messages,max_tokens):
  record=dict(source=messages[-1]['content'],raw='',pieces=0,max_tokens=max_tokens,completed=False,started=time.perf_counter());self.calls.append(record)
  stream=self.inner.stream(messages,max_tokens)
  try:
   for piece in stream:record['raw']+=piece;record['pieces']+=1;yield piece
   record['completed']=True
  except Exception as e:
   record['error']=repr(e);raise
  finally:
   stream.close();record['seconds']=time.perf_counter()-record.pop('started');record['output_tokens']=self.count_tokens(record['raw'])
def load(model,tier='t3',mode='shipped',threads=6,metal=False):
 if model=='rules':return None
 if model=='t5-tiny':
  from backends.t5 import T5
  return TracedBackend(T5(threads),mode)
 repo,file=MODELS[model];folder=ROOT/'models'/repo.replace('/','--')
 if file:
  backend=(NativeQwen3 if model.startswith('qwen3-') else llm.LlamaCppBackend)(folder/file,n_threads=threads)
  if metal:raise RuntimeError('Metal is not enabled in the CPU baseline build; use a separately labelled build.')
 else:
  if model in ['qwen05-ct2','qwen25-3-ct2']:folder=ROOT/'models'/(model+'-converted')
  backend=llm.Ct2Backend(folder) if tier=='t1' else Ct2CPU(folder,threads)
 return TracedBackend(backend,mode)
