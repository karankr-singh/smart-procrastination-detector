"""Experimental model: which tasks are likely to be finished late or missed?

TARGET LABEL (defensible, observed – never synthetic)
    late = 1 if a task with a deadline was completed after it, or is still open and past it; else 0.

PREDICTION POINT
    Features describe what was known halfway between task creation and its deadline, so the model can't
    peek at the outcome. For open tasks the prediction point is "now".

FEATURES
    lead_time_days, estimated_minutes, priority_rank,
    progress_ratio (minutes logged / estimate), sessions_so_far, session_completion_rate,
    interruptions_per_session, idle_share (0 when idle tracking was off),
    subject_prior_late_rate, user_prior_late_rate  (both use only tasks whose deadline had already passed).
    postponement/extension counts are intentionally excluded: they can't be sliced by time and would leak.

SAFEGUARDS
    * needs >= MIN_LABELLED labelled tasks and >= MIN_PER_CLASS of each class
    * time-ordered train/test split (oldest deadlines train, newest test)
    * model chosen by time-series cross-validation on the training part only
    * must beat a majority-class baseline on the held-out test set to be called 'validated'
    * unvalidated models never produce predictions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MIN_LABELLED = 40
MIN_PER_CLASS = 8
TEST_FRACTION = 0.30
MIN_TEST_POSITIVES = 5
MIN_F1_GAIN = 0.05
FEATURES = ["lead_time_days", "estimated_minutes", "priority_rank", "progress_ratio", "sessions_so_far",
            "session_completion_rate", "interruptions_per_session", "idle_share",
            "subject_prior_late_rate", "user_prior_late_rate"]
PRIORITY_RANK = {"Low": 0, "Medium": 1, "High": 2, "Urgent": 3}
LIMITATIONS = [
    "Trained on one person's history; it describes past habits, not a guaranteed future.",
    "Small datasets make results unstable – metrics can change a lot with a few new tasks.",
    "Task outcomes depend on things the app can't see (illness, workload, exams).",
    "Risk categories are estimates for self-reflection, not facts or diagnoses.",
]


def build_dataset(tasks: pd.DataFrame, sessions: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
    """One row per task that has a deadline; `late` is NaN for tasks whose outcome isn't known yet."""
    now = now or datetime.now()
    cols = ["task_id", "title", "deadline", "late", "is_open"] + FEATURES
    if tasks.empty:
        return pd.DataFrame(columns=cols)
    t = tasks[tasks["deadline"].notna() & tasks["created_at"].notna()].copy()
    if t.empty:
        return pd.DataFrame(columns=cols)
    t["late"] = np.where(t["status"] == "Completed", (t["completed_at"] > t["deadline"]).astype(float),
                         np.where(t["deadline"] < now, 1.0, np.nan))
    t = t.sort_values("deadline").reset_index(drop=True)
    sess = sessions[sessions["actual_minutes"] > 0] if not sessions.empty else sessions
    rows = []
    for _, r in t.iterrows():
        point = r["created_at"] + (r["deadline"] - r["created_at"]) / 2 if not pd.isna(r["late"]) else now
        g = sess[(sess["task_id"] == r["id"]) & (sess["start_time"] <= point)] if not sess.empty else sess
        n = len(g)
        logged = float(g["actual_minutes"].sum()) if n else 0.0
        est = float(r["estimated_minutes"]) if pd.notna(r["estimated_minutes"]) else np.nan
        idle_share = 0.0
        if n and g["idle_minutes"].notna().any():
            tr = g[g["idle_minutes"].notna()]
            tot = (tr["active_minutes"] + tr["idle_minutes"]).sum()
            idle_share = float(tr["idle_minutes"].sum() / tot) if tot > 0 else 0.0
        prior = t[(t["deadline"] < point) & t["late"].notna()]
        same = prior[prior["subject_id"] == r["subject_id"]] if pd.notna(r["subject_id"]) else prior.iloc[0:0]
        rows.append({
            "task_id": r["id"], "title": r["title"], "deadline": r["deadline"], "late": r["late"],
            "is_open": r["status"] != "Completed",
            "lead_time_days": max((r["deadline"] - r["created_at"]).total_seconds() / 86400, 0.0),
            "estimated_minutes": est, "priority_rank": PRIORITY_RANK.get(r["priority"], 1),
            "progress_ratio": min(logged / est, 2.0) if est and est > 0 else np.nan,
            "sessions_so_far": n,
            "session_completion_rate": float((g["session_status"] == "Completed").mean()) if n else np.nan,
            "interruptions_per_session": float(g["interruption_count"].mean()) if n else np.nan,
            "idle_share": idle_share,
            "subject_prior_late_rate": float(same["late"].mean()) if len(same) >= 2 else np.nan,
            "user_prior_late_rate": float(prior["late"].mean()) if len(prior) >= 3 else np.nan})
    return pd.DataFrame(rows, columns=cols)


@dataclass
class ModelReport:
    status: str                                   # "insufficient_data" | "not_validated" | "validated"
    message: str
    n_labelled: int = 0
    class_counts: dict = field(default_factory=dict)
    imbalance_warning: str = ""
    model_name: str = ""
    cv_f1: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    baseline: dict = field(default_factory=dict)
    confusion: Optional[list] = None
    importances: list = field(default_factory=list)
    split: dict = field(default_factory=dict)
    predictions: Optional[pd.DataFrame] = None
    limitations: list = field(default_factory=lambda: list(LIMITATIONS))


def _prep(df: pd.DataFrame, medians: Optional[pd.Series] = None):
    X = df[FEATURES].astype(float)
    medians = X.median().fillna(0.0) if medians is None else medians
    return X.fillna(medians), medians


def _models() -> dict:
    return {"Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
            "Random Forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=3, class_weight="balanced", random_state=0),
            "Gradient Boosting": GradientBoostingClassifier(random_state=0)}


def _scores(y_true, y_pred) -> dict:
    return {"precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0))}


def train_and_evaluate(dataset: pd.DataFrame) -> ModelReport:
    labelled = dataset[dataset["late"].notna()].sort_values("deadline").reset_index(drop=True)
    n = len(labelled)
    counts = {"on_time": int((labelled["late"] == 0).sum()), "late": int((labelled["late"] == 1).sum())}
    report = ModelReport("insufficient_data", "", n, counts)
    if n < MIN_LABELLED or min(counts.values()) < MIN_PER_CLASS:
        report.message = (f"Not enough labelled history: {n} tasks with a known outcome ({counts['on_time']} on time, "
                          f"{counts['late']} late). Need at least {MIN_LABELLED} tasks and {MIN_PER_CLASS} of each outcome.")
        return report
    minority = min(counts.values()) / n
    if minority < 0.2:
        report.imbalance_warning = f"Class imbalance: only {minority:.0%} of tasks are in the smaller group; metrics may be misleading."

    cut = int(n * (1 - TEST_FRACTION))
    train, test = labelled.iloc[:cut], labelled.iloc[cut:]
    y_tr, y_te = train["late"].astype(int).values, test["late"].astype(int).values
    report.split = {"train": len(train), "test": len(test), "train_until": str(train["deadline"].max().date()),
                    "test_from": str(test["deadline"].min().date()), "test_late": int(y_te.sum())}
    if len(set(y_tr)) < 2 or len(set(y_te)) < 2 or int(y_te.sum()) < MIN_TEST_POSITIVES:
        report.message = ("The newest tasks (used for testing) don't contain enough late tasks to evaluate a model fairly. "
                          "No predictions are shown.")
        report.status = "not_validated"
        return report

    X_tr, med = _prep(train)
    X_te, _ = _prep(test, med)

    cv = {}
    for name, model in _models().items():
        scores = []
        for tr_idx, va_idx in TimeSeriesSplit(n_splits=3).split(X_tr):
            if len(set(y_tr[tr_idx])) < 2 or len(set(y_tr[va_idx])) < 2:
                continue
            m = _models()[name].fit(X_tr.iloc[tr_idx], y_tr[tr_idx])
            scores.append(f1_score(y_tr[va_idx], m.predict(X_tr.iloc[va_idx]), zero_division=0))
        cv[name] = float(np.mean(scores)) if scores else 0.0
    best = max(cv, key=cv.get)
    model = _models()[best].fit(X_tr, y_tr)
    pred = model.predict(X_te)

    base = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr)
    base_scores = _scores(y_te, base.predict(X_te))
    scores = _scores(y_te, pred)
    report.model_name, report.cv_f1, report.metrics, report.baseline = best, cv, scores, base_scores
    report.confusion = confusion_matrix(y_te, pred, labels=[0, 1]).tolist()

    est = model[-1] if hasattr(model, "steps") else model
    raw = np.abs(est.coef_[0]) if hasattr(est, "coef_") else est.feature_importances_
    imp = sorted(zip(FEATURES, raw / (raw.sum() or 1)), key=lambda x: -x[1])
    report.importances = [(f, float(v)) for f, v in imp]

    if scores["f1"] >= base_scores["f1"] + MIN_F1_GAIN:
        report.status = "validated"
        report.message = (f"{best} beat the majority-class baseline on held-out, newer tasks "
                          f"(F1 {scores['f1']:.2f} vs {base_scores['f1']:.2f}). Still experimental.")
        open_rows = dataset[dataset["is_open"] & dataset["late"].isna()].copy()
        if not open_rows.empty:
            Xo, _ = _prep(open_rows, med)
            proba = model.predict_proba(Xo)[:, 1]
            open_rows["risk_score"] = proba
            open_rows["risk"] = pd.cut(proba, [-0.01, 0.33, 0.66, 1.01], labels=["Low", "Medium", "High"])
            report.predictions = open_rows[["task_id", "title", "deadline", "risk", "risk_score"]]
    else:
        report.status = "not_validated"
        report.message = (f"The best model ({best}, F1 {scores['f1']:.2f}) did not clearly beat a simple baseline "
                          f"(F1 {base_scores['f1']:.2f}) on held-out tasks, so no predictions are shown.")
    return report
