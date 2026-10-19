import re,collections
from rapidfuzz.distance import Levenshtein
from whisper.normalizers import EnglishTextNormalizer
NORMALIZE=EnglishTextNormalizer()
def words(s):return re.findall(r"[^\W_]+(?:['’][^\W_]+)*",s.casefold())
def distance(a,b):return Levenshtein.distance(a,b)/max(1,len(a))
def punctuation(s):
 # Anchor marks to preceding word and occurrence; do not give a matching comma elsewhere credit.
 result=collections.Counter();counts=collections.Counter()
 for m in re.finditer(r"([^\W_]+(?:['’][^\W_]+)*)([.,?!]*)",s):
  w=m[1].casefold();counts[w]+=1
  for mark in m[2]:result[(w,counts[w],mark)]+=1
 return result
def punctuation_scores(expected,actual):
 a,b=punctuation(expected),punctuation(actual);tp=sum((a&b).values());fp=sum((b-a).values());fn=sum((a-b).values())
 return dict(punct_tp=tp,punct_fp=fp,punct_fn=fn,punctuation_f1=2*tp/max(1,2*tp+fp+fn))
def layout(s):
 lines=[x.strip() for x in s.splitlines() if x.strip()];markers=re.findall(r'(?m)^\s*(\d+\.|[-*•])\s+',s)
 return dict(items=len(markers),marker='numbered' if any(x[0].isdigit() for x in markers) else 'bullet' if markers else 'none',paragraphs=len(re.split(r'\n\s*\n',s.strip())) if s.strip() else 0,greeting=bool(lines and re.match(r'(?i)^(hi|hello|hey|dear)\b.*,$',lines[0])),closing=bool(len(lines)>=2 and re.match(r'(?i)^(thanks|regards|best)[,!]?$',lines[-2])),intro_colon=bool(markers and any(x.endswith(':') for x in lines)))
def format_metrics(case,actual,rule_source):
 expected=case['expected'];le,la=layout(expected),layout(actual)
 d=dict(char_error=distance(expected,actual),exact_whitespace=' '.join(expected.split())==' '.join(actual.split()),lexical_error_expected=distance(NORMALIZE(expected).split(),NORMALIZE(actual).split()),lexical_change_rules=distance(NORMALIZE(rule_source).split(),NORMALIZE(actual).split()),non_english_unchanged=actual==case['input'] if case['category']=='non_english' else None)
 if case['category']=='email':d['layout_ok']=all(la[k]==le[k] for k in ['greeting','closing','paragraphs'])
 elif case['category'] in ['numbered_list','implicit_list','bullet_list']:d['layout_ok']=all(la[k]==le[k] for k in ['items','marker','intro_colon'])
 elif case['category'] in ['long_prose','layout_commands']:d['layout_ok']=la['paragraphs']==le['paragraphs']
 else:d['layout_ok']=None
 d['char_error_whitespace_normalized']=distance(' '.join(expected.split()),' '.join(actual.split()))
 d.update(punctuation_scores(expected,actual));return d
