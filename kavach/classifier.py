"""Stage 1: the fast always-on classifier.

In this prototype it is a TF-IDF + logistic regression model, which is small
(well under 1 MB) and runs in about a millisecond on a laptop. On the phone,
the same interface is backed by a distilled MobileBERT exported to the
Snapdragon NPU. The pipeline does not care which one is behind it.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

DATA = Path(__file__).resolve().parent.parent / "data" / "samples.jsonl"
MODEL = Path(__file__).resolve().parent.parent / "data" / "model.pkl"


def load_samples(path: Path = DATA) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _features() -> FeatureUnion:
    # Word n-grams catch phrasing; character n-grams survive typos and Hinglish spellings.
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
    ])


class ScamClassifier:
    def __init__(self) -> None:
        self.binary = Pipeline([
            ("features", _features()),
            ("clf", LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")),
        ])
        self.typer = Pipeline([
            ("features", _features()),
            ("clf", LogisticRegression(max_iter=2000, C=4.0)),
        ])

    def fit(self, rows: list[dict]) -> "ScamClassifier":
        texts = [r["text"] for r in rows]
        labels = [1 if r["label"] == "scam" else 0 for r in rows]
        self.binary.fit(texts, labels)
        scams = [r for r in rows if r["label"] == "scam"]
        self.typer.fit([r["text"] for r in scams], [r["type"] for r in scams])
        return self

    def scam_probability(self, text: str) -> float:
        return float(self.binary.predict_proba([text])[0][1])

    def scam_type(self, text: str) -> str:
        return str(self.typer.predict([text])[0])

    def scam_type_with_confidence(self, text: str) -> tuple[str, float]:
        probs = self.typer.predict_proba([text])[0]
        best = probs.argmax()
        return str(self.typer.classes_[best]), float(probs[best])

    def save(self, path: Path = MODEL) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load_or_train(cls, path: Path = MODEL) -> "ScamClassifier":
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f)
        model = cls().fit(load_samples())
        model.save(path)
        return model
