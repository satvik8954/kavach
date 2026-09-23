"""Evaluate Kavach with stratified cross-validation.

Every message is scored by a model that never saw it during training, so the
numbers reflect held-out performance. The dataset is small and hand-curated;
treat these as a sanity check, not a benchmark.
"""

import statistics
import sys
import time

from sklearn.model_selection import StratifiedKFold

from kavach.classifier import ScamClassifier, load_samples
from kavach.pipeline import Kavach


def metrics(y_true, y_pred):
    tp = sum(t and p for t, p in zip(y_true, y_pred))
    fp = sum((not t) and p for t, p in zip(y_true, y_pred))
    fn = sum(t and (not p) for t, p in zip(y_true, y_pred))
    tn = sum((not t) and (not p) for t, p in zip(y_true, y_pred))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"accuracy": (tp + tn) / len(y_true), "precision": precision,
            "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main() -> None:
    rows = load_samples()
    labels = [r["label"] == "scam" for r in rows]
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)

    model_only, full, truth, latencies, misses = [], [], [], [], []
    for train_idx, test_idx in folds.split(rows, labels):
        clf = ScamClassifier().fit([rows[i] for i in train_idx])
        kavach = Kavach(classifier=clf)
        for i in test_idx:
            text = rows[i]["text"]
            t0 = time.perf_counter()
            v = kavach.analyse(text)
            latencies.append((time.perf_counter() - t0) * 1000)
            model_only.append(v.model_score >= 0.5)
            full.append(v.is_scam)
            truth.append(labels[i])
            if v.is_scam != labels[i]:
                misses.append((rows[i]["label"], round(v.score, 2), text))

    print(f"Samples: {len(rows)}  ({sum(labels)} scam, {len(rows) - sum(labels)} safe), 5-fold CV\n")
    print(f"{'':22}{'accuracy':>10}{'precision':>11}{'recall':>9}{'f1':>7}")
    for name, pred in [("Model only", model_only), ("Model + rules", full)]:
        m = metrics(truth, pred)
        print(f"{name:22}{m['accuracy']:>10.1%}{m['precision']:>11.1%}{m['recall']:>9.1%}{m['f1']:>7.2f}")
    m = metrics(truth, full)
    print(f"\nModel + rules: {m['tp']} scams caught, {m['fn']} missed, "
          f"{m['fp']} false alarms, {m['tn']} safe messages passed")
    print(f"Latency per message: median {statistics.median(latencies):.1f} ms, "
          f"p95 {sorted(latencies)[int(len(latencies) * 0.95)]:.1f} ms (laptop CPU)")
    if misses and "-v" in sys.argv:
        print("\nMisclassified:")
        for label, score, text in misses:
            print(f"  [{label}, score {score}] {text[:90]}")


if __name__ == "__main__":
    main()
