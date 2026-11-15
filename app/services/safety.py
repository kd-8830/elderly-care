"""Rule-based drug-class and dose-proximity flags.

This is NOT medical advice. Every flag says "Confirm with your doctor or pharmacist."
"""
from collections import defaultdict
from datetime import datetime

from ..models import Medication, SafetyFlag, db


def _flag(profile_id, severity, message):
    existing = (
        SafetyFlag.query.filter_by(profile_id=profile_id, message=message).first()
    )
    if existing is not None:
        return
    db.session.add(
        SafetyFlag(profile_id=profile_id, severity=severity, message=message)
    )


def scan_profile_safety(profile_id):
    meds = (
        Medication.query.filter_by(profile_id=profile_id)
        .filter(Medication.approval_status == "approved")
        .all()
    )

    # Duplicate drug classes.
    by_class = defaultdict(list)
    for m in meds:
        if m.drug_class:
            by_class[m.drug_class.strip().lower()].append(m)
    for cls, group in by_class.items():
        if len(group) > 1:
            names = ", ".join(m.name for m in group)
            _flag(
                profile_id,
                "warning",
                f"Possible duplicate drug class '{cls}': {names}. "
                "Confirm with your doctor or pharmacist.",
            )

    # Doses too close together (< 1h apart within the same day).
    slots = []
    for m in meds:
        for hhmm in (m.times or []):
            try:
                h, mm = (int(p) for p in hhmm.split(":"))
            except ValueError:
                continue
            slots.append((h * 60 + mm, m.name))
    slots.sort()
    for i in range(len(slots) - 1):
        diff = slots[i + 1][0] - slots[i][0]
        if diff < 60 and slots[i][1] != slots[i + 1][1]:
            _flag(
                profile_id,
                "warning",
                f"Doses for {slots[i][1]} and {slots[i + 1][1]} are less than "
                "1 hour apart. Confirm with your doctor or pharmacist.",
            )

    db.session.commit()