import json,pathlib,yaml
ROOT=pathlib.Path(__file__).resolve().parent
from backends.formatters import MODELS
from backends.asr import SPEECH
config=dict(source_commit='6c465c16b67910f5fc449c2dcf86ed426183c80c',python='3.12',seeds=dict(public_subset=1729,bootstrap=1729,blind_review=1729,synthetic_noise=1729),budgets_seconds=dict(live=8.,finish=4.,default_polish=3.5,generous_quality=600.),streaming=dict(step_seconds=10.,overlap_seconds=6.,lookahead_seconds=4.,pause_seconds=.25,stop_grace_seconds=1.),formatter=dict(chunk_tokens=220,cpu_max_words=60,modes=['shipped','unlimited'],repeat_passes=2),speed=dict(warmups=3,timed_runs=10,protocol='speed-v2-natural-prose',cold_after_reboot='not measured'),hardware_tiers=dict(t1='Windows RTX 2070 CUDA',t2='same Windows CPU only, four threads',t3='this Mac, CPU baseline; native CoreML future-port conditions separate',t4='optional actual low-end Windows laptop'),model_manifest=json.loads((ROOT/'model_manifest.json').read_text()),formatter_ids={k:dict(repo=v[0],file=v[1]) for k,v in MODELS.items()},asr_ids=SPEECH,privacy=dict(audio_uploads=False,localappdata='.appdata',app_repository_access='read-only'))
if (ROOT/'native_manifest.json').exists():config['native_models']=json.loads((ROOT/'native_manifest.json').read_text())
(ROOT/'config.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
