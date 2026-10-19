import pathlib,time,re
from common import ROOT
from flowstate.asr.engine import PUNCTUATION_PROMPT
SPEECH={
 'parakeet-coreml-v2':'FluidInference/parakeet-tdt-0.6b-v2-coreml',
 'parakeet-coreml-v3':'FluidInference/parakeet-tdt-0.6b-v3-coreml',
 'parakeet-coreml-v3-int4':'FluidInference/parakeet-tdt-0.6b-v3-coreml',
 'parakeet-coreml-v3-int8v2':'FluidInference/parakeet-tdt-0.6b-v3-coreml',
 'parakeet-coreml-redux':'FluidInference/parakeet-redux-coreml',
 'whisper-turbo':'deepdml/faster-whisper-large-v3-turbo-ct2',
 'whisper-base':'Systran/faster-whisper-base.en',
 'whisper-base-no-punctuation':'Systran/faster-whisper-base.en',
 'whisper-small':'Systran/faster-whisper-small.en',
 'whisper-distil':'Systran/faster-distil-whisper-large-v3',
 'parakeet-v2-int8':'istupakov/parakeet-tdt-0.6b-v2-onnx',
 'parakeet-v2-fp32':'istupakov/parakeet-tdt-0.6b-v2-onnx',
 'parakeet-v3-int8':'istupakov/parakeet-tdt-0.6b-v3-onnx',
 'parakeet-v3-fp32':'istupakov/parakeet-tdt-0.6b-v3-onnx'}
class Whisper:
 def __init__(self,model,tier,threads):
  from flowstate.cuda_support import ensure_cuda_dll_search_paths
  ensure_cuda_dll_search_paths()
  self.punctuation_prompt=not model.endswith('-no-punctuation')
  self.metadata=dict(punctuation_prompt_enabled=self.punctuation_prompt,decode='PCM16 WAV to float32; mono 16kHz',beam_size=5,condition_on_previous_text=False)
  from faster_whisper import WhisperModel
  self.model=WhisperModel(str(ROOT/'models'/SPEECH[model].replace('/','--')),device='cuda' if tier=='t1' else 'cpu',compute_type='float16' if tier=='t1' else 'int8',cpu_threads=threads,local_files_only=True)
 def _pcm(self,path):
  # Benchmark WAVs are already normalized PCM16 mono at 16kHz; decode directly.
  # Avoid the installed PyAV file-opening incompatibility without changing model settings.
  import soundfile as sf
  samples,rate=sf.read(str(path),dtype='float32')
  if rate!=16000 or samples.ndim!=1:raise ValueError('Whisper benchmark requires 16kHz mono audio')
  return samples
 def transcribe_words(self,path,context=None,prompt=True):
  kw=dict(initial_prompt=context) if prompt else {}
  if prompt and self.punctuation_prompt:kw['hotwords']=PUNCTUATION_PROMPT
  segments,_=self.model.transcribe(self._pcm(path),beam_size=5,word_timestamps=True,condition_on_previous_text=False,**kw)
  words=[]
  for s in segments:
   if s.text.strip() and not s.words:raise RuntimeError('Missing word timings')
   words.extend((w.start,w.end,w.word.strip()) for w in s.words or [] if w.word.strip())
  return words
 def transcribe_segments(self,path):
  segments,_=self.model.transcribe(self._pcm(path),beam_size=5,condition_on_previous_text=False,**({'hotwords':PUNCTUATION_PROMPT} if self.punctuation_prompt else {}))
  return [(s.start,s.end,s.text.strip()) for s in segments if s.text.strip()]
class Parakeet:
 def __init__(self,model,tier,threads):
  import onnx_asr,onnxruntime as ort
  options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
  providers=['CUDAExecutionProvider','CPUExecutionProvider'] if tier=='t1' else ['CPUExecutionProvider']
  if tier=='t1' and 'CUDAExecutionProvider' not in ort.get_available_providers():raise RuntimeError('CUDA ONNX provider unavailable; CPU fallback is not a GPU result')
  self.options=options;self.providers=providers;self.vad_model=None
  self.metadata=dict(adapter_revision='onnx-word-boundary-v2',word_starts='space or SentencePiece boundary; library replaces SentencePiece with space',word_ends='last token start + 80ms bounded by next word start; estimated, not forced alignment')
  self.model=onnx_asr.load_model('nemo-conformer-tdt',path=ROOT/'models'/SPEECH[model].replace('/','--'),quantization='int8' if model.endswith('int8') else None,sess_options=options,providers=providers).with_timestamps()
  sessions={name:getattr(self.model.asr,name) for name in ['_encoder','_decoder_joint']}
  active={name:session.get_providers() for name,session in sessions.items()}
  self.metadata['active_onnx_session_providers']=active
  self.metadata['operator_placement_limitation']='Active CUDA session does not prove every operator runs on GPU; mixed operator placement is not profiled.'
  if tier=='t1' and any('CUDAExecutionProvider' not in providers for providers in active.values()):raise RuntimeError('An ONNX session fell back to CPU; refusing to label this as a CUDA run')
 def transcribe_words(self,path,context=None,prompt=True):
  import soundfile as sf
  self.last_method='whole-utterance'
  if sf.info(str(path)).duration>30:
   import onnx_asr
   if self.vad_model is None:
    vad=onnx_asr.load_vad('silero',path=ROOT/'models/onnx-community--silero-vad',sess_options=self.options,providers=['CPUExecutionProvider'])
    self.vad_model=onnx_asr.adapters.TextResultsAsrAdapter(self.model.asr,self.model.resampler).with_vad(vad,max_speech_duration_s=20,batch_size=1).with_timestamps()
   self.last_method='recommended-VAD-20s-segments'
   result=[]
   for segment in self.vad_model.recognize(str(path)):
    result.extend((a+segment.start,b+segment.start,w) for a,b,w in self._words(segment))
   self.last_words=result;self.last_path=str(path);return result
  r=self.model.recognize(str(path))
  self.last_words=self._words(r);self.last_path=str(path);return self.last_words
 def _words(self,r):
  if r.timestamps is None or r.tokens is None:raise RuntimeError('Parakeet returned no token timings')
  # SentencePiece starts are model timestamps; end estimates use one 80ms frame,
  # report pause/seam comparisons as limited until validated against manual word alignments.
  words=[];current='';start=0.;last=0.
  for token,t in zip(r.tokens,r.timestamps):
   if (token.startswith('▁') or token[:1].isspace()) and current:
    words.append((start,min(float(t),last+.08),current));current=''
   if not current:start=float(t)
   current+=token.replace('▁',' ');last=float(t)
  if current:words.append((start,last+.08,current))
  return [(a,b,w.strip()) for a,b,w in words if w.strip()]
 def transcribe_segments(self,path):
  w=self.transcribe_words(path);return [(w[0][0],w[-1][1],' '.join(x[2] for x in w))] if w else []
def load(model,tier,threads=6):
 if model.startswith('parakeet-coreml-'):
  from backends.native_asr import NativeParakeet
  return NativeParakeet(model,tier,threads)
 return (Whisper if model.startswith('whisper-') else Parakeet)(model,tier,threads)
