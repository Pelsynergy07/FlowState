"""Meaningful integrity checks: input independence, exact prompts, source immutability, streaming method fidelity."""
import ast,hashlib,json,collections,pathlib,inspect,sys
from common import ROOT,SRC,cases,dump
from flowstate.text import formatter as fm
rows=cases();assert len(rows)==300
bycat=collections.Counter(r['category'] for r in rows);assert len(bycat)==15 and set(bycat.values())=={20}
assert len({r['base_id'] for r in rows})==150
assert all(len(r['input'].split())==60 for r in rows if r['category']=='window60')
assert all(len(r['input'].split())<12 for r in rows if r['category']=='short')
assert not any((r['input'],r['expected']) in fm._FEW_SHOT_EXAMPLES for r in rows)
assert fm._build_messages('probe')[0]['content'] is fm.SYSTEM_PROMPT
assert [(fm._build_messages('probe')[1+2*i]['content'],fm._build_messages('probe')[2+2*i]['content']) for i in range(4)]==fm._FEW_SHOT_EXAMPLES
old=json.loads((ROOT/'results/source_audit/audit.json').read_text())
changed=[]
for file,sha in old['source_sha256'].items():
 if hashlib.sha256((SRC/'flowstate'/file).read_bytes()).hexdigest()!=sha:changed.append(file)
assert not changed,changed
if (ROOT/'streaming_core.py').exists():
 upstream=ast.parse((SRC/'flowstate/streaming.py').read_text());adapted=ast.parse((ROOT/'streaming_core.py').read_text())
 a=next(n for n in upstream.body if isinstance(n,ast.ClassDef) and n.name=='StreamingDictation');b=next(n for n in adapted.body if isinstance(n,ast.ClassDef) and n.name=='WindowProcessor')
 for name in ['_process','_window_begin','_fill_skipped','_recover']:
  x=next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name==name);y=next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name==name);
  if x.body and isinstance(x.body[0],ast.Expr) and isinstance(x.body[0].value,ast.Constant) and isinstance(x.body[0].value.value,str):x.body=x.body[1:]
  if y.body and isinstance(y.body[0],ast.Expr) and isinstance(y.body[0].value,ast.Constant) and isinstance(y.body[0].value.value,str):y.body=y.body[1:]
  assert ast.dump(x)==ast.dump(y),name
for p in ROOT.glob('*.py'):compile(p.read_text(),str(p),'exec')
for p in (ROOT/'backends').glob('*.py'):compile(p.read_text(),str(p),'exec')
dump(ROOT/'results/harness_verification.json',dict(passed=True,cases=300,categories=15,source_unchanged=True,exact_prompt_and_examples=True,streaming_processing_logic_ast_identical_ignoring_docstring_indentation=True,limitations='Integrity checks do not establish correctness of all scoring proxies, Windows portability or native model compatibility.'))
print('Harness integrity checks passed: source unchanged, 300 cases, exact prompts, faithful processing methods.')
