# Telehealth Intake Agent

A [Guava](https://goguava.ai) voice agent for nursing home change-of-condition calls. Built in one evening at the **Peachtree Hackathon: Voice AI** (October 12, 2026) by Keomaria (Ke) Camon, LPN, founder of Esoteric Healthcare Systems.

> Fictional data only. Not for clinical use.

## The problem

When a nursing home resident has a change of condition, the nurse calls a remote telehealth NP who has never met the patient. The NP often gets a name and a complaint, with no vitals and no history. On half the data, the safe default is an ER transfer. That's a bad-input problem.

## What it does

1. **Nurse calls the telehealth line.** The agent answers and runs a structured clinical intake: caller, resident, situation, vitals, history, and request.
2. **It adapts live to acuity.** After the vitals, code scores them against fixed thresholds. Critical vitals (SpO2 < 90, SBP < 90 or > 180, HR < 50 or > 120) switch the call to **STAT mode**: the agent tells the nurse to stay with the resident, cuts to the essentials, and the case flashes STAT on the dashboard mid-call.
3. **The NP works from a live dashboard.** An SBAR summary with red flags appears as the call ends. The NP clicks **Acknowledge** and enters orders.
4. **The nurse calls back for orders.** A returning caller with pending orders gets a different call: the agent reads the NP's orders and records her read-back. The dashboard shows **Read-back confirmed**.

### Safety design

- The nurse is never told the NP "has it" until the NP actually acknowledges.
- Critical thresholds are deterministic code, not LLM judgment, so they're predictable and auditable. The LLM handles conversation; code handles safety logic.
- The agent collects and structures information only. The NP makes every clinical decision.
- Orders go by voice with read-back, never plain text.
- The resident's name is a Guava `sensitive` field, redacted from stored transcripts and recordings.

## How it works

```
Nurse phone ──> Guava Dialog System <─WebSocket─> intake_agent.py
                                                   tasks: opening → vitals → (routine | STAT) history
                                                   or, with pending orders: deliver_orders
                                                         │
                                                    cases.json (shared state, atomic writes)
                                                         │
NP browser <──── polls every 2s ──────────────── dashboard.py (localhost:5050)
```

The intake is split into Guava tasks. Between tasks, the code reads the collected fields and decides which task comes next, while the call is still live. Same phone number, three behaviors, decided at runtime.

## Run it

Requires Python 3.10+, a Guava account, API key, and phone number.

```bash
pip install guava-sdk
export GUAVA_API_KEY="gva-..."
export GUAVA_AGENT_NUMBER="+1XXXXXXXXXX"

# Terminal 1: NP dashboard (no extra install)
python dashboard.py            # open http://localhost:5050

# Terminal 2: the agent
python intake_agent.py --phone # or --chat, --local, --webrtc for testing
```

Reset between runs: `rm -f cases.json`.

## Next steps

- Outbound orders callback (Guava calls the nurse) once carrier approval clears
- Push the SBAR into the telehealth provider's record
- Production deployment under a BAA

---

© 2026 Esoteric Healthcare Systems. All rights reserved.
