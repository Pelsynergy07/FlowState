import pathlib,json,os,hashlib,time
ROOT=pathlib.Path(__file__).resolve().parent
os.environ['HF_HOME']=str(ROOT/'.hf');os.environ['HF_HUB_ETAG_TIMEOUT']='60';os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='120';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ.pop('HF_HUB_OFFLINE',None)
from huggingface_hub import hf_hub_download
manifest=[]
for version in ['v2','v3','redux']:
 repo=('FluidInference/parakeet-redux-coreml' if version=='redux' else f'FluidInference/parakeet-tdt-0.6b-{version}-coreml');meta=json.loads((ROOT/'research'/(repo.split('/')[-1]+'.json')).read_text());prefixes=['Encoder.mlmodelc/','Decoder.mlmodelc/','Preprocessor.mlmodelc/','JointDecision.mlmodelc/' if version=='v2' else 'JointDecisionv3.mlmodelc/']
 if version=='v3':prefixes+=['EncoderInt4.mlmodelc/','Encoder_v2.mlmodelc/']
 files=[f for f in meta['siblings'] if f['rfilename']=='parakeet_vocab.json' or any(f['rfilename'].startswith(p) for p in prefixes)]
 folder=ROOT/'native-models'/repo.split('/')[-1];records=[]
 for f in files:
  name=f['rfilename'];print('Downloading',version,name,flush=True);path=pathlib.Path(hf_hub_download(repo,name,revision=meta['sha'],local_dir=folder));h=hashlib.sha256(path.read_bytes()).hexdigest();records.append(dict(path=name,bytes=path.stat().st_size,sha256=h))
 entry=dict(repo=repo,revision=meta['sha'],files=records);manifest.append(entry);(folder/'benchmark_download.json').write_text(json.dumps(entry,indent=2))
(ROOT/'native_manifest.json').write_text(json.dumps(manifest,indent=2));print('Native Parakeet model downloads finished',flush=True)
