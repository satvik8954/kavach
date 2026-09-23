"""Stage 2: explain the flag to the user.

Only runs when stage 1 flags something, so its cost does not matter for the
always-on path. On the phone this is Gemma 2B (quantised) on the Snapdragon
NPU. The prototype ships a template explainer that works with no model at
all, plus the prompt and hook the on-device LLM plugs into.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .rules import Signal

SCAM_NAMES = {
    "digital_arrest": "Fake police / 'digital arrest' scam",
    "kyc": "Fake KYC / account-block scam",
    "upi": "UPI collect-request scam",
    "otp_theft": "OTP theft",
    "electricity": "Fake bill-disconnection scam",
    "job_task": "Fake job / task scam",
    "lottery": "Fake prize / lottery scam",
    "loan_app": "Illegal loan-app scam",
    "sextortion": "Blackmail / sextortion",
    "impersonation": "Impersonation scam",
    "courier": "Fake courier / customs scam",
    "investment": "Fake investment scam",
}

# Short, spoken-aloud warnings. Kept deliberately simple so TTS reads them clearly.
ALERTS = {
    "en": "Warning: this looks like a scam. Do not send money. Do not share any OTP or PIN.",
    "hi": "सावधान: यह धोखाधड़ी हो सकती है। पैसे न भेजें। OTP या PIN किसी को न बताएं।",
    "te": "జాగ్రత్త: ఇది మోసం కావచ్చు. డబ్బు పంపవద్దు. OTP లేదా PIN ఎవరికీ చెప్పవద్దు.",
}


@dataclass
class Explanation:
    title: str
    reasons: list[str]
    alert: str


class Explainer(Protocol):
    def explain(self, text: str, scam_type: str, signals: list[Signal], lang: str) -> Explanation: ...


class TemplateExplainer:
    """Works with no model: names the scam and cites the rule evidence."""

    def explain(self, text: str, scam_type: str, signals: list[Signal], lang: str = "en") -> Explanation:
        reasons = [s.reason for s in sorted(signals, key=lambda s: -s.weight)]
        if not reasons:
            reasons = ["The wording closely matches known scam messages."]
        return Explanation(
            title=SCAM_NAMES.get(scam_type, "Likely scam"),
            reasons=reasons[:3],
            alert=ALERTS.get(lang, ALERTS["en"]),
        )


PROMPT = """You protect a phone user in India from fraud.
Read the message or call transcript below. It has already been flagged as a
likely {scam_name}. Evidence found: {evidence}.

In at most two short sentences a worried non-technical person can follow,
explain why this is a scam and what they must not do. Reply in {language}.

Text:
\"\"\"{text}\"\"\"
"""

LANGUAGES = {"en": "English", "hi": "Hindi", "te": "Telugu"}


class LocalLLMExplainer:
    """Hook for the on-device LLM (Gemma 2B on the NPU in the Android build).

    `generate` is any function that takes a prompt and returns text, so the
    same class works with llama.cpp on a laptop or the NPU runtime on-device.
    Falls back to the template explainer if generation fails.
    """

    def __init__(self, generate: Callable[[str], str]) -> None:
        self.generate = generate
        self.fallback = TemplateExplainer()

    def explain(self, text: str, scam_type: str, signals: list[Signal], lang: str = "en") -> Explanation:
        base = self.fallback.explain(text, scam_type, signals, lang)
        prompt = PROMPT.format(
            scam_name=base.title,
            evidence="; ".join(s.name for s in signals) or "wording similarity",
            language=LANGUAGES.get(lang, "English"),
            text=text,
        )
        try:
            answer = self.generate(prompt).strip()
        except Exception:
            return base
        return Explanation(title=base.title, reasons=[answer] if answer else base.reasons, alert=base.alert)
