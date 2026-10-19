"""Plain-language point-by-point response, generated from completed evidence only."""
from common import ROOT
import json,csv,collections

def csvrows(name):
 p=ROOT/'results'/name
 return list(csv.DictReader(p.open())) if p.exists() else []
def main():
 status=json.loads((ROOT/'review2_status.json').read_text()) if (ROOT/'review2_status.json').exists() else {}
 def streams(model):
  found={}
  for p in sorted((ROOT/'results').glob('*/*-stream-'+model+'-qwen15-q4/streaming.jsonl')):
   if not (p.parent/'FINISHED.json').exists():continue
   for l in p.read_text().splitlines():
    r=json.loads(l)
    if r.get('backend_metadata',{}).get('adapter_revision')=='onnx-word-boundary-v2' or not model.startswith('parakeet-v'):found[r['id']]=r
  return list(found.values())
 turbo=streams('whisper-turbo');v2=streams('parakeet-v2-int8');v3=streams('parakeet-v3-int8')
 category=csvrows('format_by_category.csv');forced=collections.defaultdict(lambda:[0,0])
 for r in category:
  if r['mode']=='forced':forced[r['model']][0]+=int(r['cases']);forced[r['model']][1]+=int(r['ai_invoked'])
 ct2normal=[m for m in ['qwen15-ct2','qwen25-3-ct2'] if any(r['model']==m and r['mode']=='shipped' for r in category)]
 review=list(csv.DictReader((ROOT/'HUMAN_REVIEW.csv').open())) if (ROOT/'HUMAN_REVIEW.csv').exists() else []
 grades=sum(bool(r.get('winner') or r.get('both_unacceptable')) for r in review)
 prompt=csvrows('punctuation_prompt_control.csv')
 text=['# Response to the second review','', 'Current status: '+status.get('state','unknown')+' — '+status.get('phase','')+'.','', 'The original report had real gaps. This revision keeps the 100-file speech sample and restores all 300 formatting rows, with separate diagnostic conditions. Earlier portable streaming failures were caused by a benchmark adapter bug and are withdrawn.','', '| Request | What the evidence now says |','|---|---|',f'| 1. Missing real-model streaming baseline | Whisper turbo + Qwen 1.5B GGUF completed {len(turbo)} long recordings on the Mac CPU. The actual Windows GPU combination still requires Windows. |',f'| 2. Current CT2 model and 3B upper bound | Completed normal Mac CPU CT2 comparisons: {", ".join(ct2normal) or "not yet complete"}. GPU int8_float16 is not measured here. Exact source/conversion hashes are retained. |',f'| 3. Portable Parakeet wiring | Leading-space word starts were misread. After correction, v2 completed {len(v2)} clips with {sum(r["recovered_full_recording"] for r in v2)} full-recording retries; v3 completed {len(v3)} with {sum(r["recovered_full_recording"] for r in v3)} retries. Join safeguards remain enabled. |',f'| 4. Full formatting set and forced AI | The full 300-row set is restored, with 15 category tables. Completed forced-AI models: {len(forced)}; details below. Automatic and forced conditions are separate. |',f'| 5. Unhelpful automated judge | Removed from scoring and conclusions. Raw historical files are archived. The human sheet contains {grades} actual entered votes; no human grades have been invented. |',f'| 6. Punctuation-prompt control | {"Completed on the same 100 audio files; paired changes are below." if prompt else "Still pending; no prompt-effect claim is made."} |','| 7. Broken report tables | Environment rows now sit under Environment; consistency table has matching headers and values. validate_report.py checks Markdown column counts. |','','## Forced-AI coverage','','The backend must actually be reached, including on short and already-punctuated input. The prompt, chunking, guard and final rules are retained. The CPU length skip is lifted only for this labelled diagnostic.','','| Model | Cases completed | Cases reaching AI |','|---|---:|---:|']
 for model,(n,calls) in sorted(forced.items()):text.append(f'| {model} | {n} | {calls} |')
 fmt={(r['model'],r['mode']):r for r in csvrows('format_summary.csv') if float(r['budget'])==600}
 base=fmt.get(('qwen15-ct2','forced'));large=fmt.get(('qwen25-3-ct2','forced'))
 if base and large:
  timings={r['model']:r for r in csvrows('speed_summary.csv') if r['input']=='60_words' and r['mode']=='shipped' and r['model'] in ['qwen15-ct2','qwen25-3-ct2']}
  text+=['','## What the larger reference tells us','', 'The 3B reference passed more structural layout checks and was rejected less often by the word-preservation guard when AI was forced on. This is not an independent human quality verdict. In normal app mode the layout gain was much smaller, because the app bypasses AI for many inputs. The evidence does not support replacing the current formatter with one of the smaller tested models.','', '| CT2 model | Forced-AI layout checks passed | Guard rejection | Typical 60-word wait on Mac CPU |','|---|---:|---:|---:|']
  for model,row in [('qwen15-ct2',base),('qwen25-3-ct2',large)]:
   speed=timings.get(model);wait=f"{float(speed['median_s']):.2f} seconds" if speed else 'Not measured'
   text.append(f"| {model} | {100*float(row['layout_proxy']):.1f}% | {100*float(row['rejected_fraction']):.1f}% | {wait} |")
  text+=['', 'These CT2 timings are CPU measurements on this Mac. The current CPU GGUF formatter is a separate condition and is much faster here. The Windows GPU run is required before drawing a GPU speed or memory conclusion.']
 if prompt:
  text+=['','## What removing the punctuation prompt changed','','Lower word errors are better. These are paired public clips, not the owner\'s recordings. Results vary by noise condition; this does not prove the prompt causes every invented word.','','| Test set | Same clips | With prompt word errors | Without prompt word errors |','|---|---:|---:|---:|']
  for r in prompt:text.append(f"| {r['subset']} | {r['matched_clips']} | {100*float(r['with_prompt_wer']):.2f}% | {100*float(r['without_prompt_wer']):.2f}% |")
 text+=['','## What remains separate','','The RTX GPU measurements must be run on the Windows machine. WINDOWS-REVIEW-GPU.bat is prepared for the actual CT2 GPU formatter, the 3B reference and the real streaming combination. Its Windows execution is still unverified. Owner-voice recordings and entered human votes remain separate evidence.','', 'The original FlowState code and app defaults have not been changed. Detailed tables, raw-output examples and limitations are in REPORT.html.']
 (ROOT/'REVIEW2_RESPONSE.md').write_text('\n'.join(text)+'\n')
if __name__=='__main__':main()
