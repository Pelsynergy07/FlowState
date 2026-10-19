"""Check report structure that previously allowed misleading Markdown tables."""
from common import ROOT
import re,json
lines=(ROOT/'REPORT.md').read_text().splitlines();in_code=False;width=None;heading='';errors=[]
for number,line in enumerate(lines,1):
 if line.startswith('```'):in_code=not in_code;continue
 if in_code:continue
 if line.startswith('## '):heading=line
 if line.startswith('|'):
  count=len(line.strip('|').split('|'))
  if width is None:width=count
  elif count!=width:errors.append(dict(line=number,heading=heading,expected_columns=width,actual_columns=count))
  if 'RAM bytes' in line:assert heading=='## Environment'
 else:width=None
assert not errors,errors
assert '### Completed local automated review' not in '\n'.join(lines)
heads=[line for line in lines if line.startswith('### Example ')]
assert len(heads)>=20 and all('{i}' not in h and '{c[' not in h for h in heads)
print('Report verified: all Markdown table column counts match, environment rows under Environment, automated verdict table removed, named failure examples present.')
