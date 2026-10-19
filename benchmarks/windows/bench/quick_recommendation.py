"""Translate the completed quick-screen evidence into a practical, qualified choice."""
import csv,json,pathlib,html,datetime
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parent
NAMES={'parakeet-coreml-v2':'Parakeet v2 · Apple-native','parakeet-coreml-v3':'Parakeet v3 · Apple-native','parakeet-coreml-redux':'Parakeet Redux · Apple-native','parakeet-v2-int8':'Parakeet v2 · portable','whisper-base':'Whisper base','whisper-small':'Whisper small','whisper-turbo':'Whisper turbo'}
def rows(name):
 p=ROOT/'results'/name
 return list(csv.DictReader(p.open())) if p.exists() else []
def main():
 accuracy=rows('asr_summary.csv');speed=rows('speed_summary.csv');sizes={r['model']:int(r['selected_bytes'])/1e6 for r in rows('speech_model_sizes.csv')}
 lookup={(r['model'],r['subset']):r for r in accuracy};timing={r['model']:r for r in speed if r['input']=='14-second speech'}
 review=json.loads((ROOT/'review2_status.json').read_text()) if (ROOT/'review2_status.json').exists() else None
 if ('parakeet-coreml-v2','test-clean') not in lookup:
  (ROOT/'MAC_QUICK_RESULTS.md').write_text('# Results for this machine\n\nMac-specific findings are not regenerated without the corresponding Mac result files. This folder currently contains the local hardware measurements. Read REPORT.html for the actual model/runtime tables and missing conditions. GPU and CPU figures must remain separate.\n')
  return
 models=['parakeet-coreml-v2','parakeet-coreml-redux','parakeet-v2-int8','whisper-base','whisper-small','whisper-turbo']
 text=['# FlowState: practical Mac findings','', 'Updated '+datetime.datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y, %I:%M %p IST')+'.','', '**Practical choice for a future Mac version: start with Apple-native Parakeet v2 for speech and keep Qwen 1.5B for formatting.** This is a development shortlist, not a change to the existing Windows app.','', 'Parakeet v2 is about 464 MB on the Apple-native path. On this public English sample it combines low word-error rates with a very short processing wait. The approximately 220 MB Redux version saves more space, but made more errors on difficult speech and was slower in its measured speed trial. It remains a size-first option to try with your own voice, rather than the best balance so far.','', '**For Windows: keep the current defaults until the GPU test.** The portable Parakeet v2 version is the most useful smaller speech candidate to test there next. Apple-native speed cannot be carried over to Windows.','', '**For formatting: keep the current Qwen 1.5B.** Compact Qwen 0.5B finishes the measured 60-word task faster, but the layout checks do not justify replacing the current model. The tiny grammar model also does not cover the same formatting job.','', '## Speech results you can compare','', 'Lower word-error percentages are better. These are public recordings, not your voice. Clean and difficult speech are separate sets; noise and long recordings are in the detailed report. Model size excludes the runtime and compile caches.','', '| Model | Selected files | Clean speech word errors | Difficult speech word errors | Typical time for a 14-second clip |','|---|---:|---:|---:|---:|']
 for m in models:
  clean=lookup.get((m,'test-clean'));other=lookup.get((m,'test-other'));s=timing.get(m)
  if not clean or not other:continue
  text.append(f"| {NAMES[m]} | {sizes[m]:.0f} MB | {100*float(clean['wer']):.2f}% | {100*float(other['wer']):.2f}% | {float(s['median_s']):.2f} seconds |" if s else f"| {NAMES[m]} | {sizes[m]:.0f} MB | {100*float(clean['wer']):.2f}% | {100*float(other['wer']):.2f}% | Pending |")
 text+=['','Timing is model processing on this M2 Max Mac after warm-up, not your wait for the whole recording or a live paste. Apple-native and portable backends are separate conditions. The earlier Apple-native speed trials and later portable trials used different 14-second speech excerpts, so the timing table is directional; it is not an exact same-input speed-ratio test.','', '## Long-recording results','','Apple-native Parakeet v2 completed all three selected streamed recordings without a full-recording retry. The simulated post-stop processing waits were about 0.09, 0.12 and 0.64 seconds on this Mac. These are event-driven simulations, not live hotkey-to-paste promises.','','Whisper base needed a full-recording recovery on the longest clip, producing a simulated wait of about 21.5 seconds. The earlier portable Parakeet results used a faulty word-boundary adapter and are withdrawn. With that adapter corrected, v2 completed all three selected long recordings without full-recording recovery. V3 still needed recovery on two clips. See the added streaming table below.','','## Formatting speed recheck','', 'The fresh repeat measured about 0.88 seconds for current Qwen 1.5B and 0.50 seconds for compact Qwen 0.5B on the same 60-word input. Their slower-case figures were about 0.90 and 0.51 seconds. The earlier 8-second small-model outlier did not recur in this ten-trial repeat. Its cause is not established, and the old measurement is retained. Faster formatting alone is insufficient if layout quality falls.','', '## What is finished and what is still being checked','', 'The report compares a fixed 100-file audio sample: 42 clean, 40 difficult, 12 noisy, three silence and three long recordings. Earlier larger runs are retained and reused on those IDs. Text results come from the completed formatting runs, with the full 300-row set restored after review, alongside separate forced-AI and per-category conditions. The long recordings are about 1.3, 3.9 and 8.4 minutes; fewer files do not mean they are all short.','']
 quick=list((ROOT/'results').glob('*/*-quick-decision/FINISHED.json'))
 baseline=lookup.get(('whisper-base','test-clean'))
 text.append('The shortened Mac queue has ended; see the detailed report for failed or missing conditions.' if quick else 'The last combined speech-plus-formatting checks are still running. The primary speech and formatting findings above are available now.')
 if not baseline:text.append('Whisper base whole-file accuracy is still awaiting its retry after a local audio-decoder incompatibility was repaired. Its streaming results are not a substitute for that missing accuracy run.')
 text+=['','Your recordings and the Windows runs are the next useful checks. A full scientific certification is not claimed from this smaller sample. No FlowState source or app defaults have been changed.','', 'Detailed methods, uncertainty intervals, raw failure examples and limitations are in REPORT.html.']
 if review:
  text.insert(2,'**Second-review status: '+review['state']+' — '+review['phase']+'. Earlier shortlist conclusions are provisional while these requested comparisons are added.**')
  text=[line.replace('The shortened Mac queue has ended; see the detailed report for failed or missing conditions.','The original quick screen ended. The second review adds the missing turbo streaming baseline, CT2 references and forced-AI comparisons. See current review status above.') for line in text]
 latest={}
 for file in sorted((ROOT/'results').glob('*/*/streaming.jsonl')):
  if not (file.parent/'FINISHED.json').exists():continue
  for line in file.read_text().splitlines():
   r=json.loads(line)
   if r['model'] in ['whisper-turbo','parakeet-v2-int8','parakeet-v3-int8'] and r.get('formatter')=='qwen15-q4':
    if r['model'].startswith('parakeet-v') and r.get('backend_metadata',{}).get('adapter_revision')!='onnx-word-boundary-v2':continue
    latest[(r['model'],r['id'])]=r
 if latest:
  text+=['','## Added streaming comparisons','', 'These runs use Qwen 1.5B GGUF on this Mac CPU. They are not the Windows GPU setup. Portable results below use the corrected word-boundary adapter.','', '| Speech model | Clip | Word errors | Simulated stop processing | Full-recording retry |','|---|---|---:|---:|---|']
  for (model,cid),r in sorted(latest.items()):text.append(f"| {model} | {cid} | {100*r['wer']:.2f}% | {r['simulated_stop_seconds']:.2f} seconds | {'Yes' if r['recovered_full_recording'] else 'No'} |")
 (ROOT/'MAC_QUICK_RESULTS.md').write_text('\n'.join(text)+'\n')
 plain=ROOT/'RESULTS_EXPLAINED.html'
 if plain.exists():
  content=plain.read_text();panel='<div class="note"><h2>Practical shortlist from the quick screen</h2><p><b>Future Mac version: Apple-native Parakeet v2 for speech; keep Qwen 1.5B for formatting.</b> Parakeet v2 is about 464 MB. The 220 MB Redux option saves more space but made more errors on difficult speech. Windows GPU results and your voice still need their own check.</p><p>These are measured Mac model tests, not a working Mac edition of FlowState.</p></div>'
  content=content.replace('<h2>Quick decision screen',panel+'<h2>Quick decision screen',1);plain.write_text(content)
if __name__=='__main__':main()
