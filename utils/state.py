"""Streamlit session-state helpers."""
from __future__ import annotations

from typing import Optional

import streamlit as st

from database import repositories as repo
from services.session_service import SessionManager


def user_id() -> Optional[int]:
    return st.session_state.get("user_id")


def set_user(uid: int) -> None:
    st.session_state["user_id"] = uid
    st.session_state.pop("manager", None)


def manager(uid: int, settings: dict) -> SessionManager:
    """One SessionManager per browser session. Sessions left 'Running' by a previous browser session are
    closed as 'Abandoned' the first time the manager is created."""
    mgr = st.session_state.get("manager")
    if mgr is None or mgr.user_id != uid:
        repo.abandon_orphaned_sessions(uid)
        mgr = SessionManager(uid, settings)
        st.session_state["manager"] = mgr
    else:
        mgr.apply_settings(settings)
    return mgr


def peek_manager() -> Optional[SessionManager]:
    return st.session_state.get("manager")


def toast(message: str, icon: Optional[str] = None) -> None:
    st.toast(message, icon=icon)


def register_pages(pages: dict) -> None:
    st.session_state["_pages"] = pages


def page_link(name: str, label: str, icon: Optional[str] = None, **kwargs) -> None:
    page = st.session_state.get("_pages", {}).get(name)
    if page is not None:
        st.page_link(page, label=label, icon=icon, **kwargs)
