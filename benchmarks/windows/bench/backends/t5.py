"""Greedy ONNX T5 adapter. Decoder self-attention cache only; encoder projections are recomputed by exported graph."""
import numpy as np,onnxruntime as ort,tokenizers,json
from common import ROOT
class T5:
 runtime='cpu'
 def __init__(self,threads=6):
  folder=ROOT/'models/rabden--t5-tiny-gec-hone';options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
  self.tokenizer=tokenizers.Tokenizer.from_file(str(folder/'tokenizer.json'))
  self.encoder=ort.InferenceSession(str(folder/'onnx/encoder_model_quantized.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
  self.decoder=ort.InferenceSession(str(folder/'onnx/decoder_model_merged_quantized.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
  cfg=json.loads((folder/'config.json').read_text());self.start=cfg.get('decoder_start_token_id',0);self.eos=cfg.get('eos_token_id',1)
 def count_tokens(self,text):return len(self.tokenizer.encode(text,add_special_tokens=False).ids)
 def stream(self,messages,max_tokens):
  ids=np.array([self.tokenizer.encode(messages[-1]['content']).ids],np.int64);mask=np.ones_like(ids);hidden=self.encoder.run(None,{'input_ids':ids,'attention_mask':mask})[0]
  cache={i.name:np.zeros((1,4,0,64),np.float32) for i in self.decoder.get_inputs() if i.name.startswith('past_key_values')}
  generated=[];token=self.start;emitted=''
  for _ in range(max_tokens):
   inputs=dict(input_ids=np.array([[token]],np.int64),encoder_hidden_states=hidden,encoder_attention_mask=mask,**cache)
   outputs=dict(zip([x.name for x in self.decoder.get_outputs()],self.decoder.run(None,inputs)))
   token=int(outputs['logits'][0,-1].argmax())
   if token==self.eos:break
   generated.append(token)
   for name in cache:cache[name]=outputs[name.replace('past_key_values.','present.')]
   text=self.tokenizer.decode(generated,skip_special_tokens=True)
   if not text.endswith('�'):yield text[len(emitted):];emitted=text
