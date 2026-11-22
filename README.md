# Smart Procrastination Detector (SPD)

A local, privacy-first Python app that helps students understand their study habits: focus timer, tasks, subjects,
transparent productivity scoring, explainable procrastination indicators, recommendations and an optional,
strictly-validated ML experiment. Built with **Python 3.12, Streamlit, SQLite/SQLAlchemy, Pandas, Plotly, scikit-learn**.

Everything is stored in one SQLite file on your computer. Nothing is sent anywhere.

## Install and run (Windows / macOS / Linux)

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

First launch asks you to create a local profile (or load a **synthetic** demo profile with 12 weeks of generated data).
Run `python scripts/seed_demo.py` to add the demo profile from the command line. Run tests with `pytest`.

Dark theme is the default look; switch to light from the Streamlit menu (top-right) > Settings > Theme. Both palettes are defined in `.streamlit/config.toml` and `components/theme.py`.

## What is in the app

| Page | What it does |
|---|---|
| Dashboard | Score ring with component breakdown, today/week/tasks stats, current session, weekly trend, subject split, recent sessions, personalised insights |
| Focus Workspace | Pomodoro timer (start/pause/resume/stop, custom lengths, long break cycle), subject/task link, interruption logging, tracking status, manual session logging |
| Tasks | Create/edit/delete/complete, deadlines, priorities, estimates, postpone, overdue + repeatedly-postponed detection, filter/sort/search |
| Subjects | Colours, weekly goals, progress per subject |
| Analytics | Trends, calendar heat-map, subject comparison, task charts, focus-by-hour with low-focus periods, procrastination indicators, suggestions, experimental ML |
| Reports | Daily/weekly/monthly reports, CSV and PDF export |
| Settings | Profile, timer, **privacy/consent**, notifications, data viewer/editor, export, backup, delete-all, reset |

## How the productivity score works (documented formula)

Rolling 7-day window. Each part is normalised to 0-1, then weighted:

| Component | Weight | Measures |
|---|---|---|
| Task completion | 35 | completed / tasks that were due or finished in the window |
| Focus | 30 | active / (active + idle) for tracked sessions; otherwise the proxy min(actual / planned, 1). Weighted by minutes |
| Goal progress | 20 | minutes studied / (daily goal x days), capped at 1 |
| Consistency | 15 | share of days reaching at least 50% of the daily goal |

* **Missing data:** a part with no data is left out and the remaining weights rescale to 100, so missing data is never counted as zero. No data at all gives no score.
* **Zero-division** is guarded everywhere; days before you started using the app are not counted.
* The score is a reflection aid, never a scientific or psychological diagnosis. The UI shows each component's value, weight and explanation.
* Code: `analytics/scoring.py` (the module docstring is the formula). Scores are pure functions of stored records, so they are reproducible.

## Procrastination indicators and recommendations

`analytics/procrastination.py` produces indicators with four parts: **observed pattern, supporting data, possible explanation, suggested improvement** (postponed tasks, deadline extensions, long gaps, sessions ending early, interruptions, plan vs actual, underestimates). Thresholds are named constants. They are behavioural observations, not diagnoses.

`analytics/recommendations.py` only emits a recommendation when recorded data supports it, always states *why*, and can be dismissed (restorable in Analytics).

## Privacy and tracking

* **Off by default.** Needs explicit consent (Settings > Privacy), shows status in the sidebar and Focus page, can be paused/stopped any time, and recorded activity can be deleted.
* Measures only: seconds since last input (idle) and the **category** of the foreground app. The app name is mapped to a category in memory and never stored.
* Never collects keystrokes, passwords, messages, screenshots, document contents, window titles or clipboard.
* Tracking only runs during a focus session. Idle past your threshold auto-pauses the session.
* Platform support: Windows (ctypes `GetLastInputInfo` + foreground process), macOS (`ioreg` / `osascript`), Linux (idle via `xprintidle` if installed). If unsupported, the app records nothing and says so; it never invents values. Use Settings > Privacy > Test detection on your machine.

## Optional ML experiment (`ml/`)

Predicts which open tasks may end up **late**. Label = observed (completed after deadline, or open and past it); no synthetic labels. Features are taken at the task's midpoint to avoid peeking at the outcome; postponement/extension counts are excluded because they can't be time-sliced.
Safeguards: needs 40+ labelled tasks with 8+ per class; time-ordered train/test split; model chosen by time-series CV on training data only (Logistic Regression, Random Forest, Gradient Boosting); must beat a majority-class baseline on held-out tasks; precision/recall/F1, confusion matrix, feature importances and limitations are shown; **unvalidated models never show predictions**. Core features do not depend on this module.

## Architecture

```
app.py              entry point, navigation, sidebar status
pages/              one module per page (render())
database/           models.py (SQLAlchemy), db.py (engine, transactions, migrations, backup), repositories.py
services/           timer.py (pure Pomodoro logic), session_service.py (timer+tracker+DB), export_service.py (CSV/ZIP/PDF)
tracking/           consent.py, idle.py, apps.py, tracker.py
analytics/          metrics.py, scoring.py, procrastination.py, recommendations.py, service.py
ml/                 procrastination_model.py
components/         theme.py (design tokens + CSS), widgets.py, insights.py
utils/              validation.py, formatting.py, state.py
scripts/seed_demo.py  synthetic demo data (clearly labelled)
tests/              59 automated tests
```

### Database
Tables: `users, subjects, tasks, study_sessions, activity_events, daily_analytics, user_settings`, with primary/foreign keys (enforced via `PRAGMA foreign_keys=ON`), CHECK constraints and indexes. Input is validated before every write; related changes use one transaction; errors surface as friendly messages.

Deviations from the spec schema (deliberate):
* `tasks.extension_count` added so "frequent deadline extensions" is measurable separately from postponements.
* Minute columns are floats so short sessions stay accurate; `active_minutes`/`idle_minutes` are NULL when tracking was off (never zero-filled).
* Timer lengths, consent, idle threshold, notification prefs and dismissed suggestions are stored in `user_settings`.

**Schema updates:** version stored in `PRAGMA user_version`; add a function to `MIGRATIONS` in `database/db.py` and bump `SCHEMA_VERSION` (see the module docstring).

### Behaviour notes
* A session shorter than 10 seconds is treated as an accidental start and discarded.
* A session left running when the browser/app closes is saved as `Abandoned` with the minutes recorded at the last 30-second heartbeat.
* "Postpone" (explicit action) increments `postponement_count`; editing a deadline later increments `extension_count`.
* Daily aggregates are cached in `daily_analytics`; the score stored there is the rolling 7-day score ending that day.

## Testing
`pytest` runs 59 tests: validation, database/constraints/persistence, timer and session logic with a fake clock, tracking consent, scoring (reproducibility, missing data, zero division), analytics, ML evaluation guards, exports, an end-to-end workflow, and headless rendering of every page (populated and empty).

## Honest status
* Implemented and tested here: everything in the table above.
* Verified headlessly (Streamlit AppTest) that every page renders without errors; the visual design was not checked in a real browser during development, so please review spacing/colours on your screen and tell me what to adjust.
* Windows/macOS idle and app-category detection could not be exercised in the Linux build environment; the logic is unit-tested with injected samples.
* Not included (non-code deliverables): GitHub repository, project report, PPT, viva notes and the team-contribution log. These must describe your actual work; see below.

## Team contributions (fill in with real information)
| Member | Modules owned | What they actually did |
|---|---|---|
| | | |
