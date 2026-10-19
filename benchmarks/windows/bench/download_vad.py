import pathlib,json,os,hashlib
ROOT=pathlib.Path(__file__).resolve().parent;os.environ['HF_HOME']=str(ROOT/'.hf');os.environ['HF_HUB_ETAG_TIMEOUT']='60';os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='120'
os.environ.pop('HF_HUB_OFFLINE',None)
from huggingface_hub import hf_hub_download
repo='onnx-community/silero-vad';revision='e71cae966052b992a7eca6b17738916ce0eca4ec';folder=ROOT/'models/onnx-community--silero-vad'
p=pathlib.Path(hf_hub_download(repo,'onnx/model.onnx',revision=revision,local_dir=folder));(folder/'benchmark_download.json').write_text(json.dumps(dict(repo=repo,revision=revision,file='onnx/model.onnx',bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2));print('Pinned VAD ready')
