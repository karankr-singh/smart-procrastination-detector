<<<<<<< HEAD
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
=======
# Smart Procrastination Detector

**An explainable, privacy-first productivity analytics system that helps students understand their study habits and recognize patterns linked to procrastination.**

Smart Procrastination Detector is an MCA group project built with Python. It is designed to analyze user-approved computer-activity metadata during an explicitly started study session, summarize focus and distraction patterns, and explore whether past session patterns can help estimate future procrastination risk.

The goal is not to spy on users or label them as lazy. The goal is to turn activity patterns into understandable insights that users can act on.

> **Project status:** Early-stage project. The architecture and features below describe the intended design; they should not be considered implemented until the corresponding code and tests are available.

---

## Table of contents

- [Problem statement](#problem-statement)
- [Project objectives](#project-objectives)
- [How it is intended to work](#how-it-is-intended-to-work)
- [Key features](#key-features)
- [Technology stack](#technology-stack)
- [System architecture](#system-architecture)
- [Planned project structure](#planned-project-structure)
- [Productivity scoring approach](#productivity-scoring-approach)
- [Machine-learning approach](#machine-learning-approach)
- [Privacy and responsible use](#privacy-and-responsible-use)
- [Getting started](#getting-started)
- [Development roadmap](#development-roadmap)
- [Team contributions](#team-contributions)
- [Limitations](#limitations)
- [Academic context](#academic-context)
- [License](#license)

## Problem statement

Students often intend to study or work for a set period but lose time to frequent app switching, long idle periods, or distracting applications. It can be difficult to notice these patterns consistently, and a simple screen-time total does not explain how a study session went.

This project proposes a lightweight tool that summarizes session-level activity and provides transparent, personalized feedback. It combines basic analytics with a carefully evaluated machine-learning experiment rather than assuming that every application or every idle moment has the same meaning for every person.

## Project objectives

1. **Understand study sessions:** summarize active, idle, and user-classified distracting time.
2. **Make patterns visible:** show session history, app-category usage, and switching patterns.
3. **Explain productivity metrics:** calculate a score from documented rules rather than an unexplained black box.
4. **Build a baseline first:** use simple, understandable rules before introducing machine learning.
5. **Explore risk prediction:** investigate whether labeled historical sessions can estimate the likelihood of a future distracting or interrupted session.
6. **Offer useful suggestions:** recommend realistic focus blocks and breaks based on observed patterns and user feedback.
7. **Protect user privacy:** keep tracking opt-in, limited to metadata, and easy to pause or stop.

## How it is intended to work

1. The user explicitly starts a study session and chooses or confirms application categories.
2. The tracker records limited metadata such as application category, time spent, idle duration, and app-switch counts.
3. The analytics module aggregates events into session-level metrics.
4. A transparent baseline calculates a productivity summary.
5. Once sufficient labeled data exists, an ML experiment can compare candidate models against that baseline.
6. The dashboard presents the results and practical suggestions in plain language.
7. The user can review and delete locally stored session data.

**Example:** A 45-minute session might show 30 minutes in study-related apps, 8 minutes in user-classified distracting apps, and 7 minutes idle. The dashboard could show these categories and suggest a shorter focus block next time. These numbers are illustrative only, not actual results from the current project.

## Key features

Planned capabilities include:

- **Opt-in session tracking** with visible start, pause, resume, and stop controls.
- **Activity summaries** based on application categories and session duration.
- **Idle-time analysis** and app-switch frequency.
- **Productivity score (0–100)** with a visible explanation of the factors used.
- **Session history** to help users compare their own habits over time.
- **Procrastination-risk experiment** based on historical, appropriately labeled sessions.
- **Personalized focus and break suggestions** informed by session history and user feedback.
- **Interactive dashboard** with charts, summaries, and trends.
- **Local data storage** with controls for reviewing and deleting collected records.

These are planned features and will be marked as implemented only after development and testing.

## Technology stack

| Technology | Intended use |
|---|---|
| Python 3.12 | Main programming language |
| Pandas and NumPy | Data processing and numerical analysis |
| psutil and supported Windows APIs | Limited system and foreground-application metadata, where available |
| scikit-learn | Baselines, model training, and evaluation |
| SQLite | Local session and event storage |
| SQLAlchemy | Database access and schema management |
| Streamlit | Interactive dashboard |
| Plotly | Charts and visual analytics |
| pytest | Automated tests |

The implementation may change as the project develops. Platform-specific tracking will be isolated so that unsupported APIs do not silently produce misleading results.

## System architecture

```text
User starts a session
        |
        v
Opt-in activity tracker
        |
        v
Minimal event metadata
        |
        v
Validation and feature extraction
        |
        v
SQLite session storage
        |
        v
Productivity analytics and rule-based baseline
        |
        +------------------------------+
        |                              |
        v                              v
Historical session analysis      ML evaluation
        |                              |
        +---------------+--------------+
                        |
                        v
           Recommendations and insights
                        |
                        v
              Streamlit + Plotly UI
```

The architecture separates tracking, analytics, storage, machine learning, recommendations, and presentation. This makes the project easier to test and helps keep data collection separate from analysis.

## Planned project structure

The following structure is the intended layout for the codebase as development progresses:

```text
smart-procrastination-detector/
├── app/
│   ├── tracker/           # Opt-in activity and idle-time metadata
│   ├── analytics/         # Session metrics and feature extraction
│   ├── ml/                # Training, evaluation, and inference
│   ├── recommendations/   # Focus and break suggestions
│   ├── database/          # SQLite schema and data-access functions
│   └── dashboard/         # Streamlit interface
├── data/
│   ├── raw/               # Local-only data; do not commit personal logs
│   └── processed/         # Local-only derived datasets
├── models/                # Locally generated model artifacts
├── tests/                 # Unit and integration tests
├── docs/                  # Design notes and project documentation
├── main.py                # Application entry point
├── requirements.txt       # Python dependencies
├── .env.example           # Example configuration
├── .gitignore
└── README.md
```

## Productivity scoring approach

The proposed productivity score will be a **descriptive indicator**, not an objective measurement of a person's worth or effort. A first version may combine:

- proportion of session time in user-approved focus categories;
- proportion of time in user-classified distracting categories;
- idle-time proportion; and
- app-switch frequency, interpreted cautiously.

Before a score is used, the team will document the formula, define how missing data is handled, and test edge cases. Weights should be configurable or clearly justified. The dashboard should show the factors behind a score so that users can interpret it instead of treating it as a definitive judgment.

## Machine-learning approach

Machine learning is an experimental component, not a promise that the system can accurately read a person's intentions.

### Proposed workflow

1. Define a clear prediction target and a labeling protocol before training.
2. Build session-level features from permitted metadata.
3. Start with a rule-based baseline.
4. Compare suitable models such as Logistic Regression, Random Forest, and Gradient Boosting.
5. Use held-out sessions or time-based splits to reduce data leakage.
6. Report precision, recall, F1-score, a confusion matrix, class balance, and relevant limitations.
7. Compare results with the baseline and avoid making claims unsupported by evaluation.

A model should only be trained when enough suitable labeled data is available. Synthetic data may help test code and the pipeline, but it cannot demonstrate real-world predictive performance. Any prediction should be presented as an uncertain estimate, not a diagnosis or definitive statement about user intent.

## Privacy and responsible use

Privacy is a core design requirement.

- Tracking must be **off by default** and require an explicit user action to begin.
- The user should be able to pause or stop a session at any time.
- Collect only the metadata needed for the stated functionality.
- Do **not** record raw keystrokes, passwords, private messages, clipboard contents, screenshots, or document text.
- Prefer application categories over full URLs or detailed browsing histories.
- Keep personal activity logs, local databases, credentials, and generated model files out of version control.
- Provide a clear way to review and delete locally stored data.
- Explain what is collected, why it is collected, and how it is used.
- Do not use the score to rank, punish, or make high-stakes decisions about people.

## Getting started

The repository is currently documentation-first. Once the initial application files and dependency list are added, the intended Windows setup is:

1. Install Python 3.12.
2. Clone the repository and open it in VS Code.
3. Create and activate a virtual environment in PowerShell:

   ```powershell
   py -3.12 -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

4. Install the project dependencies after `requirements.txt` is available:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Follow the run instructions that will be added once the application entry point and dashboard are implemented.

**Note:** The commands above describe the planned setup. They may not run yet while this repository contains only the README.

## Development roadmap

- [ ] **Milestone 1 — Foundation:** configuration, package layout, dependency management, and tests.
- [ ] **Milestone 2 — Data layer:** SQLite schema, session records, and data-retention controls.
- [ ] **Milestone 3 — Tracking:** opt-in start/pause/stop controls and limited metadata collection.
- [ ] **Milestone 4 — Analytics:** session aggregation, focus/distraction summaries, and explainable scoring.
- [ ] **Milestone 5 — Baseline:** rule-based classifications and user feedback.
- [ ] **Milestone 6 — ML experiment:** dataset preparation, labeling protocol, model comparison, and evaluation.
- [ ] **Milestone 7 — Recommendations:** personalized focus-block and break suggestions.
- [ ] **Milestone 8 — Dashboard:** Streamlit interface, Plotly charts, session history, and summaries.
- [ ] **Milestone 9 — Validation and delivery:** tests, privacy review, documentation, demonstration, and MCA presentation.

## Team contributions

For a two-person team, responsibilities can be divided as follows and adjusted as implementation progresses.

**Team member A — Tracking, analytics, and ML**
- Activity metadata and session feature extraction
- Productivity metrics and transparent scoring
- Dataset preparation, baseline, and ML evaluation
- Recommendation logic and experiment reporting

**Team member B — Database and application**
- SQLite schema and data-access layer
- Session controls and configuration
- Streamlit dashboard and Plotly visualizations
- Integration, usability, and application testing

**Shared responsibilities**
- Privacy and responsible-use review
- Requirements and research methodology
- Integration testing, documentation, and final presentation

## Limitations

- Application-category rules may not reflect what a person is actually doing in an application.
- Idle time does not necessarily mean wasted time; a person may be reading, thinking, or working offline.
- App-switching alone is not proof of procrastination.
- Model quality depends on the amount, quality, and representativeness of labeled data.
- Tracking capabilities can vary by operating system and desktop environment.
- Productivity scores and predictions can be wrong and should be interpreted as supportive feedback.

## Academic context

This project is being developed as an MCA group project to explore Python application development, data processing, productivity analytics, database design, dashboarding, and responsible machine-learning evaluation.

The team intends to document the methodology, assumptions, experiments, results, and limitations transparently. No performance results are claimed until the system has been implemented and evaluated.
>>>>>>> 2cf90f4f13d729c3b1f1ba36dce589e1cbbc9b77
