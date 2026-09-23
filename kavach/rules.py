"""Stage 0: instant rule signals.

Cheap regex checks that run before any model. They catch the obvious tells
(asking for a UPI PIN to *receive* money, OTP requests, secrecy demands) in
microseconds, and they give the explainer concrete evidence to cite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    name: str
    weight: float
    scam_type: str
    reason: str


_RULES: list[tuple[str, float, str, str, re.Pattern]] = [
    (
        "pin_to_receive",
        0.9,
        "upi",
        "Asks you to enter a UPI PIN to receive money. A PIN is only ever needed to send money.",
        re.compile(r"(pin|upi).{0,60}(receive|refund|credit|cashback|wapas)|"
                   r"(receive|refund|credit|cashback|wapas).{0,60}(pin)", re.I),
    ),
    (
        "otp_request",
        0.85,
        "otp_theft",
        "Asks you to read out or share an OTP. No bank or official will ever ask for one.",
        re.compile(r"(share|tell|read|bata|confirm).{0,40}(otp|code)|"
                   r"(otp|code).{0,40}(share|tell|read|bata|confirm)", re.I),
    ),
    (
        "secrecy",
        0.8,
        "digital_arrest",
        "Tells you not to disconnect or not to tell anyone. Real police and courts never do this.",
        re.compile(r"(do not|don'?t|mat).{0,20}(disconnect|cut|inform|tell|contact|kaat|bata)|"
                   r"keep (this|it) confidential|stay on (the )?(video|call)", re.I),
    ),
    (
        "authority_threat",
        0.7,
        "digital_arrest",
        "Claims police, CBI, customs or court action against you. This is how 'digital arrest' scams start.",
        re.compile(r"\b(arrest|warrant|cbi|narcotics|ndps|customs|money laundering|"
                   r"cyber crime|legal notice)\b", re.I),
    ),
    (
        "remote_access",
        0.85,
        "impersonation",
        "Asks you to install a screen-sharing or remote access app.",
        re.compile(r"\b(anydesk|teamviewer|quicksupport|remote access|screen ?share|\.apk)\b", re.I),
    ),
    (
        "account_block",
        0.55,
        "kyc",
        "Threatens that your account, card or connection will be blocked soon.",
        re.compile(r"(blocked|suspended|deactivated|disconnected|terminated|band ho|kaat)"
                   r".{0,40}(today|tonight|hours|immediately|aaj)|"
                   r"(today|tonight|aaj).{0,40}(blocked|suspended|disconnected|band|kaat)", re.I),
    ),
    (
        "card_details",
        0.85,
        "kyc",
        "Asks for card number, CVV, PIN or password.",
        re.compile(r"\b(cvv|card number|expiry date|password|customer id)\b", re.I),
    ),
    (
        "pay_to_withdraw",
        0.8,
        "job_task",
        "Asks you to pay a fee or deposit before you can receive winnings or earnings.",
        re.compile(r"(processing fee|registration|deposit|tax fee|recharge|pay).{0,60}"
                   r"(withdraw|claim|earnings|prize|activate)|"
                   r"(withdraw|claim).{0,60}(pay|deposit|fee)", re.I),
    ),
    (
        "suspicious_link",
        0.5,
        "kyc",
        "Contains a shortened or look-alike link.",
        re.compile(r"(bit\.ly|tinyurl|goo\.gl|http://|"
                   r"\b[a-z]+-(kyc|verify|secure|update)[a-z-]*\.(in|net|com|xyz))", re.I),
    ),
    (
        "too_good",
        0.6,
        "lottery",
        "Promises a prize, guaranteed returns or easy daily income.",
        re.compile(r"(lucky draw|you (have )?won|guaranteed|double within|"
                   r"\d+ ?percent return|daily just for|rozana)", re.I),
    ),
]


# A rule is skipped when its "unless" pattern matches. Legit OTP messages say
# "never share this code", which would otherwise look like an OTP request.
_UNLESS: dict[str, re.Pattern] = {
    "otp_request": re.compile(r"(never|do not|don'?t|not to) share|with the driver only", re.I),
}


def scan(text: str) -> list[Signal]:
    """Return every rule signal that fires on the text."""
    hits = []
    for name, weight, scam_type, reason, pattern in _RULES:
        unless = _UNLESS.get(name)
        if unless and unless.search(text) and not re.search(r"(tell|bata|read).{0,20}(otp|number|code)", text, re.I):
            continue
        if pattern.search(text):
            hits.append(Signal(name, weight, scam_type, reason))
    return hits


def rule_score(signals: list[Signal]) -> float:
    """Combine signal weights as independent evidence: 1 - prod(1 - w)."""
    remaining = 1.0
    for s in signals:
        remaining *= 1.0 - s.weight
    return 1.0 - remaining
