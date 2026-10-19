"""Create an attributed, source-pinned benchmark adaptation; never import the app streaming/UI class."""
import ast,pathlib,textwrap
from common import ROOT,SRC
p=SRC/'flowstate/streaming.py';s=p.read_text();tree=ast.parse(s);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StreamingDictation')
header='''# Adapted from FlowState streaming.py (MIT). Source hash is recorded by environment.json.
# The benchmark replaces capture/thread scheduling, retains the full seam/gap/guard algorithm.
import logging,re,time,wave,threading
from pathlib import Path
import numpy as np
from flowstate.text.formatter import capitalize_start,join_sections,needs_polish
from flowstate.text.guard import preserves_words,repair
from flowstate.text.pipeline import apply_rules
from flowstate.text.vocabulary import apply_vocabulary
logger=logging.getLogger(__name__)
'''
parts=[header]
for n in tree.body:
 if isinstance(n,ast.Assign):
  if any(isinstance(t,ast.Name) and t.id in ['STEP_SECONDS','OVERLAP_SECONDS','LOOKAHEAD_SECONDS','LIVE_BUDGET_SECONDS','FINISH_BUDGET_SECONDS','STOP_GRACE_SECONDS','_SENTENCE_END'] for t in n.targets):parts.append(ast.get_source_segment(s,n))
 if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ['_mid','_has_speech','_StopDeadline']:parts.append(ast.get_source_segment(s,n))
parts.append('''class WindowProcessor:
    def __init__(self,engine,pipeline,folder):
        self._engine=engine;self._pipeline=pipeline;self._folder=folder
        self._stop=threading.Event();self._cursor=0.;self._segments=[];self._cleaned=[];self._words=[];self._pending=[];self._clean_cut=True
''')
for n in cls.body:
 if isinstance(n,ast.FunctionDef) and n.name in ['_window_begin','_process','_fill_skipped','_recover']:
  parts.append(textwrap.indent(ast.get_source_segment(s,n),'    '))
(ROOT/'streaming_core.py').write_text('\n\n'.join(parts)+'\n')
print('Adapted streaming processor generated from current source, retaining gap recovery and content guard')
