"""Kavach demo.

    python demo.py "Your KYC has expired, click bit.ly/xyz"    # check one message
    python demo.py --samples                                    # run the built-in examples
    python demo.py --call data/calls/digital_arrest.txt         # replay a live call
    python demo.py --call data/calls/digital_arrest.txt --lang te
"""

import argparse
import sys
import time

from kavach.pipeline import CallMonitor, Kavach

RED, GREEN, DIM, BOLD, RESET = "\033[91m", "\033[92m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    RED = GREEN = DIM = BOLD = RESET = ""

EXAMPLES = [
    "Dear customer your KYC has expired. Your account will be blocked today. Update at http://sbi-kyc-verify.in",
    "You have a collect request of Rs 5000. Enter your UPI PIN to receive the cashback.",
    "Rs 349 debited from A/c XX2231 to Swiggy via UPI. Not you? Call 1800 123 4567.",
    "Bhaiya galti se paisa chala gaya, request accept karke PIN daal do, paisa wapas aa jayega",
    "Are we still meeting at 7 near the metro station?",
    "Your electricity will be disconnected tonight at 9:30 pm. Contact officer 8123456789 immediately.",
]


def show(text: str, v) -> None:
    if v.is_scam:
        print(f"\n{RED}{BOLD}⚠  SCAM  ({v.score:.0%}){RESET}  {DIM}{v.latency_ms:.1f} ms{RESET}")
        print(f"   {text}")
        print(f"   {BOLD}{v.title}{RESET}")
        for r in v.reasons:
            print(f"   • {r}")
    else:
        print(f"\n{GREEN}{BOLD}✓  safe   ({v.score:.0%}){RESET}  {DIM}{v.latency_ms:.1f} ms{RESET}")
        print(f"   {text}")


def replay_call(path: str, kavach: Kavach, delay: float) -> None:
    monitor = CallMonitor(kavach)
    print(f"{DIM}Replaying {path}. Everything runs locally; no network calls.{RESET}\n")
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        speaker, _, said = line.partition(":")
        print(f"{DIM}{speaker:>6}{RESET}  {said.strip()}")
        time.sleep(delay)
        if speaker.strip().upper() != "CALLER":
            continue
        v = monitor.feed(said.strip())
        if v:
            bar = "━" * 64
            print(f"\n{RED}{bar}\n  ⚠  KAVACH ALERT, MID-CALL: {v.title}\n{bar}{RESET}")
            for r in v.reasons:
                print(f"{RED}  • {r}{RESET}")
            print(f"\n{BOLD}  🔊 {v.alert}{RESET}")
            print(f"{RED}{bar}{RESET}\n")
            time.sleep(delay)
    if not monitor.alerted:
        print(f"\n{GREEN}{BOLD}✓ Call ended. No scam detected.{RESET}")


def main() -> None:
    p = argparse.ArgumentParser(description="Kavach on-device scam detection demo")
    p.add_argument("text", nargs="?", help="a message to check")
    p.add_argument("--samples", action="store_true", help="run the built-in examples")
    p.add_argument("--call", help="replay a call transcript file")
    p.add_argument("--lang", default="en", choices=["en", "hi", "te"], help="language of the alert")
    p.add_argument("--delay", type=float, default=0.8, help="seconds between call lines")
    args = p.parse_args()

    kavach = Kavach(lang=args.lang)
    if args.call:
        replay_call(args.call, kavach, args.delay)
    elif args.text:
        show(args.text, kavach.analyse(args.text))
    else:
        for t in EXAMPLES:
            show(t, kavach.analyse(t))
        print()


if __name__ == "__main__":
    main()
