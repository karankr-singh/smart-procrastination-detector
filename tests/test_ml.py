import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analytics import service as svc
from ml import procrastination_model as ml


def test_insufficient_data_gives_no_predictions(uid):
    snap = svc.load_snapshot(uid)
    rep = ml.train_and_evaluate(ml.build_dataset(snap.tasks, snap.sessions))
    assert rep.status == "insufficient_data" and rep.predictions is None and "Not enough" in rep.message


def _fake_dataset(n, labels, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({f: rng.normal(size=n) for f in ml.FEATURES})
    df["task_id"], df["title"] = range(n), "t"
    df["deadline"] = pd.date_range("2026-01-01", periods=n, freq="D")
    df["late"], df["is_open"] = labels, False
    return df


def test_noise_labels_are_not_validated_and_hide_predictions():
    rng = np.random.default_rng(1)
    ds = _fake_dataset(80, rng.integers(0, 2, 80).astype(float))
    open_rows = _fake_dataset(5, [np.nan] * 5, 2); open_rows["is_open"] = True; open_rows["task_id"] += 1000
    rep = ml.train_and_evaluate(pd.concat([ds, open_rows], ignore_index=True))
    assert rep.status in ("not_validated", "validated")
    if rep.status == "not_validated":
        assert rep.predictions is None
    assert rep.metrics and set(rep.metrics) == {"precision", "recall", "f1"} and rep.baseline and len(rep.confusion) == 2


def test_signal_is_detected_with_time_split():
    n = 100
    ds = _fake_dataset(n, [0.0] * n)
    rng = np.random.default_rng(3)
    ds["late"] = (ds["progress_ratio"] + rng.normal(0, .3, n) > 0).astype(float)
    rep = ml.train_and_evaluate(ds)
    assert rep.split["train_until"] < rep.split["test_from"]           # strictly time-ordered
    assert rep.status == "validated" and rep.metrics["f1"] > rep.baseline["f1"]
    assert rep.importances[0][0] == "progress_ratio"


def test_class_imbalance_warning():
    labels = [1.0] * 9 + [0.0] * 71
    rep = ml.train_and_evaluate(_fake_dataset(80, labels))
    assert rep.imbalance_warning or rep.status == "insufficient_data"
    assert rep.limitations


def test_seeded_dataset_builds_without_leakage_columns(tmpdb):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.seed_demo import seed
    uid = seed()
    snap = svc.load_snapshot(uid)
    ds = ml.build_dataset(snap.tasks, snap.sessions)
    assert "postponement_count" not in ds.columns and "extension_count" not in ds.columns
    assert ds["late"].notna().sum() >= ml.MIN_LABELLED
    rep = ml.train_and_evaluate(ds)
    assert rep.status in ("validated", "not_validated")
