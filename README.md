# Kavach — on-device scam shield

**Kavach warns you about a scam call while it is still happening, before the money moves. Everything runs on the phone, and nothing is ever uploaded.**

Built for the iQOO Hackathon 2026 (Hyderabad City Battle), FinTech & Commerce track.

```
CALLER  Hello, am I speaking with Mr. Rao?
  USER  Yes, who is this?
CALLER  This is Inspector Rajesh Verma from Mumbai Cyber Crime branch.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠  KAVACH ALERT, MID-CALL: Fake police / 'digital arrest' scam
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Claims police, CBI, customs or court action against you.

  🔊 జాగ్రత్త: ఇది మోసం కావచ్చు. డబ్బు పంపవద్దు. OTP లేదా PIN ఎవరికీ చెప్పవద్దు.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CALLER  A FedEx parcel booked with your Aadhaar was seized at customs...
```

The alert fires three lines before the caller asks for money.

## The problem

UPI collect-request traps, fake KYC messages and "digital arrest" calls work because the victim decides under pressure, during a live call. Cloud-based protection can't help at that moment:

- **Privacy.** Nobody will stream their call audio and SMS inbox to a server.
- **Latency.** A warning that arrives after the call has ended is too late.
- **Coverage.** The people who get targeted most often have patchy networks.

So the detection has to run on the phone itself, and the iQOO 15's Snapdragon NPU makes that practical.

## How it works

Two stages. A cheap check runs on everything, and the expensive one runs only when something is flagged.

```
 SMS / call audio
        │
        ▼
 ┌──────────────┐   on-device speech-to-text (Whisper Tiny, in the Android build)
 │   Capture    │
 └──────┬───────┘
        ▼
 ┌──────────────┐   Stage 0: instant regex signals
 │    Rules     │   PIN-to-receive, OTP request, secrecy demand, authority threat…
 └──────┬───────┘
        ▼
 ┌──────────────┐   Stage 1: small classifier, runs on EVERY message and utterance
 │  Classifier  │   prototype: TF-IDF + logistic regression (~1–3 ms)
 └──────┬───────┘   phone: distilled MobileBERT on the NPU
        │ flagged?
        ▼
 ┌──────────────┐   Stage 2: runs ONLY on a flag
 │  Explainer   │   names the scam type, gives reasons, alert in en / hi / te
 └──────┬───────┘   phone: Gemma 2B quantised for the NPU
        ▼
   Full-screen alert + spoken warning, mid-call
```

For calls, a rolling window over the last few utterances is checked as the call goes on. A mid-call alert needs **concrete evidence** (at least one rule signal, or a very confident model), because taking over someone's screen by mistake is how a safety app gets uninstalled.

## Try it

```bash
pip install -r requirements.txt

python demo.py --samples                                   # check some example messages
python demo.py --call data/calls/digital_arrest.txt        # replay a scam call
python demo.py --call data/calls/digital_arrest.txt --lang te
python demo.py --call data/calls/bank_reminder.txt         # a real bank call: no alert
python demo.py "Enter your UPI PIN to receive Rs 5000 cashback"

python eval.py -v                                          # cross-validated accuracy
python eval.py --data data/spam_ham_india.csv -v          # same, on a real spam/ham CSV
python -m pytest -q                                        # tests
```

No network calls are made anywhere in the pipeline.

## Results so far

### Hand-labelled set

5-fold cross-validation on 110 hand-labelled Indian messages (45 scam, 65 safe). Every message is scored by a model that never saw it during training.

| | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| Model only | 94.5% | 93.3% | 93.3% | 0.93 |
| **Model + rules** | **95.5%** | **93.5%** | **95.6%** | **0.95** |

This set is small and was written by hand from well-known scam patterns, so treat it as a sanity check, not a benchmark.

### Indian Telecom SMS Spam Collection (real messages)

`python eval.py --data data/spam_ham_india.csv -v`: 2,267 rows, of which 2,063 remain after dropping duplicates and one empty row (736 spam, 1,327 ham). Duplicates are dropped so the same text can't be in both a training fold and a test fold. 5-fold cross-validation, retraining the model on this corpus in each fold:

| | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| Model only | 99.4% | 99.7% | 98.6% | 0.99 |
| Model + rules | 99.4% | 99.7% | 98.6% | 0.99 |

That's 726 of 736 spam caught, 10 missed and 2 false alarms. Median latency is 2.5 ms per message on a laptop CPU.

**Read these numbers carefully:**

- **This dataset labels promotional spam as spam, not only fraud.** Most of its "spam" is telecom, retail and loan marketing ("FREE 2GB data", "Diwali offers"), which is easy to separate from personal chat. A high score here shows the pipeline separates marketing from chat. It does **not** show that it detects fraud.
- **The labels are noisy.** Most of the 12 errors are labelling problems: fragments like "https" and "Cart on" marked ham, a real OTP message and TRAI/RBI anti-fraud advisories marked spam. The "ham" also includes several WhatsApp stock-tip group chats that look like investment scams.
- **The rules add nothing measurable here**, because the classifier already catches the marketing. On this corpus, rules matter because they must *not* fire on ordinary messages: in a live call, one rule signal counts as evidence for a full-screen alert.
- **The model the demo ships does not transfer yet.** Trained only on the 110 hand-labelled messages and tested on this corpus, it flags **24% of real ham** (318 of 1,327, including "Not feeling well"). It catches only 10.5% of the spam, which is mostly expected because the spam is marketing, not fraud. Before this model is used on real inboxes it needs more real safe messages in training.

**Rule fixes from this evaluation.** Checking where each rule fired on real messages turned up four false triggers, and all four are fixed:
- `card_details` fired on everyday chat ("I am changing my password"). It now needs a request to hand the password over.
- `pin_to_receive` matched "pin" inside other words in shop ads.
- `pay_to_withdraw` fired on legitimate "recharge and activate" telecom offers.
- `too_good` fired on a rice brand ("Fortune Rozana") and on "guaranteed delivery".

After the fixes, no rule fires on any ham message in the corpus. Every hand-labelled scam that had a rule signal still has one, and the hand-labelled results are unchanged.

## What's in this repo

```
kavach/
  rules.py        Stage 0: evidence signals, each with a plain-language reason
  classifier.py   Stage 1: scam / safe model and scam-type model
  explainer.py    Stage 2: template explainer + on-device LLM hook and prompt
  pipeline.py     Kavach (two-stage pipeline) and CallMonitor (live calls)
data/
  samples.jsonl   labelled messages: English, Hindi and Hinglish
  spam_ham_india.csv  Indian Telecom SMS Spam Collection (spam / ham)
  calls/          call transcripts for the demo
demo.py           CLI demo
eval.py           cross-validated evaluation
tests/            behaviour tests, including "alert fires before the money request"
```

**Working now:** the full detection pipeline, the scam-type classifier, the call monitor, alerts in English, Hindi and Telugu, the evaluation (hand-labelled set and real SMS corpus) and the tests.

**Stubbed with a defined interface:** `LocalLLMExplainer` takes any `generate(prompt) -> str` function, so Gemma 2B drops in without touching the pipeline. Until then the template explainer is used.

## Roadmap (hackathon build on the iQOO 15)

- [ ] Android app: SMS listener, call-audio capture, foreground service, full-screen overlay alert
- [ ] Whisper Tiny for on-device streaming transcription
- [ ] Distil the classifier to MobileBERT and export it to the Snapdragon NPU
- [ ] Gemma 2B (quantised) behind `LocalLLMExplainer`
- [x] Evaluate on the Indian Telecom SMS Spam Collection (see Results; spam there includes marketing)
- [ ] Add real safe messages to training to cut false alarms on real inboxes (currently 24%)
- [ ] Evaluate on a fraud-specific corpus, such as the Hinglish scam-call dataset
- [ ] Telugu and Hindi text-to-speech for the spoken warning
- [ ] Measure latency, battery use and thermals on the device
