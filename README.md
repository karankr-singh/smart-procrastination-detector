# Smart Procrastination Detector (SPD)

<p align="center">
 <strong>Understand your study habits. Make your focus count.</strong>
 <br />
 A local, privacy-first productivity analytics app that helps students understand their study patterns through focus sessions, transparent scoring, behavioural indicators, and explainable insights.
</p>

<p align="center">
 <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12" />
 <img src="https://img.shields.io/badge/Streamlit-App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
 <img src="https://img.shields.io/badge/SQLite-Local%20Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
 <img src="https://img.shields.io/badge/scikit--learn-ML-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white" alt="scikit-learn" />
 <img src="https://img.shields.io/badge/Tests-59%20automated-brightgreen?style=for-the-badge&logo=pytest&logoColor=white" alt="59 automated tests" />
</p>

---

## What is SPD?

Procrastination is not always obvious. It can show up as repeatedly postponed tasks, interrupted focus sessions, unrealistic study plans, or inconsistent routines.

**Smart Procrastination Detector (SPD)** is a Python-based application that helps students make sense of these patterns. It brings together task and subject management, a focus timer, productivity analytics, explainable behavioural indicators, and an optional machine-learning experiment.

Instead of judging users or making assumptions about their intentions, SPD surfaces recorded patterns, explains why an insight appears, and offers practical suggestions.

> **Built around one idea: productivity should be understood, not judged.**

## Features

| Module | What it offers |
|---|---|
| **Dashboard** | Productivity score and breakdown, daily and weekly statistics, current session, subject split, recent sessions, and personalized insights |
| **Focus Workspace** | Pomodoro timer, customizable focus and break lengths, subject/task linking, interruption logging, tracking status, and manual session logging |
| **Task Management** | Create, edit, complete, and delete tasks; priorities, deadlines, estimates, postponements, overdue detection, filtering, sorting, and search |
| **Subject Management** | Subject organization, colour labels, weekly goals, and progress tracking |
| **Analytics** | Trends, calendar heatmap, subject comparisons, task charts, focus-by-hour analysis, procrastination indicators, and suggestions |
| **Reports** | Daily, weekly, and monthly reports with CSV and PDF export |
| **Privacy & Settings** | Profile and timer preferences, consent controls, notifications, data viewer/editor, export, backup, delete-all, and reset |
| **Experimental ML** | A guarded experiment that evaluates whether historical task data can help estimate which open tasks may become overdue |

## Screenshots

### Dashboard
<img width="1360" height="631" alt="Screenshot 2026-11-22 144456" src="https://github.com/user-attachments/assets/cd2cdb56-84fb-4f09-b1ba-8329132c19c6" />

### Task Management
<img width="1037" height="617" alt="Screenshot 2026-11-22 144546" src="https://github.com/user-attachments/assets/e7e8e33d-997b-4ecf-bb14-7ab9cf16877d" />

### Subject Management
<img width="1017" height="629" alt="Screenshot 2026-11-22 144618" src="https://github.com/user-attachments/assets/1daae0d5-83c1-4432-968a-f01cfa75bb5e" />

### Analytics
<img width="1132" height="632" alt="Screenshot 2026-11-22 144645" src="https://github.com/user-attachments/assets/af777112-f079-417f-9c7b-a21a4363cfa6" />

### Weekly Reports
<img width="1360" height="624" alt="Screenshot 2026-11-22 144728" src="https://github.com/user-attachments/assets/d88bb61d-84db-45b2-90e5-3b371cda5baa" />

## Explainable Productivity Score

SPD calculates a rolling **7-day productivity score** using normalized components and documented weights.

| Component | Weight |
|---|---:|
| Task completion | 35% |
| Focus | 30% |
| Goal progress | 20% |
| Consistency | 15% |

**Scoring safeguards**
- Components without sufficient data are excluded and the remaining weights are rescaled.
- Missing data is not silently treated as zero productivity.
- Zero-division cases are guarded.
- Days before a user starts using the app are not counted.
- The UI explains each component, its value, and its weight.

The score is a reflection aid, not a scientific measurement or psychological diagnosis. The implementation is in `analytics/scoring.py`.

## Behavioural Indicators & Recommendations

The analytics layer looks for observable patterns such as:
- Repeatedly postponed tasks and deadline extensions.
- Long gaps and sessions ending earlier than planned.
- Interruptions and differences between planned and actual study time.
- Repeated underestimation of task duration.

Each indicator is designed to show the observed pattern, supporting data, a possible explanation, and a suggested improvement. Recommendations are only shown when recorded activity supports them, explain their reasoning, and can be dismissed or restored.

These are behavioural observations—not diagnoses or claims about a user's intentions.

## Machine-Learning Experiment

The optional `ml/` module explores whether an open task may end up late, based on historical task records.

Candidate models include:
- Logistic Regression
- Random Forest
- Gradient Boosting

The experiment includes safeguards:
- Requires at least 40 labelled tasks, with at least 8 examples per class.
- Uses a time-ordered train/test split.
- Selects models using time-series cross-validation on training data only.
- Compares performance against a majority-class baseline on held-out tasks.
- Reports precision, recall, F1-score, confusion matrix, feature importance, and limitations.
- Does not show predictions from unvalidated models.

Labels are based on observed task outcomes; synthetic labels are not used. The ML module is experimental, and core application features do not depend on it.

## Privacy by Design

Privacy is a core design requirement.

- Activity tracking is **off by default** and requires explicit consent.
- Tracking can be paused or stopped at any time.
- Tracking runs only during a focus session.
- The app measures idle duration and the category of the foreground application.
- Application names are mapped to categories in memory and are not stored.
- No keystrokes, passwords, private messages, screenshots, document contents, window titles, or clipboard contents are collected.
- Personal records are stored locally in SQLite.
- Users can review, export, back up, and delete their stored data.

Platform-specific detection is supported where available:
- **Windows:** `GetLastInputInfo` and foreground-process detection.
- **macOS:** `ioreg` and `osascript`.
- **Linux:** idle detection through `xprintidle`, if installed.

If detection is unsupported, the application reports that limitation and records no fabricated activity values. Use **Settings → Privacy → Test detection** to check support on your machine.

## Technology Stack

| Technology | Role |
|---|---|
| Python 3.12 | Application logic |
| Streamlit | Interactive application |
| SQLite & SQLAlchemy | Local persistence and database access |
| Pandas | Data processing |
| Plotly | Interactive visualizations |
| scikit-learn | Machine-learning experiment |
| pytest | Automated testing |

## Project Structure

```text
smart-procrastination-detector/
│
├── analytics/ # Metrics, scoring, indicators, recommendations
├── components/ # Reusable UI components and theme
├── database/ # SQLAlchemy models, DB access, migrations, backups
├── docs/ # Project documentation
├── ml/ # Experimental ML model and evaluation
├── pages/ # Streamlit application pages
├── scripts/ # Utility scripts and demo-data generation
├── services/ # Timer, session, and export services
├── tests/ # Automated test suite
├── tracking/ # Consent, idle detection, app categories, tracker
├── utils/ # Validation, formatting, and state utilities
│
├── .streamlit/ # Streamlit configuration
├── app.py # Application entry point
├── config.py # Application configuration
├── requirements.txt # Python dependencies
└── pytest.ini # Pytest configuration
```

### Database notes

The SQLite database uses relational tables for users, subjects, tasks, study sessions, activity events, daily analytics, and user settings. Foreign-key enforcement, check constraints, indexes, input validation, and transactional writes help protect data integrity.

Schema changes are versioned through `PRAGMA user_version` and migrations in `database/db.py`.

## Getting Started

### Prerequisites

- Python 3.12
- Git

### 1. Clone the repository

```bash
git clone https://github.com/karankr-singh/smart-procrastination-detector.git
cd smart-procrastination-detector
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the application

```bash
streamlit run app.py
```

On first launch, create a local profile or load the clearly labelled synthetic demo profile.

### 5. Optional: Generate demo data

```bash
python scripts/seed_demo.py
```

Demo data is synthetic and is intended for exploring the application—not for claiming real-world model performance.

## Testing

Run the automated test suite:

```bash
pytest
```

The repository currently includes **59 automated tests** covering validation, database constraints and persistence, timer/session logic, tracking consent, scoring edge cases, analytics, ML evaluation safeguards, exports, end-to-end workflows, and headless page rendering.

## Limitations & Honest Status

- Windows and macOS tracking could not be exercised in the Linux development environment; platform-specific logic is unit-tested with injected samples.
- Tracking behaviour depends on operating-system support and should be tested on the target machine.
- Application categories cannot determine what a person is actually doing inside an application.
- Idle time or application switching alone is not proof of procrastination.
- ML quality depends on sufficient, representative, labelled task data.
- Visual spacing and colours should be reviewed in a real browser on the target screen.

The application features described above are implemented in the project. Platform-specific tracking and visual presentation still warrant testing on the machines and environments where the app will be used.

## The Team

Built by:

<table>
 <tr>
 <td align="center" width="50%">
 <strong>Karan Kumar Singh</strong><br />
 <a href="https://github.com/karankr-singh">@karankr-singh</a>
 </td>
 <td align="center" width="50%">
 <strong>Chirag Yadav</strong><br />
 <a href="https://github.com/chiragyadaavv">@chiragyadaavv</a>
 </td>
 </tr>
</table>


---
