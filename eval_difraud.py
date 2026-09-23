"""Evaluate Kavach on the SMS domain of DIFrauD (difraud/difraud on Hugging Face).

Trains on the DIFrauD train split plus data/samples.jsonl, scores the DIFrauD
test split, and checks how many test messages nearly match a training message
once digits and URLs are normalised away (template-level leakage).

    python eval_difraud.py            # downloads the split files on first run
    python eval_difraud.py -v         # also list misclassified messages
"""

import argparse
import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from eval import metrics
from kavach.classifier import ScamClassifier, load_samples
from kavach.pipeline import Kavach

DIR = Path(__file__).resolve().parent / "data" / "difraud_sms"
URL = "https://huggingface.co/datasets/difraud/difraud/resolve/main/sms/{split}.jsonl"
NEAR = 0.9  # cosine similarity of normalised char n-grams counted as a near match

_URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b\S+\.(com|co\.uk|net|org|in|biz|info)\b\S*)", re.I)


def load_split(split: str) -> list[dict]:
    path = DIR / f"{split}.jsonl"
    if not path.exists():
        DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL.format(split=split), path)
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [{"label": "scam" if r["label"] == 1 else "safe", "text": r["text"]} for r in rows]


def normalise(text: str) -> str:
    text = _URL_RE.sub(" URL ", text.lower())
    text = re.sub(r"\d+", "0", text)
    text = re.sub(r"[^a-z0 ]+", " ", text.replace("URL", "url"))
    return " ".join(text.split())


def near_matches(train: list[str], test: list[str]) -> tuple[list[bool], list[bool], list[float]]:
    """For each test text: exact match after normalising, near match, best similarity."""
    tr, te = [normalise(t) for t in train], [normalise(t) for t in test]
    exact_set = set(tr)
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit(tr + te)
    nn = NearestNeighbors(n_neighbors=1, metric="cosine").fit(vec.transform(tr))
    dist, _ = nn.kneighbors(vec.transform(te))
    sims = [1 - d[0] for d in dist]
    exact = [t in exact_set and t != "" for t in te]
    return exact, [s >= NEAR for s in sims], sims


def report(name: str, truth: list[bool], full: list[bool], model: list[bool]) -> None:
    print(f"\n{name}: {len(truth)} messages ({sum(truth)} fraud, {len(truth) - sum(truth)} safe)")
    print(f"{'':22}{'accuracy':>10}{'precision':>11}{'recall':>9}{'f1':>7}")
    for label, pred in [("Model only", model), ("Model + rules", full)]:
        m = metrics(truth, pred)
        print(f"{label:22}{m['accuracy']:>10.1%}{m['precision']:>11.1%}{m['recall']:>9.1%}{m['f1']:>7.2f}")
    m = metrics(truth, full)
    print(f"Model + rules: {m['tp']} caught, {m['fn']} missed, {m['fp']} false alarms, {m['tn']} passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="list misclassified messages")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    train, test = load_split("train") + load_samples(), load_split("test")
    print(f"Train: {len(train)} (DIFrauD sms train + {len(load_samples())} hand-labelled), "
          f"{sum(r['label'] == 'scam' for r in train)} fraud")
    kavach = Kavach(classifier=ScamClassifier().fit(train))

    truth, full, model, latencies, misses = [], [], [], [], []
    for r in test:
        t0 = time.perf_counter()
        v = kavach.analyse(r["text"])
        latencies.append((time.perf_counter() - t0) * 1000)
        truth.append(r["label"] == "scam")
        full.append(v.is_scam)
        model.append(v.model_score >= 0.5)
        if v.is_scam != truth[-1]:
            misses.append((r["label"], round(v.score, 2), r["text"]))

    report("Test split", truth, full, model)
    print(f"Latency per message: median {statistics.median(latencies):.1f} ms (laptop CPU)")

    exact, near, _ = near_matches([r["text"] for r in train], [r["text"] for r in test])
    n = len(test)
    print(f"\nLeakage check (digits -> 0, URLs -> 'url', punctuation and case dropped):")
    print(f"  identical to a training message after normalising: {sum(exact)} / {n} ({sum(exact) / n:.1%})")
    print(f"  near match (char n-gram cosine >= {NEAR}):            {sum(near)} / {n} ({sum(near) / n:.1%})")
    for label in ("scam", "safe"):
        idx = [i for i, r in enumerate(test) if r["label"] == label]
        k = sum(near[i] for i in idx)
        print(f"    {'fraud' if label == 'scam' else 'safe':5}: {k} / {len(idx)} ({k / len(idx):.1%})")

    keep = [i for i in range(n) if not near[i]]
    report("Test split without near matches", [truth[i] for i in keep],
           [full[i] for i in keep], [model[i] for i in keep])

    if misses and args.verbose:
        print("\nMisclassified:")
        for label, score, text in misses:
            print(f"  [{label}, score {score}] {' '.join(text.split())[:110]}")


if __name__ == "__main__":
    main()
