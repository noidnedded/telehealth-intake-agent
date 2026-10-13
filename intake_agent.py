"""Telehealth Intake Agent
Inbound Guava agent. Dynamic user state = case acuity, learned live from vitals.
Routine vs STAT mode changes the rest of the call. Fictional data only.
"""
import argparse
import json
import logging
import os
import re
import tempfile
from datetime import datetime

import guava
from guava import logging_utils

logger = logging.getLogger("intake")

BASE = os.path.dirname(os.path.abspath(__file__))
CASES_PATH = os.path.join(BASE, "cases.json")


# ---------- cases.json helpers (atomic writes) ----------
def load_cases():
    if not os.path.exists(CASES_PATH):
        return []
    with open(CASES_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_cases(cases):
    fd, tmp = tempfile.mkstemp(dir=BASE, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(cases, f, indent=2)
    os.replace(tmp, CASES_PATH)


def now_hm():
    return datetime.now().strftime("%H:%M")


def create_case():
    cases = load_cases()
    case_id = f"c_{len(cases) + 1:04d}"
    cases.append({
        "id": case_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "call_in_progress",
        "acuity": None,
        "timeline": {"call_in_progress": now_hm()},
        "nurse_name": None,
        "fields": {},
        "red_flags": [],
        "missing": [],
        "sbar_text": None,
        "orders": None,
        "readback_text": None,
    })
    save_cases(cases)
    return case_id


def get_case(case_id):
    for c in load_cases():
        if c["id"] == case_id:
            return c
    return None


def update_case(case_id, fields=None, timeline=None, **changes):
    cases = load_cases()
    for c in cases:
        if c["id"] == case_id:
            if fields:
                c["fields"].update(fields)
            if timeline:
                c["timeline"].update(timeline)
            c.update(changes)
    save_cases(cases)


def grab(call, keys):
    return {k: call.get_field(k) for k in keys}


# ---------- clinical logic (Section 11, demo defaults) ----------
def to_num(v):
    if v is None:
        return None
    m = re.search(r"\d+(\.\d+)?", str(v))
    return float(m.group()) if m else None


def parse_bp(bp):
    nums = re.findall(r"\d+", str(bp or ""))
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    return None, None


def assess(fields):
    """Returns (red_flags, critical) where critical=True means STAT mode."""
    flags, critical = [], False
    sbp, _ = parse_bp(fields.get("bp"))
    hr = to_num(fields.get("heart_rate"))
    temp = to_num(fields.get("temp_f"))
    spo2 = to_num(fields.get("spo2"))

    if spo2 is not None and spo2 < 90:
        flags.append(f"LOW OXYGEN SpO2 {int(spo2)}%")
        critical = True
    if sbp is not None and (sbp < 90 or sbp > 180):
        flags.append(f"BLOOD PRESSURE SBP {sbp}")
        critical = True
    if hr is not None and (hr < 50 or hr > 120):
        flags.append(f"HEART RATE {int(hr)}")
        critical = True
    if temp is not None and temp >= 100.4:
        flags.append(f"FEVER {temp} F")
    reason = str(fields.get("reason_for_call") or "").lower()
    if any(w in reason for w in ["confus", "mental status", "altered", "lethargic", "not acting"]):
        flags.append("ACUTE MENTAL STATUS CHANGE")
    return flags, critical


ALL_KEYS = ["nurse_name", "resident_name", "reason_for_call", "bp", "heart_rate",
            "temp_f", "spo2", "relevant_history", "nurse_request"]


def build_sbar(case):
    f = case["fields"]
    flags = case["red_flags"]
    acuity = "STAT" if case["acuity"] == "stat" else "ROUTINE"
    lines = [
        f"TELEHEALTH INTAKE | {acuity} | received {datetime.now().strftime('%-I:%M %p')} | RED FLAGS: {len(flags)}",
        f"CALLER   {f.get('nurse_name')}",
        f"RESIDENT {f.get('resident_name')}",
        "",
        f"S  {f.get('reason_for_call')}",
        f"   Request: {f.get('nurse_request')}",
        f"B  Hx {f.get('relevant_history')}",
        f"A  BP {f.get('bp')}  HR {f.get('heart_rate')}  T {f.get('temp_f')} F  SpO2 {f.get('spo2')}%",
    ]
    lines += [f"   !! {x}" for x in flags]
    lines.append(f"R  {f.get('nurse_request')}")
    if case["missing"]:
        lines.append(f"NOT PROVIDED: {', '.join(case['missing'])}")
    return "\n".join(lines)


# ---------- agent ----------
agent = guava.Agent(
    name="Ava",
    organization="Peachtree Telehealth",
    purpose="Take change-of-condition calls from nursing home nurses and prepare a summary for the nurse practitioner.",
    speech_speed="fast",
    pronunciations={"Rocephin": "roh-SEF-in", "ceftriaxone": "sef-try-AX-own", "PRN": "P R N", "IM": "I M", "UA": "U A"},
)


def pending_orders_case():
    """Plan B: a case with NP orders waiting for the nurse to call back."""
    pend = [c for c in load_cases() if c.get("status") == "orders_sent"]
    return sorted(pend, key=lambda c: c["timeline"].get("orders_sent", ""))[-1] if pend else None

OPENING_KEYS = ["nurse_name", "resident_name", "reason_for_call"]
VITAL_KEYS = ["bp", "heart_rate", "temp_f", "spo2"]
HISTORY_KEYS = ["relevant_history", "nurse_request"]

RULES = [
    "Keep questions short; the nurse is busy.",
    "Do not give clinical advice or orders; you only collect information for the NP.",
]


@agent.on_call_start
def on_call_start(call: guava.Call):
    # DYNAMIC STATE #2: a returning nurse with pending orders gets a different call.
    pending = pending_orders_case()
    if pending:
        call.set_variable("case_id", pending["id"])
        resident = pending["fields"].get("resident_name") or "the resident"
        logger.info("Orders callback for case %s", pending["id"])
        call.set_task(
            "deliver_orders",
            objective=f"Deliver the nurse practitioner's orders for {resident} and get a read-back.",
            checklist=[
                f"Say you have the NP's orders for {resident}, then read them slowly, exactly as written: {pending['orders']}",
                "Ask the nurse to read the orders back to you.",
                guava.Field(key="readback_text", field_type="text",
                            description="The nurse's read-back of the orders, word for word"),
                "Accept her read-back if it covers each order in substance. Transcription often garbles medication names; "
                "small wording or pronunciation differences are fine and you must NOT correct them.",
                "Only if a whole order is missing or a number or dose is clearly different, read that one order again, once. Then accept.",
                "Do not add, change, or explain any order.",
            ],
        )
        return

    case_id = create_case()
    call.set_variable("case_id", case_id)
    logger.info("New case %s", case_id)
    call.set_task(
        "opening",
        objective="Greet the nurse briefly and collect who is calling and what's going on with the resident, so the NP gets the full picture.",
        checklist=[
            guava.Field(key="nurse_name", field_type="text",
                        description="The nurse's name and title (LPN or RN)"),
            guava.Field(key="resident_name", field_type="text", sensitive=True,
                        description="The resident's name"),
            guava.Field(key="reason_for_call", field_type="text",
                        question="In a sentence or two, what's going on with the resident?"),
            "Ask for the nurse's name and title and the resident's name together in ONE question.",
            *RULES,
        ],
    )


@agent.on_task_complete("opening")
def on_opening_done(call: guava.Call):
    case_id = call.get_variable("case_id")
    vals = grab(call, OPENING_KEYS)
    update_case(case_id, fields=vals, nurse_name=vals["nurse_name"])
    call.set_task(
        "vitals",
        objective="Collect the resident's current vital signs.",
        checklist=[
            guava.Field(key="bp", field_type="text", description="Blood pressure, e.g. 120 over 80"),
            guava.Field(key="heart_rate", field_type="integer", description="Heart rate"),
            guava.Field(key="temp_f", field_type="text", description="Temperature in Fahrenheit"),
            guava.Field(key="spo2", field_type="integer", description="Oxygen saturation percent"),
            "Ask for all four vitals in ONE question.",
            "Read all four vitals back in one short sentence to confirm.",
            *RULES,
        ],
    )


@agent.on_task_complete("vitals")
def on_vitals_done(call: guava.Call):
    case_id = call.get_variable("case_id")
    update_case(case_id, fields=grab(call, VITAL_KEYS))
    case = get_case(case_id)

    # DYNAMIC STATE: acuity learned live from what the nurse just reported.
    flags, critical = assess(case["fields"])
    acuity = "stat" if critical else "routine"
    call.set_variable("acuity", acuity)
    update_case(case_id, red_flags=flags, acuity=acuity)  # dashboard sees STAT mid-call
    logger.info("Case %s acuity=%s flags=%s", case_id, acuity, flags)

    if critical:
        call.set_task(
            "history",
            objective="These vitals are critical. Finish intake as fast as possible so the NP can act.",
            checklist=[
                "Calmly tell the nurse these vitals are concerning, you are flagging this as URGENT for the NP, and ask her to stay with the resident.",
                guava.Field(key="relevant_history", field_type="text",
                            question="Quickly, his top two or three diagnoses?"),
                guava.Field(key="nurse_request", field_type="text",
                            question="And what do you need from the NP?"),
                "Do not ask any extra questions. Be brief.",
                "Do not give clinical advice or orders; you only collect information for the NP.",
            ],
        )
    else:
        call.set_task(
            "history",
            objective="Collect background and the nurse's request for the NP.",
            checklist=[
                guava.Field(key="relevant_history", field_type="text",
                            description="Key diagnoses, e.g. CHF, COPD, diabetes, dementia"),
                guava.Field(key="nurse_request", field_type="text",
                            question="What are you asking the NP for?"),
                *RULES,
            ],
        )


@agent.on_task_complete("history")
def on_history_done(call: guava.Call):
    case_id = call.get_variable("case_id")
    acuity = call.get_variable("acuity")
    update_case(case_id, fields=grab(call, HISTORY_KEYS))
    case = get_case(case_id)
    missing = [k for k in ALL_KEYS if case["fields"].get(k) in (None, "")]
    case["missing"] = missing
    sbar = build_sbar(case)
    update_case(case_id, missing=missing, sbar_text=sbar,
                status="summary_received", timeline={"summary_received": now_hm()})
    logger.info("SBAR built for %s", case_id)

    # Never claim the NP has received it before Acknowledge.
    if acuity == "stat":
        call.hangup(
            "Tell the nurse the summary has been sent to the nurse practitioner flagged URGENT, "
            "that she'll get confirmation once the NP reviews it, and that if the resident gets worse "
            "before then she should follow her facility's emergency protocol and not wait for the callback."
        )
    else:
        call.hangup(
            "Tell the nurse the summary has been sent to the nurse practitioner, that she'll get "
            "confirmation once the NP reviews it, and that orders will come by phone."
        )


@agent.on_task_complete("deliver_orders")
def on_orders_delivered(call: guava.Call):
    case_id = call.get_variable("case_id")
    update_case(case_id, readback_text=call.get_field("readback_text"),
                status="readback_confirmed", timeline={"readback_confirmed": now_hm()})
    call.hangup("Thank the nurse and remind her to enter the orders in the EHR per facility policy. Be brief.")


if __name__ == "__main__":
    logging_utils.configure_logging()
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    for flag in ["--phone", "--webrtc", "--local", "--chat"]:
        g.add_argument(flag, action="store_true")
    a = p.parse_args()
    if a.phone:
        agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
    elif a.webrtc:
        agent.listen_webrtc()
    elif a.local:
        agent.call_local()
    else:
        agent.chat()
