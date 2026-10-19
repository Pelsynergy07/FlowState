"""Build an evidence-only report. Incomplete runs and missing measurements remain explicit."""
import pathlib,json,collections,statistics,csv,re,datetime,html,random,hashlib
import numpy as np
from zoneinfo import ZoneInfo
from common import ROOT,dump
from metrics import format_metrics
from rapidfuzz.distance import Levenshtein

def load_jsonl(path):
 rows=[]
 for line in path.read_text().splitlines():
  try:rows.append(json.loads(line))
  except json.JSONDecodeError:pass
 return rows

def csv_write(path,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)

def mean_ci(rows,key):
 clusters=collections.defaultdict(list)
 for r in rows:
  v=r.get(key)
  if v is not None:clusters[r['base_id']].append(float(v))
 if not clusters:return None
 a=np.array([np.mean(v) for v in clusters.values()]);rng=np.random.default_rng(1729)
 samples=np.mean(rng.choice(a,size=(2000,len(a)),replace=True),axis=1)
 return float(np.mean(a)),*map(float,np.quantile(samples,[.025,.975]))
def fmt_ci(t,percent=False):
 if t is None:return 'Not measured'
 factor=100 if percent else 1
 digits=1 if percent else 3
 return f'{t[0]*factor:.{digits}f} [{t[1]*factor:.{digits}f}, {t[2]*factor:.{digits}f}]'
def caps(ref,out):
 from difflib import SequenceMatcher
 pattern=r"[^\W_]+(?:['’][^\W_]+)*";a=list(re.finditer(pattern,ref));b=list(re.finditer(pattern,out));align={}
 for block in SequenceMatcher(None,[x[0].casefold() for x in a],[x[0].casefold() for x in b],autojunk=False).get_matching_blocks():
  for k in range(block.size):align[block.a+k]=block.b+k
 st=sp=pt=pp=0
 for i,x in enumerate(a):
  before=ref[:x.start()];sentence=(not before.strip() or bool(re.search(r'[.!?]\s*$|\n\s*(?:[-*•]|\d+\.)?\s*$',before)))
  if sentence and x[0][:1].isupper():st+=1;sp+=int(i in align and b[align[i]][0][:1].isupper())
  if not sentence and any(c.isupper() for c in x[0]):pt+=1;pp+=int(i in align and b[align[i]][0]==x[0])
 return dict(sentence_caps=sp/st if st else None,proper_caps=pp/pt if pt else None)

def main():
 quick=json.loads((ROOT/'quick_profile.json').read_text()) if (ROOT/'quick_profile.json').exists() else None
 report=['# FlowState benchmark — interim evidence report','', 'This report updates from saved local runs. It is not a completed replacement decision. Every result below comes from a recorded run; unavailable tests are labelled.','', '## Recommendation in plain language','', '- Keep the current defaults until the owner’s recordings, Windows results and blind review are available.','- Results belong to their recorded machine and runtime; Mac CPU results do not substitute for RTX 2070 timings.','- Smaller downloads alone do not qualify a model for replacement.','- The Apple-native Parakeet path is separate from portable CPU and Windows GPU paths.','- No 4 GB GPU or Android performance claim is possible without running those devices.','', 'Generated '+datetime.datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y, %I:%M %p IST')+'.','', '## What was checked and how','', 'The benchmark imports FlowState’s text modules read-only and sets LOCALAPPDATA to its own .appdata before importing. It never calls preload, and never imports hotkeys, paste, UI or capture modules. The app repository and app environment remain separate. Model files are downloaded by full Hugging Face commit hash, with SHA256 and byte counts in each benchmark_download.json. Package versions and source hashes are stored beside each result.','', 'The local app is 1.0.7-beta at commit 6c465c16b67910f5fc449c2dcf86ed426183c80c; the brief described 1.0.4-beta. The verified constants match the brief. Additional behavior matters: needs_polish runs after vocabulary/rules; the CPU 60-word skip happens before chunking; _keep_edges can preserve lowercase starts and missing terminal punctuation for fragments; streaming includes prompt-free gap recovery, conditional overlap and a final content guard. The source audit records these settings and the original prompt/examples.','', 'The full D3 pool has 150 authored cases, ten in each of fifteen categories, with two input variants (300 rows). The temporary 100-row formatting filter has been removed: all 300 rows are reported, following the second review. Both variants of one authored case form one bootstrap cluster. Expected outputs were authored independently of model output. Twenty references have an author spot-check and ambiguity notes in data/EXPECTED_REVIEW.md; they still need independent human validation. Four exact source few-shot pairs are saved separately and excluded from scored results. Default developer vocabulary is used; no personal vocabulary or recordings have been imported.','', 'Each formatter runs through the real CleanupPipeline. Shipped CPU mode keeps its 60-word skip. Unlimited mode labels the backend runtime as cuda only to lift that branch; it still physically runs on the Mac CPU. The original automatic shortlist uses 4, 8 and 600-second conditions with two passes for repeatability. Added CT2 and forced-AI comparisons use one 600-second quality pass, plus separate dedicated speed checks; no repeatability or deadline-quality claim is made for those added conditions. Three warm-up calls precede scoring. Guard wrappers patch the formatter’s imported aliases, so repair and salvage events are captured without editing FlowState. Tiny T5 receives source text directly because it is not an instruction model; layout is outside its capability.','', 'Character distance and exact match are descriptive, since multiple punctuation/layout choices can be valid. Layout checks are structural proxies (email lines, list counts/markers, paragraph counts), not a validated semantic layout judge. Punctuation is anchored to word occurrence rather than matching global counts. Capitalization uses aligned reference words; proper nouns are approximated by non-initial capitalization. Lexical-change metrics normalize number forms; the FlowState guard is a separate check, not an independent proof of content preservation. Full filler precision/recall, paragraph-boundary distance and answered-instead classification require additional annotation/review and are not claimed.','', 'Confidence intervals use 2,000 bootstrap resamples with seed 1729; formatting clusters variants and repeats by authored base case. No significance or equivalence is inferred merely from a similar average. Only completed formatter runs are summarized below.','', ]
 envs={};format_rows=[];speed_rows=[];asr_rows=[];stream_rows=[];incomplete=[]
 for p in sorted((ROOT/'results').glob('*/*/environment.json')):
  e=json.loads(p.read_text());envs[(p.parent.parent.name,e['tier'])]=e
  f=p.parent/'format.jsonl'
  if f.exists():
   if not (p.parent/'resources.json').exists():incomplete.append((p.parent.name,len(load_jsonl(f))));continue
   for r in load_jsonl(f):
    r['machine']=p.parent.parent.name;r.update(format_metrics(r,r['output'],r['rules_output']));r.update(caps(r['expected'],r['output']));format_rows.append(r)
  for name,target in [('speed.jsonl',speed_rows),('asr.jsonl',asr_rows),('streaming.jsonl',stream_rows)]:
   if (p.parent/name).exists():
    if name in ['asr.jsonl','speed.jsonl'] and not (p.parent/'resources.json').exists():continue
    if name=='streaming.jsonl' and not (p.parent/'FINISHED.json').exists():continue
    for r in load_jsonl(p.parent/name):r['machine']=p.parent.parent.name;target.append(r)
 if quick:
  asr_rows=[r for r in asr_rows if r['id'] in set(quick['audio_ids'])]
  stream_rows=[r for r in stream_rows if r['id'] in set(quick['audio_ids'])]
  report+=['','## Owner-requested quick decision screen','', 'The owner requested practical insight sooner, replacing the comprehensive sweep. Speech tables use 100 audio examples; the full 300-row formatting set has been restored following the second review. The audio sample contains: 42 clean, 40 difficult, 12 noisy, three silence clips and three long recordings. Seed 1729 and exact IDs are recorded in quick_profile.json. Previously collected results are reused on those identical IDs; no result is invented and full raw runs are retained. Intervals are wider with this smaller sample. This is directional evidence, not a comprehensive certification. Portable fp32 speech conditions, 30-trial repeats and exhaustive streaming combinations remain deferred. The second review adds the missing turbo streaming baseline, CT2 formatter references, forced-AI diagnostics and a no-punctuation-prompt control. The dedicated speed checks retain at least ten timed calls.','']
 report+=['','## Environment','', '| Machine | Tier | OS | CPU | RAM bytes | Python |','|---|---|---|---|---:|---|']
 for (machine,tier),e in envs.items():report.append(f"| {machine} | {tier} | {e['os']} | {e.get('apple_hardware') or e['cpu']} | {e['ram_bytes']} | {e['python'].split()[0]} |")
 report+=['','Windows/RTX, driver, VRAM and low-end laptop results: not measured on this Mac. GPU resource fields remain unavailable where NVML is absent. Apple memory is unified; process RSS is not a discrete VRAM measurement.','', '## Formatting accuracy','', 'Intervals are 95% bootstrap intervals. Rates are percentages. Guard rejection uses repair calls as denominator; bypassed calls are not counted as accepted model outputs.','', '| Machine / tier | Model | CPU mode | Budget s | Rows | Exact match % [CI] | Layout proxy % [CI] | Character error [CI] | Repair calls | Rejected % |','|---|---|---|---:|---:|---|---|---|---:|---:|']
 groups=collections.defaultdict(list)
 for r in format_rows:groups[(r['machine'],r['tier'],r['model'],r['mode'],r['budget'])].append(r)
 summary=[]
 for key,rows in sorted(groups.items()):
  machine,tier,model,mode,budget=key;events=[e for r in rows for e in r['guard_events'] if e['kind']=='repair'];rejected=sum(e['outcome']=='rejected' for e in events);rate=100*rejected/len(events) if events else None
  report.append(f"| {machine} / {tier} | {model} | {mode} | {budget:g} | {len(rows)} | {fmt_ci(mean_ci(rows,'exact_whitespace'),True)} | {fmt_ci(mean_ci(rows,'layout_ok'),True)} | {fmt_ci(mean_ci(rows,'char_error'))} | {len(events)} | {f'{rate:.1f}' if rate is not None else 'N/A'} |")
  summary.append(dict(machine=machine,tier=tier,model=model,mode=mode,budget=budget,rows=len(rows),exact_match=float(np.mean([r['exact_whitespace'] for r in rows])),character_error=float(np.mean([r['char_error'] for r in rows])),layout_proxy=float(np.mean([r['layout_ok'] for r in rows if r['layout_ok'] is not None])) if any(r['layout_ok'] is not None for r in rows) else None,repair_calls=len(events),rejected_calls=rejected,rejected_fraction=rejected/len(events) if events else None,accepted_calls=sum(e['outcome']=='accepted' for e in events),repaired_calls=sum(e['outcome']=='repaired' for e in events),salvage_attempts=sum(e['kind']=='salvage' for r in rows for e in r['guard_events']),salvage_successes=sum(e['outcome']=='salvaged' for r in rows for e in r['guard_events'] if e['kind']=='salvage'),llm_case_fraction=np.mean([bool(r['llm_calls']) for r in rows]),sentence_caps=fmt_ci(mean_ci(rows,'sentence_caps'),True),proper_caps=fmt_ci(mean_ci(rows,'proper_caps'),True),lexical_change_rules=fmt_ci(mean_ci(rows,'lexical_change_rules')),guard_preserves_fraction=np.mean([r['guard_preserves'] for r in rows])))
  csv_write(ROOT/'results'/('cases-'+model+'-'+mode+'-'+str(budget)+'.csv'),[{k:v for k,v in r.items() if k not in ['guard_events','llm_calls']} for r in rows])
 csv_write(ROOT/'results/format_summary.csv',summary)
 if not format_rows:report+=['','No formatter run has completed.']
 if incomplete:report+=['','Incomplete runs excluded from accuracy summaries: '+', '.join(f'{x} ({n} rows saved)' for x,n in incomplete)+'.']
 report+=['','## Formatting results by category','', 'Generous 600-second condition; first pass only. Each category has 20 inputs in the full set. Automatic and forced modes are kept separate. AI call counts expose bypasses; output scores are after the content guard.','', '| Model | Mode | Category | Cases | AI invoked | Exact match % [CI] | Layout % [CI] | Spacing-normalized character error [CI] |','|---|---|---|---:|---:|---|---|---|']
 categorygroups=collections.defaultdict(list)
 for r in format_rows:
  if r['budget']==600 and r['repeat']==0:categorygroups[(r['machine'],r['tier'],r['model'],r['mode'],r['category'])].append(r)
 category_summary=[]
 for key,rows in sorted(categorygroups.items()):
  machine,tier,model,mode,category=key
  report.append(f"| {model} | {mode} | {category} | {len(rows)} | {sum(bool(r['llm_calls']) for r in rows)} | {fmt_ci(mean_ci(rows,'exact_whitespace'),True)} | {fmt_ci(mean_ci(rows,'layout_ok'),True)} | {fmt_ci(mean_ci(rows,'char_error_whitespace_normalized'))} |")
  category_summary.append(dict(machine=machine,tier=tier,model=model,mode=mode,category=category,cases=len(rows),ai_invoked=sum(bool(r['llm_calls']) for r in rows),exact=fmt_ci(mean_ci(rows,'exact_whitespace'),True),layout=fmt_ci(mean_ci(rows,'layout_ok'),True),character_error_normalized=fmt_ci(mean_ci(rows,'char_error_whitespace_normalized'))))
 csv_write(ROOT/'results/format_by_category.csv',category_summary)
 # Compare the AI on cases where it actually ran; bypasses are not AI-quality successes.
 report+=['','## AI-only quality: bypassed cases excluded','', 'The all-case table describes the app pipeline. This table isolates cases with at least one recorded model call. It uses the generous 600-second condition and the first pass only, so repeats do not inflate the sample. A call can still be rejected by the content guard; final output after that guard is scored. The next paired table uses only inputs on which BOTH baseline and candidate invoked the model.','', '| Model | Mode | All cases | AI invoked | Bypassed | Exact match % [CI] | Layout proxy % [CI] | Spacing-normalized character error [CI] |','|---|---|---:|---:|---:|---|---|---|']
 active_summary=[]
 for key,rows in sorted(groups.items()):
  machine,tier,model,mode,budget=key
  if budget!=600 or model=='rules':continue
  first=[r for r in rows if r['repeat']==0];active=[r for r in first if r['llm_calls']]
  report.append(f"| {model} | {mode} | {len(first)} | {len(active)} | {len(first)-len(active)} | {fmt_ci(mean_ci(active,'exact_whitespace'),True)} | {fmt_ci(mean_ci(active,'layout_ok'),True)} | {fmt_ci(mean_ci(active,'char_error_whitespace_normalized'))} |")
  active_summary.append(dict(machine=machine,tier=tier,model=model,mode=mode,all_cases=len(first),invoked=len(active),bypassed=len(first)-len(active),exact=fmt_ci(mean_ci(active,'exact_whitespace'),True),layout=fmt_ci(mean_ci(active,'layout_ok'),True),char_error_normalized=fmt_ci(mean_ci(active,'char_error_whitespace_normalized'))))
 csv_write(ROOT/'results/format_invoked_only.csv',active_summary)
 report+=['','### Paired inputs where both models ran','', 'Each candidate is compared on identical input IDs, machine and mode. The 3B CT2 reference uses the 1.5B CT2 baseline; other candidates use the 1.5B GGUF baseline. The baseline is named in each row. Rates below describe final guarded output. Forced mode is reported separately: it explicitly enables polishing and lifts the CPU length skip while retaining the same prompt, chunks, content guard and final rules. It is a diagnostic, not shipped behavior.','', '| Candidate | Baseline | Mode | Matched invoked cases | Baseline layout % [CI] | Candidate layout % [CI] | Paired layout change, points [CI] |','|---|---|---|---:|---|---|---|']
 firstmap={(r['machine'],r['tier'],r['model'],r['mode'],r['id']):r for r in format_rows if r['budget']==600 and r['repeat']==0}
 paired_summary=[]
 for g,rows in sorted(groups.items()):
  machine,tier,model,mode,budget=g
  if budget!=600 or model in ['rules','qwen15-q4']:continue
  baseline_model='qwen15-ct2' if model=='qwen25-3-ct2' else 'qwen15-q4'
  pairs=[]
  for c in rows:
   if c['repeat']!=0 or not c['llm_calls']:continue
   b=firstmap.get((machine,tier,baseline_model,mode,c['id']))
   if b and b['llm_calls']:pairs.append((b,c))
  base=[b for b,c in pairs];candidate=[c for b,c in pairs]
  delta=[dict(base_id=c['base_id'],delta=float(c['layout_ok'])-float(b['layout_ok'])) for b,c in pairs if b['layout_ok'] is not None and c['layout_ok'] is not None]
  report.append(f"| {model} | {baseline_model} | {mode} | {len(pairs)} | {fmt_ci(mean_ci(base,'layout_ok'),True)} | {fmt_ci(mean_ci(candidate,'layout_ok'),True)} | {fmt_ci(mean_ci(delta,'delta'),True)} |")
  paired_summary.append(dict(machine=machine,tier=tier,model=model,baseline_model=baseline_model,mode=mode,matched_invoked=len(pairs),layout_pairs=len(delta),baseline_layout=fmt_ci(mean_ci(base,'layout_ok'),True),candidate_layout=fmt_ci(mean_ci(candidate,'layout_ok'),True),layout_change_points=fmt_ci(mean_ci(delta,'delta'),True)))
 csv_write(ROOT/'results/format_paired_invoked.csv',paired_summary)
 report+=['','### Reference spacing and scoring','', 'Exact match has always collapsed all whitespace before comparison, including blank lines. Therefore a blank line after a list introduction cannot by itself lower the exact-match score. The original raw character-error metric does count spacing differences. The AI-only table now also reports character error after collapsing whitespace, with the original metric retained for traceability. List layout checks compare item counts, marker type and introductory colon; they do not penalize blank lines around a list. Email and prose paragraph counts remain layout-sensitive and need human reference validation. The low exact-match rates cannot be explained by blank lines alone.','', '### Scope of the runtime comparison','', 'The Mac formatter measurements use GGUF on CPU. They do not measure the current Windows GPU Qwen 1.5B CTranslate2 int8 backend. Qwen3 1.7B has been used as a supplementary local judge, which is not a formatter benchmark for that model. Qwen 1.5B CT2 int8 and Qwen 3B CT2 int8 are added as separate CPU-on-Mac conditions; only completed result files count. The actual CUDA int8_float16 RTX run remains a Windows task and cannot be claimed from this Mac. No result from another format or device substitutes for them.','', '### Confirmed FlowState date-content bug','', 'Read-only reproduction confirms that “october eighteenth twenty twenty six” becomes “October 18 twenty six”. The repeated-word cleanup removes a meaningful “twenty”; this happens before the AI and also affects the rules-only baseline. The correct expected answer must not be changed to match this bug. In this audited version, “had” and “that” are explicitly protected: “I had had enough” and “I know that that works” remain unchanged in direct tests. The original app code has not been edited. Reproduction details are saved in APP_BUGS.md.']
 report+=['','### Model call trace health','', 'A backend error is not a successful AI formatting call. Incomplete traces can mean deadline interruption; the raw error field distinguishes an exception from an ordinary deadline cut-off.','', '| Model | Mode | Raw calls | Backend exceptions | Incomplete calls |','|---|---|---:|---:|---:|']
 for key,rs in sorted(groups.items()):
  if key[-1]!=600:continue
  traces=[c for r in rs for c in r['llm_calls']]
  if traces:report.append(f"| {key[2]} | {key[3]} | {len(traces)} | {sum(bool(c.get('error')) for c in traces)} | {sum(not c.get('completed',False) for c in traces)} |")
 # Separate fidelity and raw-output warnings; no proxy called an answered-instead rate.
 report+=['','## Content safeguards and instruction-like dictation','', 'The raw response and final pasted-text candidate are both saved for every model call. Guard acceptance, repair, rejection and salvage are recorded per call. Repaired-word counts can be derived from the raw/fixed word alignment; they are not yet reported as an exact count of forbidden edits. Any instruction-like response needs human classification before an answered-instead rate can be certified. A rejected answer remains a model failure even if FlowState restores the input. No zero-failure claim is made from the guard alone.','', '## When the model is actually used','']
 rules=[r for r in format_rows if r['model']=='rules']
 if rules:
  n=sum(r['needs_polish_after_rules'] for r in rules);report.append(f'The rules-only run has {len(rules)} cases; {n} ({100*n/len(rules):.1f}%) satisfy needs_polish after rules. This is a synthetic text-set trigger rate, not an ASR/live-window trigger rate. Actual model calls can be lower because of the CPU length skip. The formatter-size decision must therefore include recognizer punctuation, not model speed alone.')
 report+=['','## Repeated-output consistency','', '| Machine | Tier | Model | Mode | Generous-budget repeated pairs | Different final outputs |','|---|---|---|---|---:|---:|']
 checks=collections.defaultdict(dict)
 for r in format_rows:
  if r['budget']==600:checks[(r['machine'],r['tier'],r['model'],r['mode'],r['id'])][r['repeat']]=r
 diffs=collections.defaultdict(lambda:[0,0])
 for key,pairs in checks.items():
  if 0 in pairs and 1 in pairs:diffs[key[:4]][0]+=1;diffs[key[:4]][1]+=pairs[0]['output']!=pairs[1]['output']
 for key,(n,d) in sorted(diffs.items()):report.append('| '+' | '.join(map(str,key))+f' | {n} | {d} |')
 report+=['','Deadline-limited repeats may diverge because interruption time changes. Greedy model determinism is judged on completed, generous-budget calls; final-output equality alone can hide different raw responses that the guard rejected. Raw traces remain available.','', '## Speed and memory','', 'Speed uses a separate three warm-ups and ten timed calls per input. CPU measurements here use six threads; four-thread constrained tests belong to T2/T4. CPU shipped-mode long sections can bypass the model; those latency numbers do not demonstrate generation speed. Load time has an uncontrolled filesystem cache and is never labelled cold-after-reboot. Sampled process RSS can miss peaks shorter than 20ms.','', '| Machine / tier | Model | Mode / input | Timed calls | Median s | p95 s | Inside 3.5 s | Inside 4 s | Inside 8 s | Calls using model |','|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
 speedgroups=collections.defaultdict(list)
 for r in speed_rows:speedgroups[(r['machine'],r['tier'],r['model'],r.get('mode',''),r.get('input_label','14-second speech'),r.get('protocol','asr-14s-v1' if r.get('kind')=='asr' else 'v1-exploratory'))].append(r)
 speedsummary=[]
 for key,rows in sorted(speedgroups.items()):
  vals=np.array([r['seconds'] for r in rows]);med=float(np.median(vals));p95=float(np.percentile(vals,95));rates=[100*float(np.mean(vals<=b)) for b in [3.5,4,8]];calls=sum(r.get('llm_calls',1)>0 for r in rows)
  report.append(f'| {key[0]} / {key[1]} | {key[2]} | {key[3]} / {key[4]} ({key[5]}) | {len(rows)} | {med:.3f} | {p95:.3f} | {rates[0]:.1f}% | {rates[1]:.1f}% | {rates[2]:.1f}% | {calls} |')
  speedsummary.append(dict(machine=key[0],tier=key[1],model=key[2],mode=key[3],input=key[4],protocol=key[5],runs=len(rows),median_s=med,p95_s=p95,within35=rates[0],within4=rates[1],within8=rates[2]))
 report+=['','### Why some speed figures differ','', 'The approximately 0.27-second and 3.7-second Qwen 1.5B long-input figures come from different speed protocols, not an identical input: v1 used repetitive exploratory text and generated a short rejected response; v2 uses natural prose near 220 model tokens. Both are retained and labelled. They must not be pooled or interpreted as a regression. The Qwen 0.5B high p95 includes real slow calls; a median hides those stalls. Ten timed calls give an unstable tail estimate, and saved evidence alone does not establish whether background work, scheduling or inference caused a stall. The completed quick-plan ten-trial repeat measured the same 60-word input at approximately 0.879 seconds median / 0.897 seconds p95 for Qwen 1.5B and 0.500 / 0.507 seconds for compact Qwen 0.5B. The old stall did not recur; its cause remains unknown. Raw traces, input hashes and process CPU time are retained, alongside the old outliers.']
 csv_write(ROOT/'results/speed_summary.csv',speedsummary)
 if not speed_rows:report+=['','No dedicated speed run has finished yet. Per-case quality-run times are saved but are not substituted for the dedicated speed protocol.']
 report+=['','### Recorded load time and peak memory','', 'Latest completed resource record for each condition. Values are decimal MB. Process-tree memory includes child runtimes where visible; Apple CoreML service allocations outside the tree may be missed. These are sampled peaks, not guaranteed total model memory. Native load includes compilation/cache behavior and is not a reboot-cold comparison.','', '| Machine | Condition | Load s | Process MB | Process tree MB | Total device VRAM MB |','|---|---|---:|---:|---:|---:|']
 resource_latest={}
 for p in sorted((ROOT/'results').glob('*/*/resources.json')):
  if not (p.parent/'environment.json').exists():continue
  condition=re.sub(r'^\d{8}T\d{6}\.\d+Z-','',p.parent.name);resource_latest[(p.parent.parent.name,condition)]=json.loads(p.read_text())
 for (machine,condition),res in sorted(resource_latest.items()):
  def mb(k):return f"{res[k]/1e6:.1f}" if res.get(k) is not None else 'Unavailable'
  report.append(f"| {machine} | {condition} | {res.get('load_seconds','Unavailable')} | {mb('peak_process_rss_bytes')} | {mb('peak_process_tree_rss_bytes')} | {mb('peak_device_vram_bytes')} |")
 report+=['','Memory/load records are in each completed run’s resources.json; NVIDIA VRAM is total device use rather than process-exclusive allocation. Combined ASR+formatter VRAM fit on 8 GB or 4 GB is unmeasured until both run simultaneously on the relevant GPU. Near-full-VRAM behavior is also pending Windows testing; no allocation stress test is attempted on this Mac’s unified memory.','', '## Speech recognition and long recordings','', 'The full saved public pool contains 300 utterances each from LibriSpeech test-clean/test-other with seed 1729; the primary tables use the fixed quick-screen IDs when quick_profile.json is present. The pool creates ten chapter concatenations over one minute and synthetic coloured-noise copies at measured 10 and 5 dB SNR. Concatenations are explicitly labelled as synthetic long-form; there is no claim they replicate natural long dictation. The supplementary noise is not MUSAN. LibriSpeech’s references do not give reliable punctuation or proper-noun case; those metrics need D1. All recordings remain local.','', '| Machine / tier | Model | Subset | Utterances | WER % [95% CI] |','|---|---|---|---:|---|']
 unique_asr={}
 for r in asr_rows:unique_asr[(r['machine'],r['tier'],r['model'],r['subset'],r['id'])]=r
 asr_rows=list(unique_asr.values())
 agroups=collections.defaultdict(list)
 for r in asr_rows:agroups[(r['machine'],r['tier'],r['model'],r['subset'])].append(r)
 asummary=[]
 for key,rows in sorted(agroups.items()):
  if key[-1]=='silence':report.append(f'| {key[0]} / {key[1]} | {key[2]} | silence | {len(rows)} | {sum(r["insertions"] for r in rows)} hallucinated words (WER undefined) |');continue
  errors=np.array([r['substitutions']+r['deletions']+r['insertions'] for r in rows]);counts=np.array([r['ref_words'] for r in rows]);rng=np.random.default_rng(1729);idx=rng.integers(0,len(rows),size=(2000,len(rows)));sample=errors[idx].sum(axis=1)/np.maximum(1,counts[idx].sum(axis=1));v=(float(errors.sum()/max(1,counts.sum())),*map(float,np.quantile(sample,[.025,.975])))
  report.append(f'| {key[0]} / {key[1]} | {key[2]} | {key[3]} | {len(rows)} | {fmt_ci(v,True)} |');asummary.append(dict(machine=key[0],tier=key[1],model=key[2],subset=key[3],count=len(rows),wer=v[0],ci_low=v[1],ci_high=v[2]))
 csv_write(ROOT/'results/asr_summary.csv',asummary)
 if not asr_rows:report+=['','No scored speech-recognition run has finished. Downloaded models are not evidence of accuracy.']
 report+=['','## Whisper base punctuation-prompt control','', 'The control uses the same base.en weights, beam 5, word timestamps, 100 audio IDs and all other decoding settings. It removes only the punctuation hotwords; whole-file runs have no preceding-window context. A lower error rate can support a prompt effect on this sample, but does not establish a universal cause from one changed condition.','', '| Subset | Matched clips | With punctuation prompt WER % | Without prompt WER % | Difference, percentage points [95% CI] |','|---|---:|---:|---:|---|']
 prompted={(r['machine'],r['tier'],r['id']):r for r in asr_rows if r['model']=='whisper-base'}
 controls=collections.defaultdict(list)
 for r in asr_rows:
  if r['model']=='whisper-base-no-punctuation' and (b:=prompted.get((r['machine'],r['tier'],r['id']))):controls[r['subset']].append((b,r))
 prompt_summary=[]
 for subset,pairs in sorted(controls.items()):
  err=lambda r:r['substitutions']+r['deletions']+r['insertions']
  if subset=='silence':
   a=sum(r['insertions'] for r,c in pairs);b=sum(c['insertions'] for r,c in pairs)
   report.append(f'| silence | {len(pairs)} | {a} invented words | {b} invented words | WER undefined |');continue
  counts=np.array([a['ref_words'] for a,b in pairs]);aa=np.array([err(a) for a,b in pairs]);bb=np.array([err(b) for a,b in pairs]);rng=np.random.default_rng(1729);idx=rng.integers(0,len(pairs),size=(2000,len(pairs)));delta=(bb[idx].sum(axis=1)-aa[idx].sum(axis=1))/np.maximum(1,counts[idx].sum(axis=1));a=aa.sum()/max(1,counts.sum());b=bb.sum()/max(1,counts.sum());ci=(b-a,*map(float,np.quantile(delta,[.025,.975])))
  report.append(f'| {subset} | {len(pairs)} | {100*a:.2f} | {100*b:.2f} | {fmt_ci(ci,True)} |');prompt_summary.append(dict(subset=subset,matched_clips=len(pairs),with_prompt_wer=a,without_prompt_wer=b,change_points_ci=fmt_ci(ci,True)))
 if not controls:report.append('Control run not yet complete; no causal conclusion is drawn.')
 prompt_examples=[]
 for pairs in controls.values():
  for b,c in pairs:prompt_examples.append(dict(id=b['id'],subset=b['subset'],reference=b['reference'],with_prompt=b['output'],without_prompt=c['output'],insertions_with_prompt=b['insertions'],insertions_without_prompt=c['insertions'],insertion_reduction=b['insertions']-c['insertions']))
 csv_write(ROOT/'results/punctuation_prompt_examples.csv',sorted(prompt_examples,key=lambda r:r['insertion_reduction'],reverse=True))
 csv_write(ROOT/'results/punctuation_prompt_control.csv',prompt_summary)
 stream_rows=[r for r in stream_rows if not r['model'].startswith('parakeet-v') or r.get('backend_metadata',{}).get('adapter_revision')=='onnx-word-boundary-v2']
 stream_rows=list({(r['machine'],r['tier'],r['model'],r.get('formatter','rules'),r['id']):r for r in stream_rows}.values())
 report+=['','The streaming processor is an attributed benchmark adaptation of the pinned source seam/gap/repair methods, with capture and thread scheduling replaced by event-driven audio arrival. It does not instantiate StreamingDictation. It measures actual processing durations and simulates backlog; simulated stop latency is not a live hotkey-to-paste measurement. The original portable adapter misread library-normalized leading spaces as if raw SentencePiece markers were still present, grouping entire phrases as one word. Those legacy streaming rows are excluded from the current comparison and retained in raw files. Corrected runs record adapter_revision=onnx-word-boundary-v2. Pause selection still uses estimated token-derived word ends, not forced alignment. No claim that its pause/seam accuracy matches Whisper is made without word-level reference alignments. Per-minute drift and ±1-second seam-error metrics remain unavailable until alignments are supplied. Portable ONNX Parakeet uses the pinned Silero VAD adapter for recordings longer than 30 seconds, with 20-second target chunks; Apple-native models use their runtime’s long-recording handling. These backend conditions are recorded separately.','', '| Machine / tier | Model / formatter | Clip | Streaming WER % | Final processing s | Simulated stop s | Full recovery |','|---|---|---|---:|---:|---:|---|']
 for r in stream_rows:report.append(f'| {r["machine"]} / {r["tier"]} | {r["model"]} / {r.get('formatter','rules')} | {r["id"]} | {100*r["wer"]:.2f} | {r["measured_final_processing_seconds"]:.3f} | {r["simulated_stop_seconds"]:.3f} | {r["recovered_full_recording"]} |')
 report+=['','### Formatter trigger rate in streamed speech','', 'Measured per cleanup section in live windows, after vocabulary and rules. Recovery and final sections are excluded from this live rate. Older runs without section traces remain unavailable, rather than being treated as zero. Rules-only streaming measures potential triggers, not the effect of an AI formatter.','', '| Speech model | Live sections | Would trigger AI % | Actual model calls |','|---|---:|---:|---:|']
 sectiongroups=collections.defaultdict(list)
 for r in stream_rows:
  for section in r.get('cleanup_sections',[]):
   if section['phase']=='live':sectiongroups[(r['machine'],r['tier'],r['model'],r.get('formatter','rules'))].append(section)
 for key,sections in sorted(sectiongroups.items()):report.append(f"| {key[2]} ({key[3]}) | {len(sections)} | {100*np.mean([s['needs_polish_after_rules'] for s in sections]):.1f} | {sum(s['llm_calls'] for s in sections)} |")
 # Generate blind review only from completed, matched baseline/candidate rows.
 outputmap={(r['machine'],r['tier'],r['model'],r['mode'],r['budget'],r['id']):r for r in format_rows if r['repeat']==0}
 rng=random.Random(1729);review=[];keymap=[];failures=[]
 for key,base in sorted(outputmap.items()):
  machine,tier,model,mode,budget,cid=key
  if model not in ['qwen15-q4','qwen15-ct2'] or mode!='shipped' or budget!=600:continue
  for candidate in ['qwen05-q4','qwen05-q8','qwen3-06-q8','t5-tiny','rules','qwen25-3-ct2','qwen25-3-q4']:
   if candidate=='qwen25-3-ct2' and model!='qwen15-ct2':continue
   if candidate!='qwen25-3-ct2' and model!='qwen15-q4':continue
   other=outputmap.get((machine,tier,candidate,mode,budget,cid))
   if other is None:continue
   if other['char_error']>.01:failures.append((base,other))
 # For each candidate, exactly up to 60 random matched cases, stable seed.
 pairgroups=collections.defaultdict(list)
 for b,c in failures:pairgroups[(b['machine'],b['tier'],c['model'])].append((b,c))
 for key,pairs in pairgroups.items():
  # Include all matched cases, not only failures, to avoid selection bias.
  pairs=[]
  for k,b in outputmap.items():
   if k[0]==key[0] and k[1]==key[1] and k[2]==('qwen15-ct2' if key[2]=='qwen25-3-ct2' else 'qwen15-q4') and k[3]=='shipped' and k[4]==600:
    c=outputmap.get((k[0],k[1],key[2],k[3],k[4],k[5]))
    if c:pairs.append((b,c))
  rng.shuffle(pairs)
  for b,c in pairs[:60]:
   flip=rng.choice([False,True]);aa,bb=(c,b) if flip else (b,c);rid='review-'+hashlib.sha256(json.dumps([key,b['id'],aa['model'],bb['model'],aa['output'],bb['output']],ensure_ascii=False).encode()).hexdigest()[:12]
   review.append(dict(review_id=rid,input=b['input'],output_a=aa['output'],output_b=bb['output'],winner='',layout_notes='',punctuation_notes='',faithfulness_notes='',both_unacceptable=''))
   keymap.append(dict(review_id=rid,model_a=aa['model'],model_b=bb['model'],machine=key[0],tier=key[1],case=b['id']))
 if review:
  previous=ROOT/'HUMAN_REVIEW.csv'
  if previous.exists():
   oldrows=list(csv.DictReader(previous.open()));old={r['review_id']:r for r in oldrows}
   graded=[r for r in oldrows if any(r.get(k) for k in ['winner','layout_notes','punctuation_notes','faithfulness_notes','both_unacceptable'])]
   if graded:csv_write(ROOT/'HUMAN_REVIEW_SAVED_GRADES.csv',graded)
   for r in review:
    if r['review_id'] in old:
     for field in ['winner','layout_notes','punctuation_notes','faithfulness_notes','both_unacceptable']:r[field]=old[r['review_id']].get(field,'')
  csv_write(previous,review);csv_write(ROOT/'results/BLIND_REVIEW_KEY.csv',keymap)
 report+=['','## Blind review','', f'{len(review)} blind review rows are currently available in HUMAN_REVIEW.csv. Model identities are kept separately in results/BLIND_REVIEW_KEY.csv. Rubric: prefer faithful wording first, then correct email/list/paragraph layout, then punctuation/case; mark A, B, tie, or both unacceptable. No reviewer votes or win/tie/loss rates are invented. The earlier automated judge is excluded; the human sheet is the source of reviewer votes.']
 report+=['','The Qwen3 1.7B automated judge has been withdrawn from scoring and recommendations because its excessive both-unacceptable rate made its verdicts unhelpful. Raw judge files remain archived for audit. They are not human grades. Only explicitly entered HUMAN_REVIEW.csv votes count as human review; blank cells are missing evidence.']
 graded=[r for r in review if r.get('winner') or r.get('both_unacceptable')]
 report.append(f'Actual human-graded rows currently present: {len(graded)} of {len(review)}. No grades are invented by this benchmark.')
 report+=['','## Concrete failure examples','', 'These examples are actual saved final outputs, compared with hand-written references. Differences can include valid alternatives; descriptive notes are not independent human verdicts.']
 chosen=[];seen=set()
 bycat=collections.defaultdict(list)
 for pair in sorted(failures,key=lambda x:(x[1]['id'],x[1]['model'])):bycat[pair[1]['category']].append(pair)
 ordered=[]
 while any(bycat.values()):
  for category in sorted(bycat):
   if bycat[category]:ordered.append(bycat[category].pop(0))
 for b,c in ordered:
  key=c['base_id']
  if key in seen:continue
  seen.add(key);chosen.append((b,c))
  if len(chosen)==20:break
 for i,(b,c) in enumerate(chosen,1):
  notes=[]
  if c['layout_ok'] is False:notes.append('The structural layout check differs from the reference.')
  if c['lexical_error_expected']>.01:notes.append('Normalized wording differs from the reference; inspect whether this is an allowed filler/cue removal or a content error.')
  if c['char_error']>.01:notes.append('Punctuation, casing, spacing or wording differs from the reference.')
  report += ['',f'### Example {i}: {c["id"]} — {c["model"]}', '', 'Input:','```text',c['input'],'```','Current baseline:','```text',b['output'],'```','Candidate:','```text',c['output'],'```','Reference:','```text',c['expected'],'```',' '.join(notes)]
 if len(chosen)<20:report+=['',f'Only {len(chosen)} paired failure examples are available from completed runs; additional examples are pending.']
 report+=['','## Portability and migration','', '| Candidate | Windows | macOS | Android |','|---|---|---|---|','| Whisper CT2 | Existing CUDA/CPU route | CPU route available; see completed runtime-specific results | No validated Python/CT2 mobile integration in this benchmark |','| Parakeet ONNX | CPU/CUDA providers need per-device checks | CPU/CUDA providers require separate device runs | ONNX deployment plausible; app integration, operator support and memory unmeasured |','| Parakeet CoreML / FluidAudio | Apple runtime unavailable | Apple-specific future-port candidate | CoreML unavailable |','| Qwen GGUF | llama.cpp CPU route; shipped wheel cap respected | CPU and optional Metal are separate conditions; see completed results | Native llama.cpp integration plausible, not measured |','| Qwen CT2 | Current GPU route; conversions recorded separately | CPU future-port comparison | No validated mobile CT2 integration |','| Tiny T5 ONNX | Runtime compatible in principle; test locally | Greedy ONNX adapter verified | ONNX possible; layout unsupported |','| Optional Gemma / Llama | Access/license and adapter checks pending | Access/license and adapter checks pending | No device result |','', 'No migration is recommended yet. If a candidate later passes, review asr/engine.py, asr/models.py, text/llm.py, onboarding download sizes, installer dependencies and possibly guard behavior. Keep hardware-based defaults, offer an opt-in model choice and release a beta before changing defaults. Benchmark results alone do not justify relaxing the content guard.','', '## Missing evidence and limitations','', '- D1: owner recordings are not yet present/verified. The 25-clip recording sheet and exact reference/expected strings are provided. Hindi examples are optional placeholders for languages the owner actually uses.','- T1/T2: Windows GPU/CPU runs and cross-machine output comparison are pending. T4 is optional and unmeasured.','- All proposed models, precision variants, deadlines and runtimes must appear in completed result files before a full-matrix claim is made. The extended 3B/CT2 and gated-model conditions may remain pending.','- Standalone formatting does not fully reproduce assembled streamed text. In particular, lowercase fragment edges are deliberately retained by _keep_edges; do not blame that behavior on the candidate alone.','- Structural layout scoring, synthetic noise, chapter concatenation, estimated Parakeet word ends, and shared desktop background activity limit interpretation. Dedicated speed runs serialize inference; quality-run timings are not treated as the speed protocol.','- The public-audio suite needs independent word alignments for boundary and per-minute metrics. No hand-aligned results are invented.','- A no-deadline pass uses a large finite budget, not mathematically unlimited time. Any still-truncated call must remain excluded from a pure model-quality claim.','- Actual installed bytes and verified upstream file sizes are different from peak download traffic or RAM. No conversion size is estimated as if measured.','', '## Pass criteria before replacing a default','', 'Owner-voice WER must stay within 0.5 percentage points of baseline; public-speech confidence and streaming seam behavior must be no worse. Guard rejection may rise by at most 2 points and layout accuracy may fall by at most 2 points. Answered-instead must be zero, content must be preserved, blind review must not be significantly worse, median stop-to-text must be no slower on the same tier, and at least 95% of formatter calls must finish within their budget. Missing evidence means not qualified, rather than pass.','', '## Reproducibility files','', 'README.md; config.yaml; model_manifest.json; model_catalogue.json; requirements-macos.lock.txt; results/source_audit/audit.json; per-run environment.json, raw JSONL traces and resources.json. The model plan records exact repos, full revisions and selected weight sizes.','']
 text='\n'.join(report);(ROOT/'REPORT.md').write_text(text)
 # Readable offline HTML, including tables, code samples and links, without an external service.
 parts=['<!doctype html><html><meta charset="utf-8"><title>FlowState benchmark report</title><style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:16px/1.6 system-ui;color:#172033}h1,h2,h3{line-height:1.2}h2{margin-top:40px}pre{white-space:pre-wrap;background:#f2f4f8;padding:18px}table{border-collapse:collapse;font-size:13px;display:block;overflow-x:auto}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left}a{color:#245fdb}li{margin:8px 0}</style>'];in_code=False;in_table=False
 for line in report:
  if line=='```text':
   if in_table:parts.append('</tbody></table>');in_table=False
   parts.append('<pre>');in_code=True;continue
  if line=='```':parts.append('</pre>');in_code=False;continue
  if in_code:parts.append(html.escape(line)+'\n');continue
  if line.startswith('|'):
   if re.match(r'^\|[\s|:\-]+\|$',line):continue
   if not in_table:parts.append('<table><tbody>');in_table=True
   parts.append('<tr>'+''.join('<td>'+html.escape(c.strip())+'</td>' for c in line.strip('|').split('|'))+'</tr>');continue
  if in_table:parts.append('</tbody></table>');in_table=False
  if line.startswith('### '):parts.append('<h3>'+html.escape(line[4:])+'</h3>')
  elif line.startswith('## '):parts.append('<h2>'+html.escape(line[3:])+'</h2>')
  elif line.startswith('# '):parts.append('<h1>'+html.escape(line[2:])+'</h1>')
  elif line.startswith('- '):parts.append('<p>• '+html.escape(line[2:])+'</p>')
  elif line:parts.append('<p>'+html.escape(line)+'</p>')
 if in_table:parts.append('</tbody></table>')
 parts.append('</html>');(ROOT/'REPORT.html').write_text('\n'.join(parts))
 # Charts contain actual observations only; do not draw placeholder WER points.
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 charts=ROOT/'results/charts';charts.mkdir(exist_ok=True)
 if summary:
  filtered=[r for r in summary if r['budget']==600 and r['mode']=='shipped' and r['rejected_fraction'] is not None]
  if filtered:
   fig,ax=plt.subplots(figsize=(9,4));ax.bar([r['model'] for r in filtered],[100*r['rejected_fraction'] for r in filtered]);ax.set_ylabel('Rejected repair calls (%)');ax.set_title('Guard rejection · generous budget · shipped mode');fig.tight_layout();fig.savefig(charts/'guard_rejection.png',dpi=150);plt.close(fig)
 if speedsummary:
  weights={'qwen15-q4':1117320736,'qwen05-q4':491400032,'qwen05-q8':675710816,'qwen3-06-q8':639446688,'t5-tiny':32414206}
  for model,folder in [('qwen15-ct2','jncraton--Qwen2.5-1.5B-Instruct-ct2-int8'),('qwen25-3-ct2','qwen25-3-ct2-converted')]:
   path=ROOT/'models'/folder/'model.bin'
   if path.exists():weights[model]=path.stat().st_size
  filtered=[r for r in speedsummary if r['input']=='60_words' and r['mode']=='unlimited' and r['model'] in weights and r['protocol']=='speed-v2-natural-prose']
  if filtered:
   fig,ax=plt.subplots(figsize=(8,5))
   for r in filtered:ax.scatter(weights[r['model']]/1e6,r['median_s']);ax.annotate(r['model'],(weights[r['model']]/1e6,r['median_s']))
   ax.set_xlabel('Selected model weights (decimal MB)');ax.set_ylabel('Median 60-word pipeline latency (s)');ax.set_title('This machine only · CPU limit lifted');fig.tight_layout();fig.savefig(charts/'latency_vs_size.png',dpi=150);plt.close(fig)
 # Actual selected speech files, not nominal parameter counts or download traffic.
 speech_sizes={}
 from backends.asr import SPEECH
 from backends.native_asr import NativeParakeet
 native=json.loads((ROOT/'native_manifest.json').read_text()) if (ROOT/'native_manifest.json').exists() else []
 for model,repo in SPEECH.items():
  if model.startswith('parakeet-coreml'):
   record=next((r for r in native if r['repo']==repo),None)
   if record:
    enc='EncoderInt4.mlmodelc' if model.endswith('int4') else 'Encoder_v2.mlmodelc' if model.endswith('int8v2') else 'Encoder.mlmodelc'
    components=[enc,'Preprocessor.mlmodelc','Decoder.mlmodelc','JointDecision.mlmodelc' if model.endswith('-v2') else 'JointDecisionv3.mlmodelc']
    speech_sizes[model]=sum(f['bytes'] for f in record['files'] if any(f['path'].startswith(c+'/') for c in components) or f['path']=='parakeet_vocab.json')
  else:
   folder=ROOT/'models'/repo.replace('/','--')
   if model.startswith('whisper'):files=[folder/'model.bin']
   elif model.endswith('int8'):files=[folder/'encoder-model.int8.onnx',folder/'decoder_joint-model.int8.onnx',folder/'vocab.txt']
   else:files=[folder/'encoder-model.onnx',folder/'encoder-model.onnx.data',folder/'decoder_joint-model.onnx',folder/'vocab.txt']
   if all(f.exists() for f in files):speech_sizes[model]=sum(f.stat().st_size for f in files)
 csv_write(ROOT/'results/speech_model_sizes.csv',[dict(model=k,selected_bytes=v) for k,v in speech_sizes.items()])
 for subset in ['test-clean','test-other']:
  plotted=[r for r in asummary if r['subset']==subset and r['model'] in speech_sizes]
  if plotted:
   fig,ax=plt.subplots(figsize=(10,6))
   for r in plotted:
    x=speech_sizes[r['model']]/1e6;y=100*r['wer'];ax.errorbar(x,y,yerr=[[y-100*r['ci_low']],[100*r['ci_high']-y]],fmt='o',capsize=3);ax.annotate(r['model'],(x,y),xytext=(5,5),textcoords='offset points',fontsize=8)
   ax.set_xlabel('Selected model files (decimal MB)');ax.set_ylabel('Word error (%) · 95% bootstrap interval');ax.set_title('This Mac · '+subset+' · runtimes labelled by model');fig.tight_layout();fig.savefig(charts/('wer_vs_size_'+subset+'.png'),dpi=150);plt.close(fig)
 import owner_report
 owner_report.main()
 import quick_recommendation
 quick_recommendation.main()
 import review2_summary
 review2_summary.main()
 destination_file=ROOT/'report_destination.json'
 if destination_file.exists():
  import shutil
  dest=pathlib.Path(json.loads(destination_file.read_text())['path']);dest.mkdir(parents=True,exist_ok=True)
  for name in ['REPORT.md','REPORT.html','RESULTS_EXPLAINED.html','HUMAN_REVIEW.csv','APP_BUGS.md','MAC_QUICK_RESULTS.md','REVIEW2_RESPONSE.md']:
   if (ROOT/name).exists():shutil.copy2(ROOT/name,dest/name)
  if (ROOT/'data/RECORDING_SHEET.html').exists():shutil.copy2(ROOT/'data/RECORDING_SHEET.html',dest/'RECORDING_SHEET.html')
  for name in ['format_invoked_only.csv','format_paired_invoked.csv','speed_summary.csv','asr_summary.csv','date_bug_reproduction.json','format_by_category.csv','punctuation_prompt_control.csv','punctuation_prompt_examples.csv']:
   if (ROOT/'results'/name).exists():shutil.copy2(ROOT/'results'/name,dest/name)
 print('Report updated:',len(format_rows),'completed formatting rows;',len(speed_rows),'timed speed rows;',len(asr_rows),'speech rows;',len(review),'blind review rows',flush=True)
if __name__=='__main__':main()
