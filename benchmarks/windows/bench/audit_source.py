"""Read-only source audit. Does not import Windows-only app modules."""
import ast,hashlib,json,os,pathlib,platform,subprocess,sys,datetime
ROOT=pathlib.Path(__file__).resolve().parent
os.environ['LOCALAPPDATA']=str(ROOT/'.appdata');sys.dont_write_bytecode=True
SRC=pathlib.Path(os.environ.get('FLOWSTATE_SRC',str(pathlib.Path.home()/'Desktop/AI builds/FlowState/src')))
sys.path.insert(0,str(SRC))
from flowstate import __version__
from flowstate.text import formatter,llm,pipeline,guard
files=['asr/engine.py','asr/models.py','streaming.py','text/formatter.py','text/llm.py','text/pipeline.py','text/guard.py','text/vocabulary.py','text/disfluency.py','text/dates.py','text/structure.py','paths.py']
constants={};hashes={}
for name in files:
 p=SRC/'flowstate'/name; hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 for node in ast.parse(p.read_text()).body:
  if isinstance(node,ast.Assign):
   for t in node.targets:
    if isinstance(t,ast.Name) and t.id.isupper():
     try:constants[name+':'+t.id]=ast.literal_eval(node.value)
     except (ValueError,TypeError):pass
out=ROOT/'results'/'source_audit';out.mkdir(parents=True,exist_ok=True)
example='hey john um number one milk number two eggs thanks sarah'
result={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'version':__version__,'commit':subprocess.check_output(['git','-C',str(SRC.parent),'rev-parse','HEAD'],text=True).strip(),'git_status':subprocess.check_output(['git','-C',str(SRC.parent),'status','--short'],text=True),'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'constants':constants,'source_sha256':hashes,'known_rules_case':{'input':example,'actual':pipeline.CleanupPipeline().run(example,polish=False,allow_load=False)},'guard_default_min_kept':guard.repair.__defaults__[0],'model_baselines':{'cuda':vars(llm.CUDA_MODEL),'cpu':vars(llm.CPU_MODEL)}}
(out/'audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=lambda x:sorted(x) if isinstance(x,set) else str(x))+'\n');print(json.dumps(result,indent=2,ensure_ascii=False,default=lambda x:sorted(x) if isinstance(x,set) else str(x)))
