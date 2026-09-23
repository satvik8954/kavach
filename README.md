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
python -m pytest -q                                        # tests
```

No network calls are made anywhere in the pipeline.

## Results so far

5-fold cross-validation on 110 hand-labelled Indian messages (45 scam, 65 safe). Every message is scored by a model that never saw it during training.

| | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| Model only | 94.5% | 93.3% | 93.3% | 0.93 |
| **Model + rules** | **95.5%** | **93.5%** | **95.6%** | **0.95** |

Median latency is 2.5 ms per message on a laptop CPU.

**Caveat:** the dataset is small and was written by hand from well-known scam patterns, so these numbers are a sanity check, not a benchmark. The next step is evaluating on public Indian corpora (see the roadmap).

## What's in this repo

```
kavach/
  rules.py        Stage 0: evidence signals, each with a plain-language reason
  classifier.py   Stage 1: scam / safe model and scam-type model
  explainer.py    Stage 2: template explainer + on-device LLM hook and prompt
  pipeline.py     Kavach (two-stage pipeline) and CallMonitor (live calls)
data/
  samples.jsonl   labelled messages: English, Hindi and Hinglish
  calls/          call transcripts for the demo
demo.py           CLI demo
eval.py           cross-validated evaluation
tests/            behaviour tests, including "alert fires before the money request"
```

**Working now:** the full detection pipeline, the scam-type classifier, the call monitor, alerts in English, Hindi and Telugu, the evaluation and the tests.

**Stubbed with a defined interface:** `LocalLLMExplainer` takes any `generate(prompt) -> str` function, so Gemma 2B drops in without touching the pipeline. Until then the template explainer is used.

## Roadmap (hackathon build on the iQOO 15)

- [ ] Android app: SMS listener, call-audio capture, foreground service, full-screen overlay alert
- [ ] Whisper Tiny for on-device streaming transcription
- [ ] Distil the classifier to MobileBERT and export it to the Snapdragon NPU
- [ ] Gemma 2B (quantised) behind `LocalLLMExplainer`
- [ ] Evaluate on public corpora: the Indian Telecom SMS Spam Collection and the Hinglish scam-call dataset
- [ ] Telugu and Hindi text-to-speech for the spoken warning
- [ ] Measure latency, battery use and thermals on the device
