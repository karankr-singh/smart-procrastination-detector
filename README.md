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

The team intends to document the methodology, assumptions, experiments, results, and limitations transparently. No performance results are claimed until the system has been implemented and evaluated..
