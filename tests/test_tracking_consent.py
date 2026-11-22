import pandas as pd
from database import repositories as repo
from services.session_service import SessionManager
from tracking import apps, consent
from tracking.tracker import ActivityTracker


def test_tracking_off_by_default(uid):
    s = repo.get_settings(uid)
    assert consent.has_consent(s) is False
    assert consent.effective_flags(s) == (False, False)
    assert ActivityTracker.from_settings(s) is None


def test_flags_without_consent_are_ignored(uid):
    s = repo.get_settings(uid); s["track_idle"] = True; s["track_apps"] = True   # flags set, consent missing
    assert ActivityTracker.from_settings(s) is None


def test_grant_and_revoke(uid):
    consent.grant_consent(uid, idle=True, apps=False)
    s = repo.get_settings(uid)
    assert consent.effective_flags(s) == (True, False) and s["tracking_consent_at"]
    consent.revoke_consent(uid)
    assert ActivityTracker.from_settings(repo.get_settings(uid)) is None


def test_tracker_splits_active_idle_and_auto_pauses():
    idle = iter([0, 0, 90, 90, 400])
    tr = ActivityTracker(True, False, 5, idle_fn=lambda: next(idle))
    results = [tr.sample(1.0) for _ in range(5)]
    assert round(tr.active_seconds) == 2 and round(tr.idle_seconds) == 3
    assert [r["auto_pause"] for r in results] == [False, False, False, False, True]


def test_tracker_stores_only_categories_not_app_names():
    tr = ActivityTracker(False, True, app_fn=lambda: "Code.exe", idle_fn=lambda: 0)
    tr.sample(10)
    assert set(tr.category_seconds) == {"Programming"}
    assert all(e.get("category") in apps.CATEGORY_KEYWORDS or e.get("category") == "Other" for e in tr.events())
    assert "Code" not in str(tr.events())


def test_user_pause_stops_sampling():
    tr = ActivityTracker(True, True, idle_fn=lambda: 0, app_fn=lambda: "chrome")
    tr.paused_by_user = True; tr.sample(5)
    assert tr.active_seconds == 0 and not tr.category_seconds


def test_unsupported_platform_yields_no_fake_data():
    tr = ActivityTracker(True, False, idle_fn=lambda: None)
    tr.sample(5)
    assert tr.summary()["active_minutes"] is None and tr.events() == []


def test_manager_without_consent_has_no_tracker(uid, fake_clock):
    m = SessionManager(uid, repo.get_settings(uid), clock=fake_clock)
    m.start(None, None, 25)
    assert m.tracker is None


def test_tracked_session_saves_active_idle_and_auto_pauses(uid, fake_clock):
    consent.grant_consent(uid, idle=True, apps=True)
    s = repo.get_settings(uid)
    seq = [0, 0, 100, 100]
    pos = {"i": 0}
    def idle_fn():
        v = seq[min(pos["i"], 3)]; pos["i"] += 1; return v
    m = SessionManager(uid, s, clock=fake_clock,
                       tracker_factory=lambda st: ActivityTracker.from_settings(st, idle_fn=idle_fn, app_fn=lambda: "Slack"))
    m.start(None, None, 25)
    for _ in range(4):
        fake_clock.advance(seconds=4); m.tick()
    m.stop()
    r = repo.list_sessions_df(uid).iloc[0]
    assert r["idle_minutes"] > 0 and r["active_minutes"] > 0
    ev = repo.list_events_df(uid)
    assert "Communication" in set(ev["category"].dropna())
    assert repo.delete_activity_events(uid) > 0
    assert repo.list_events_df(uid).empty and pd.isna(repo.list_sessions_df(uid).iloc[0]["active_minutes"])
