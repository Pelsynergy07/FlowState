import pathlib,subprocess,sys,argparse,venv,os
p=argparse.ArgumentParser();p.add_argument('--tier',required=True,choices=['t1','t2','t3','t4']);a=p.parse_args()
if sys.version_info[:2]!=(3,12):raise SystemExit('Please install and run Python 3.12.')
root=pathlib.Path(__file__).resolve().parent;target=root.parent/('.venv' if a.tier=='t3' else '.venv-'+a.tier)
if target.resolve()==pathlib.Path(sys.prefix).resolve():raise SystemExit('Run setup from Python 3.12 outside this environment.')
venv.EnvBuilder(with_pip=True).create(target);python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
default_src=root/'source_snapshot/src' if (root/'source_snapshot/src/flowstate/text/pipeline.py').exists() else pathlib.Path.home()/'Desktop/AI builds/FlowState/src'
src=pathlib.Path(os.environ.get('FLOWSTATE_SRC',str(default_src)))
if not (src/'flowstate/text/pipeline.py').exists():
 selected=pathlib.Path(input('Paste the path to your FlowState folder, then press Enter: ').strip().strip(chr(34)))
 src=selected/'src' if (selected/'src/flowstate').exists() else selected
 if not (src/'flowstate/text/pipeline.py').exists():raise SystemExit('FlowState src folder not found; setup stopped without changing the app.')
import json
(root/'machine.json').write_text(json.dumps(dict(flowstate_src=str(src.resolve())),indent=2))
req='requirements-gpu.txt' if a.tier=='t1' else 'requirements.txt'
subprocess.run([str(python),'-m','pip','install','-r',str(root/req)],check=True)
with (root/f'requirements-{a.tier}.lock.txt').open('w') as f:subprocess.run([str(python),'-m','pip','freeze'],stdout=f,check=True)
subprocess.run([str(python),'-m','pip','install','-r',str(root/'requirements-convert.txt')],check=True)
print('Benchmark setup finished. Run:',str(python),'run_all.py --tier',a.tier,'--stage all --download')
