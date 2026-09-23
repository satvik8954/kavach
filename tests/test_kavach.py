from kavach.pipeline import CallMonitor, Kavach
from kavach.rules import scan

k = Kavach()


def test_upi_pin_to_receive_is_flagged():
    v = k.analyse("Accept the collect request and enter your UPI PIN to receive Rs 5000 cashback.")
    assert v.is_scam
    assert any(s.name == "pin_to_receive" for s in v.signals)


def test_normal_bank_debit_is_safe():
    assert not k.analyse("Rs 349 debited from A/c XX2231 to Swiggy via UPI. Not you? Call 1800 123 4567.").is_scam


def test_legit_otp_does_not_trigger_otp_rule():
    assert not any(s.name == "otp_request" for s in scan("123456 is your OTP. Never share this code with anyone."))


def test_personal_message_is_safe():
    assert not k.analyse("Can you pick up milk and bread on the way back?").is_scam


def test_flag_includes_explanation_and_alert():
    v = k.analyse("This is CBI. You are under digital arrest. Do not disconnect the call or tell anyone.")
    assert v.is_scam and v.title and v.reasons and v.alert


def test_telugu_alert():
    v = Kavach(lang="te").analyse("Your KYC expired, account blocked today. Share the OTP to verify.")
    assert v.is_scam and "OTP" in v.alert and "జాగ్రత్త" in v.alert


def _replay(path):
    monitor = CallMonitor(Kavach())
    for line in open(path, encoding="utf-8"):
        speaker, _, said = line.partition(":")
        if speaker.strip() == "CALLER" and monitor.feed(said.strip()):
            return True
    return False


def test_scam_call_alerts_before_the_money_request():
    monitor = CallMonitor(Kavach())
    lines = [l.partition(":")[2].strip() for l in open("data/calls/digital_arrest.txt", encoding="utf-8")
             if l.startswith("CALLER")]
    fired_at = next(i for i, l in enumerate(lines) if monitor.feed(l))
    assert fired_at < len(lines) - 1, "alert must fire before the final 'transfer your savings' line"


def test_legit_bank_call_does_not_alert():
    assert not _replay("data/calls/bank_reminder.txt")
