import json
from datetime import datetime
from unittest.mock import patch
import pytest
from flowstate.config import ConfigStore
from flowstate.usage import UsageStore, UsageTracker


@pytest.fixture
def usage(tmp_path):
    config=ConfigStore(path=tmp_path/'config.json')
    tracker=UsageTracker(UsageStore(tmp_path/'usage.sqlite3'),config,key='phc_test',host='https://us.i.posthog.com')
    yield tracker,config
    tracker.close()


def rows(tracker):
    with tracker.store.connect() as db:
        return [json.loads(row[0]) for row in db.execute('SELECT payload FROM outbox ORDER BY created')]


def test_local_stats_survive_restart_and_history_purge(usage,tmp_path):
    tracker,_=usage
    tracker.record(120,90,2500,'success')
    tracker.record(30,15,1000,'error')
    tracker.record(0,5,300,'empty')
    with patch('flowstate.session.store.paths.sessions_dir',return_value=tmp_path/'sessions'):
        (tmp_path/'sessions').mkdir()
        from flowstate.session.store import purge_all_sessions
        purge_all_sessions()
    data=UsageStore(tracker.store.path).snapshot()
    assert (data['words'],data['sessions'],data['successes'],data['errors'],data['empty']) == (150,3,1,1,1)
    assert data['audio_seconds']==110
    assert data['median_seconds']==2.5


def test_no_requests_events_or_identity_without_explicit_consent(usage):
    tracker,_=usage
    tracker.record(42,10,1000,'success')
    with patch('flowstate.usage.urllib.request.urlopen') as send:
        tracker.flush()
        send.assert_not_called()
    assert rows(tracker)==[]
    with tracker.store.connect() as db:
        assert db.execute('SELECT * FROM metadata').fetchall()==[]


def test_events_contain_only_counts_and_random_ids_and_retain_retry_uuid(usage):
    tracker,config=usage
    config.config.analytics.enabled=True;config.save()
    tracker.record(42,10,1250,'success')
    before=rows(tracker)
    event=before[-1]
    assert event['event']=='dictation_completed'
    assert set(event['properties'])=={'distinct_id','app_version','platform','$process_person_profile','$geoip_disable','$ip',
                                     'word_count','audio_seconds','processing_ms','outcome'}
    assert event['properties']['$process_person_profile'] is False
    assert event['properties']['$geoip_disable'] is True
    assert event['properties']['$ip']=='0.0.0.0'
    with patch('flowstate.usage.urllib.request.urlopen',side_effect=OSError('offline')):
        tracker.flush();tracker.flush()
    assert rows(tracker)==before
    assert tracker.sync_error


def test_successful_upload_removes_only_uploaded_rows(usage):
    tracker,config=usage
    config.config.analytics.enabled=True;config.save()
    tracker.record(42,10,1000,'success')
    class Response:
        status=200
        def __enter__(self): return self
        def __exit__(self,*args):pass
        def read(self,*args):return b'{"status":1}'
    def send(request,timeout):
        assert request.full_url=='https://us.i.posthog.com/batch/'
        body=json.loads(request.data)
        assert body['api_key']=='phc_test'
        tracker.record(8,2,400,'success')
        return Response()
    with patch('flowstate.usage.urllib.request.urlopen',side_effect=send):tracker.flush()
    assert len(rows(tracker))==1
    assert rows(tracker)[0]['properties']['word_count']==8
    assert tracker.last_sync is not None


def test_withdrawing_consent_clears_queue_rotates_identity_and_keeps_local_totals(usage):
    tracker,config=usage
    config.config.analytics.enabled=True;config.save()
    tracker.record(12,10,1000,'success')
    original=rows(tracker)[0]['properties']['distinct_id']
    config.config.analytics.enabled=False;config.save()
    assert rows(tracker)==[]
    with patch('flowstate.usage.urllib.request.urlopen') as send:
        tracker.flush();send.assert_not_called()
    assert tracker.store.snapshot()['words']==12
    config.config.analytics.enabled=True;config.save()
    assert rows(tracker)[0]['properties']['distinct_id'] != original


def test_restarting_does_not_count_as_a_new_participating_installation(usage):
    tracker,config=usage
    config.config.analytics.enabled=True;config.save()
    original=rows(tracker)[0]['properties']['distinct_id']
    other=UsageTracker(tracker.store,config,key='phc_test',host='https://us.i.posthog.com')
    assert [e['event'] for e in rows(tracker)].count('analytics_enabled')==1
    other._enqueue('app_opened',{})
    assert rows(tracker)[-1]['properties']['distinct_id']==original
    other.close()


def test_no_historical_words_are_uploaded_when_sharing_is_enabled(usage):
    tracker,config=usage
    tracker.record(9999,120,1000,'success')
    config.config.analytics.enabled=True;config.save()
    assert len(rows(tracker))==1
    assert 'word_count' not in rows(tracker)[0]['properties']


def test_unknown_properties_cannot_send_content(usage):
    tracker,config=usage
    config.config.analytics.enabled=True;config.save()
    tracker._enqueue('app_opened',{'transcript':'PRIVATE TEXT','username':'PRIVATE USER'})
    assert 'PRIVATE' not in json.dumps(rows(tracker))


def test_unconfigured_project_cannot_send_or_queue(usage):
    tracker,config=usage
    tracker.key=''
    config.config.analytics.enabled=True;config.save()
    tracker.record(40,10,1000,'success')
    assert rows(tracker)==[]
    assert tracker.store.snapshot()['words']==40


def test_local_reset_does_not_change_consent_or_queued_events(usage):
    tracker,config=usage
    config.config.analytics.enabled=True;config.save()
    tracker.record(40,10,1000,'success')
    events=rows(tracker)
    tracker.store.reset()
    assert tracker.store.snapshot()['words']==0
    assert rows(tracker)==events
    assert config.config.analytics.enabled is True


def test_latencies_use_successful_sessions_only_and_real_percentiles(usage):
    tracker,_=usage
    for ms in (1000,2000,3000): tracker.record(1,1,ms,'success')
    tracker.record(1,1,100000,'error')
    data=tracker.store.snapshot()
    assert data['median_seconds']==2
    assert data['p95_seconds']==pytest.approx(2.9)


def test_stats_view_updates_and_consent_is_immediate(usage):
    from PySide6.QtWidgets import QApplication
    from flowstate.ui.usage_stats import UsageStatsView
    app=QApplication.instance() or QApplication([])
    tracker,config=usage
    view=UsageStatsView(config,tracker)
    tracker.record(1234,90,1200,'success');view.refresh()
    assert view.values['words'].text()=='1,234'
    assert view.values['median'].text()=='1.20s'
    view.sharing.setChecked(True)
    assert config.config.analytics.enabled is True
    assert json.loads(config._path.read_text())['analytics']['enabled'] is True
    view.close();view.deleteLater()


def test_dictation_records_raw_words_once_even_when_paste_fails(usage,tmp_path):
    from unittest.mock import MagicMock
    from flowstate.app import RecordingController
    from flowstate.session.model import Session
    from pathlib import Path
    tracker,_=usage
    controller=RecordingController.__new__(RecordingController)
    controller._usage=tracker
    controller.signals=MagicMock()
    controller._hotkeys=MagicMock()
    controller._asr=MagicMock()
    controller._asr.transcribe_segments.return_value=[(0,2,'one two three four')]
    controller._pipeline=MagicMock()
    controller._pipeline.run.return_value='One two three four.'
    session=Session('test',datetime.now(),tmp_path)
    with patch('flowstate.app.paste_transcript',side_effect=RuntimeError('PRIVATE clipboard failure')):
        controller._process_recording(Path('missing.wav'),session,None,[],[])
    data=tracker.store.snapshot()
    assert (data['words'],data['sessions'],data['errors'])==(4,1,1)
    controller.signals.usage_updated.emit.assert_called_once()


def test_stats_failure_does_not_break_successful_dictation(usage,tmp_path):
    from unittest.mock import MagicMock
    from flowstate.app import RecordingController
    from flowstate.session.model import Session
    from pathlib import Path
    controller=RecordingController.__new__(RecordingController)
    controller._usage=MagicMock()
    controller._usage.record.side_effect=OSError('disk full')
    controller.signals=MagicMock();controller._hotkeys=MagicMock()
    controller._asr=MagicMock();controller._asr.transcribe_segments.return_value=[(0,2,'full original text')]
    controller._pipeline=MagicMock();controller._pipeline.run.return_value='Full original text.'
    with patch('flowstate.app.paste_transcript') as paste:
        controller._process_recording(Path('missing.wav'),Session('test',datetime.now(),tmp_path),None,[],[])
    paste.assert_called_once_with('Full original text.',[])
    controller.signals.recording_finished.emit.assert_called_once()
    controller.signals.error.emit.assert_not_called()
