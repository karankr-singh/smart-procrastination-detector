import pandas as pd
from datetime import datetime, timedelta

from database import repositories as repo
from services.session_service import SessionManager
from services.timer import FocusTimer, Phase, State


def test_timer_pause_resume_elapsed(fake_clock):
    t = FocusTimer(25, 5, 15, clock=fake_clock)
    t.start()
    fake_clock.advance(minutes=10); t.pause()
    fake_clock.advance(minutes=30)                     # paused time must not count
    assert round(t.elapsed()) == 600 and t.state == State.PAUSED
    t.resume(); fake_clock.advance(minutes=5)
    assert round(t.elapsed()) == 900 and round(t.remaining()) == 600


def test_timer_completion_and_pomodoro_cycle(fake_clock):
    t = FocusTimer(25, 5, 15, sessions_before_long_break=4, clock=fake_clock)
    phases = []
    for _ in range(4):
        t.start(); fake_clock.advance(minutes=26)
        assert t.is_done(); t.complete(); phases.append(t.phase)
        t.start(); fake_clock.advance(minutes=16); t.complete()    # take the break
    assert phases == [Phase.SHORT_BREAK, Phase.SHORT_BREAK, Phase.SHORT_BREAK, Phase.LONG_BREAK]


def test_custom_duration_and_stop(fake_clock):
    t = FocusTimer(25, 5, 15, clock=fake_clock)
    t.start(planned_minutes=50); fake_clock.advance(minutes=20)
    assert t.planned_seconds == 3000 and round(t.stop()) == 1200 and t.state == State.IDLE


def test_session_persists_with_status_and_minutes(uid, fake_clock):
    m = SessionManager(uid, repo.get_settings(uid), clock=fake_clock)
    sid = repo.add_subject(uid, "Maths")
    m.start(sid, None, 25)
    fake_clock.advance(minutes=10); m.pause()
    fake_clock.advance(minutes=5); m.resume()
    fake_clock.advance(minutes=5)
    m.log_interruption()
    rec = m.stop()
    df = repo.list_sessions_df(uid)
    assert len(df) == 1 and rec["session_status"] == "Stopped Early"
    r = df.iloc[0]
    assert round(r["actual_minutes"], 1) == 15.0 and r["planned_minutes"] == 25 and r["interruption_count"] == 1
    assert pd.isna(r["active_minutes"])      # tracking was off



def test_completed_session_and_auto_break(uid, fake_clock):
    m = SessionManager(uid, repo.get_settings(uid), clock=fake_clock)
    m.start(None, None, 25)
    fake_clock.advance(minutes=25, seconds=1)
    assert m.tick() == ["phase_complete"]
    assert repo.list_sessions_df(uid).iloc[0]["session_status"] == "Completed"
    assert m.timer.phase == Phase.SHORT_BREAK and m.timer.state == State.RUNNING
    fake_clock.advance(minutes=5, seconds=1)
    assert m.tick() == ["break_over"] and m.timer.phase == Phase.FOCUS


def test_accidental_start_is_discarded(uid, fake_clock):
    m = SessionManager(uid, repo.get_settings(uid), clock=fake_clock)
    m.start(None, None, 25); fake_clock.advance(seconds=3)
    assert m.stop() is None and repo.list_sessions_df(uid, include_running=True).empty


def test_orphaned_running_session_is_abandoned(uid, fake_clock):
    m = SessionManager(uid, repo.get_settings(uid), clock=fake_clock)
    m.start(None, None, 25)
    assert repo.abandon_orphaned_sessions(uid) == 1
    assert repo.list_sessions_df(uid, include_running=True).iloc[0]["session_status"] == "Abandoned"


def test_session_records_survive_restart(uid, tmpdb, fake_clock):
    import database.db as db
    m = SessionManager(uid, repo.get_settings(uid), clock=fake_clock)
    m.start(None, None, 25); fake_clock.advance(minutes=25, seconds=1); m.tick()
    db.configure(tmpdb)
    assert len(repo.list_sessions_df(uid)) == 1
