# FlowState statistics

## Where to see the numbers

**In FlowState:** open Settings → Stats. This shows lifetime words, dictation sessions,
recording minutes, active days, successful/failed/empty sessions, median and p95 time
to paste. Timing statistics use the latest 1,000 successful sessions. Export creates
a JSON report containing counters only. These totals start with this feature and
persist across restarts, upgrades, and history purges in
`%LOCALAPPDATA%\FlowState\usage.sqlite3`.

**Across installations:** use your private PostHog project → Dashboards. This is a
separate analytics service, not a public page on the FlowState website. Only users
who explicitly enable sharing contribute. Counts describe participating app
installations, not verified individual people; reinstalls and resetting the sharing
ID can increase installation counts.

## Connect the project

1. Create a FlowState project in https://us.posthog.com or https://eu.posthog.com.
2. Copy its **project API key** (`phc_…`) from project settings.
3. Put that public ingestion key and its region (`US` or `EU`) in
   `src/flowstate/resources/analytics.json`, then build the installer. Never put a
   personal API key or account credentials in the app.
4. For development, `FLOWSTATE_POSTHOG_KEY` and `FLOWSTATE_POSTHOG_REGION` can
   override the bundled configuration.
5. Enable sharing in Stats on your test installation and complete a dictation.
   Check PostHog's events view for `analytics_enabled`, `app_opened`, and
   `dictation_completed`.

Without a project key, local statistics work and sharing is unavailable. No cloud
project is created automatically and no analytics data is sent to an unconfigured
project. The app does not enable autocapture, screen/session replay, or person
profiles. Keep the owner dashboard private unless you deliberately share it.

## Build the portfolio dashboard

In PostHog, create a blank private dashboard named **FlowState — Usage & reliability**.
Add these insights (or give the following definitions to PostHog's dashboard AI):

| Insight | Event and calculation |
| --- | --- |
| Monthly active installations | Unique `distinct_id` on `dictation_completed`, rolling 30 days |
| Weekly active installations | Unique `distinct_id` on `dictation_completed`, rolling 7 days |
| New participating installations | Unique `distinct_id` on `analytics_enabled` |
| Total words transcribed | Sum `word_count` across completed, failed, and empty dictation events |
| Words per day | Same sum, grouped daily |
| Dictation sessions | Total count of those three dictation events |
| Recording hours | Sum `audio_seconds` across dictation events, divided by 3,600 |
| Median time to paste | Median `processing_ms` on completed events, divided by 1,000 |
| p95 time to paste | 95th percentile of `processing_ms` on completed events, divided by 1,000 |
| Successful-session rate | Completed / (completed + failed); exclude no-speech sessions |
| Returning installations | Retention with `dictation_completed` as both initial and returning event |
| Version adoption | Unique installations grouped by `app_version` |

Words count whitespace-delimited ASR tokens before formatting and screenshot
references. Words recognized during a failed paste still count as transcribed.
Session outcomes cover transcription/formatting/paste attempts; microphone setup
failures before recording reaches processing are not included. Time to paste starts
when recording stops and processing begins, and ends after the paste operation.
It does not count the time spent speaking. Empty/no-speech sessions are distinct
from failures. Do not interpret downloads as active users or opt-in counts as the
entire user base.

Useful sources: [PostHog dashboards](https://posthog.com/docs/product-analytics/dashboards),
[anonymous events](https://posthog.com/docs/data/anonymous-vs-identified-events),
[retention](https://posthog.com/docs/product-analytics/retention).

## Privacy and reliability

- Sharing defaults to **off**, including upgrades from older versions.
- Enabling sharing applies immediately; historical local totals are never uploaded.
- Shared data contains fixed event names, a random installation ID, app version,
  Windows platform label, event timestamp, word count, recording duration, processing
  duration, and a fixed outcome. It never contains transcripts, audio, images,
  clipboard content, file paths, window titles, usernames, or exception messages.
- GeoIP enrichment and person-profile processing are disabled, and the event IP
  property is zeroed. As with any HTTPS service, the provider receives a network
  connection; this is not a promise that it cannot see the source IP in transport logs.
- Uploads run in a background thread with a five-second timeout. Offline events
  retain stable UUIDs for deduplication, are bounded to 1,000 events, and expire
  after 30 days. A crash or full queue can undercount activity.
- Turning sharing off clears unsent events, resets the random ID, and prevents new
  analytics requests. An already-in-flight request cannot be recalled. Local totals
  remain. Already delivered events are not deleted by the toggle.
- Reset local stats clears counters only, not models, recordings, consent, or
  already shared events. Queue and local counter failures do not fail dictation.
- Model/session content is never scanned to produce or backfill these statistics.
