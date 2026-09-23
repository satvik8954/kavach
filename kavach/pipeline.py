"""The two-stage pipeline, plus a monitor for live call transcripts."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from .classifier import ScamClassifier
from .explainer import Explainer, TemplateExplainer
from .rules import Signal, rule_score, scan

THRESHOLD = 0.5


@dataclass
class Verdict:
    is_scam: bool
    score: float
    model_score: float
    rule_score: float
    scam_type: str | None
    signals: list[Signal] = field(default_factory=list)
    title: str | None = None
    reasons: list[str] = field(default_factory=list)
    alert: str | None = None
    latency_ms: float = 0.0


class Kavach:
    def __init__(self, classifier: ScamClassifier | None = None,
                 explainer: Explainer | None = None, lang: str = "en",
                 threshold: float = THRESHOLD) -> None:
        self.classifier = classifier or ScamClassifier.load_or_train()
        self.explainer = explainer or TemplateExplainer()
        self.lang = lang
        self.threshold = threshold

    def score(self, text: str) -> tuple[float, float, float, list[Signal]]:
        signals = scan(text)
        r = rule_score(signals)
        m = self.classifier.scam_probability(text)
        # The model decides on its own; strong rule evidence can push a borderline
        # case over the line, but rules alone never flag a message the model is
        # confident is safe.
        combined = max(m, 0.5 * m + 0.5 * r)
        return combined, m, r, signals

    def _scam_type(self, text: str, signals: list[Signal]) -> str:
        # Trust the type model when it is sure; otherwise go with the strongest rule.
        guess, confidence = self.classifier.scam_type_with_confidence(text)
        if confidence < 0.35 and signals:
            return max(signals, key=lambda s: s.weight).scam_type
        return guess

    def analyse(self, text: str) -> Verdict:
        start = time.perf_counter()
        combined, m, r, signals = self.score(text)
        verdict = Verdict(is_scam=combined >= self.threshold, score=combined,
                          model_score=m, rule_score=r, scam_type=None, signals=signals)
        if verdict.is_scam:
            # Stage 2 only runs on a flag.
            verdict.scam_type = self._scam_type(text, signals)
            exp = self.explainer.explain(text, verdict.scam_type, signals, self.lang)
            verdict.title, verdict.reasons, verdict.alert = exp.title, exp.reasons, exp.alert
        verdict.latency_ms = (time.perf_counter() - start) * 1000
        return verdict


class CallMonitor:
    """Feeds a live call transcript to Kavach one utterance at a time.

    Scams build up over a call, so each check looks at a rolling window of the
    last few utterances. The alert fires once, the first time the window
    crosses the threshold, while the call is still going.

    Taking over the screen mid-call is disruptive, so calls need concrete
    evidence: at least one rule signal, or a very confident model. A model
    trained on SMS has little to go on for a short greeting and should not
    be trusted to fire on its own.
    """

    def __init__(self, kavach: Kavach, window: int = 4, model_only_bar: float = 0.85) -> None:
        self.kavach = kavach
        self.buffer: deque[str] = deque(maxlen=window)
        self.model_only_bar = model_only_bar
        self.alerted = False

    def feed(self, utterance: str) -> Verdict | None:
        self.buffer.append(utterance)
        if self.alerted:
            return None
        verdict = self.kavach.analyse(" ".join(self.buffer))
        has_evidence = bool(verdict.signals) or verdict.model_score >= self.model_only_bar
        if verdict.is_scam and has_evidence:
            self.alerted = True
            return verdict
        return None
