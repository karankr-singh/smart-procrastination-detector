"""Renders every page headlessly (Streamlit AppTest) on seeded and empty databases."""
import pytest
from streamlit.testing.v1 import AppTest

PAGES = ["dashboard", "focus", "tasks", "subjects", "analytics_page", "reports", "settings_page"]
SCRIPT = '''
import sys; sys.path.insert(0, r"{root}")
import streamlit as st
import database.db as db
db.configure(r"{db}")
from database import repositories as repo
from components import theme
theme.inject()
if "user_id" not in st.session_state:
    users = repo.list_users()
    if users: uid = users[0]["id"]
    elif {seeded}:
        from scripts.seed_demo import seed
        uid = seed()
    else: uid = repo.create_user("Empty")
    st.session_state["user_id"] = uid
from utils import state
uid = st.session_state["user_id"]
state.manager(uid, repo.get_settings(uid)); state.register_pages({{}})
import pages.{page} as m
m.render()
'''


@pytest.mark.parametrize("seeded", [True, False])
def test_pages_render(tmp_path, seeded):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for page in PAGES:
        at = AppTest.from_string(SCRIPT.format(root=root, db=tmp_path / "ui.sqlite3", seeded=seeded, page=page), default_timeout=120).run()
        assert not at.exception, f"{page}: {[e.value for e in at.exception]}"
        assert not at.error, f"{page}: {[e.value for e in at.error]}"


def test_full_app_onboarding_to_dashboard(tmp_path, monkeypatch):
    from pathlib import Path
    import database.db as db
    db.configure(tmp_path / "app.sqlite3")       # app.py reuses the configured engine
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    assert not at.exception
    at.text_input[0].set_value("Ava")
    at.get("form_submit_button")[0].click()
    at.run()
    assert not at.exception
    assert any("Good" in m.value and "Ava" in m.value for m in at.markdown)
