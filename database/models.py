"""SQLAlchemy models. Datetimes are naive local time. Minutes are floats so short sessions stay accurate."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    preferred_study_start: Mapped[str] = mapped_column(String(5), nullable=False, default="18:00")
    preferred_study_end: Mapped[str] = mapped_column(String(5), nullable=False, default="21:00")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    __table_args__ = (CheckConstraint("daily_goal_minutes BETWEEN 10 AND 1000", name="ck_user_goal"),)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#8B7CFF")
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # weekly goal; 0 = none
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_subject_user_name"),
                      Index("ix_subjects_user", "user_id"))


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="Medium")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="Pending")
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    actual_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    postponement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Schema addition (documented in README): counts edits that moved a deadline later.
    extension_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    __table_args__ = (
        CheckConstraint("priority IN ('Low','Medium','High','Urgent')", name="ck_task_priority"),
        CheckConstraint("status IN ('Pending','In Progress','Completed','Overdue')", name="ck_task_status"),
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_deadline", "deadline"),
    )


class StudySession(Base):
    __tablename__ = "study_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"))
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    planned_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    actual_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    active_minutes: Mapped[Optional[float]] = mapped_column(Float)   # NULL = not tracked
    idle_minutes: Mapped[Optional[float]] = mapped_column(Float)     # NULL = not tracked
    interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    session_status: Mapped[str] = mapped_column(String(14), nullable=False, default="Running")
    __table_args__ = (
        CheckConstraint("session_status IN ('Running','Completed','Stopped Early','Abandoned','Manual')",
                        name="ck_session_status"),
        Index("ix_sessions_user_start", "user_id", "start_time"),
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)   # active|idle|category|interruption|auto_pause
    category: Mapped[Optional[str]] = mapped_column(String(24))
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    __table_args__ = (Index("ix_events_session", "session_id"),)


class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    study_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    active_minutes: Mapped[Optional[float]] = mapped_column(Float)
    task_completion_rate: Mapped[Optional[float]] = mapped_column(Float)
    productivity_score: Mapped[Optional[float]] = mapped_column(Float)   # rolling 7-day score ending on `date`
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_user_date"),)


class UserSetting(Base):
    __tablename__ = "user_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(60), nullable=False)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    __table_args__ = (UniqueConstraint("user_id", "setting_key", name="uq_setting_user_key"),)
