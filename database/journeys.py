"""
Saving and reading a student's journeys: one row per field (table `journeys`), holding that field's career
answers and result and its program profile and recommendation. Called by the backend after each career step
and each program recommendation, so the work is saved as the student goes and is the same on every device.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .connection import aware
from .models import Assessment, Journey, User


def _field_match(db: Session, user_id: int, field: str):
    """The model's fit for this field from the student's latest field questionnaire result, if any."""
    last = db.scalar(select(Assessment).where(Assessment.user_id == user_id, Assessment.kind == "field")
                     .order_by(Assessment.created_at.desc(), Assessment.id.desc()))
    if last is None:
        return None
    r = last.result or {}
    if isinstance(r.get("all_fields"), dict) and field in r["all_fields"]:
        return float(r["all_fields"][field])
    return next((float(t["probability"]) for t in r.get("top_fields", []) if t.get("field") == field), None)


def _journey(db: Session, user: User, field: str) -> Journey:
    j = db.scalar(select(Journey).where(Journey.user_id == user.id, Journey.field == field))
    if j is None:
        j = Journey(user_id=user.id, field=field, career_answers={})
        db.add(j)
    j.field_match = _field_match(db, user.id, field)
    return j


def record_career(db: Session, user: User, field: str, answers: dict, careers: list | None):
    """Save the career answers so far; `careers` (top 3) once the career questions are finished.
    If the answers change, the field's old program recommendation no longer fits and is cleared."""
    j = _journey(db, user, field)
    if (j.career_answers or {}) != answers:
        if j.program_result is not None and not _starts_with(answers, j.career_answers or {}):
            j.program_result, j.shortlist = None, None  # a different career: its programs no longer apply
        j.career_answers = dict(answers)
    if careers is not None:
        j.career_result = {"careers": careers}
    elif not answers:
        j.career_result = None  # started again
    db.commit()
    return j


def _starts_with(new: dict, old: dict) -> bool:
    """True when `new` only adds answers to `old` (the same conversation continuing)."""
    return all(new.get(k) == v for k, v in old.items())


def record_programs(db: Session, user: User, field: str, inputs: dict, result: dict):
    """Save the program profile and the recommendation exactly as it was shown."""
    j = _journey(db, user, field)
    j.career_answers = dict(inputs.get("answers") or j.career_answers or {})
    j.program_inputs = inputs
    j.program_result = result
    db.commit()
    return j


def set_shortlist(db: Session, user: User, field: str, programs: list):
    """The programs the student shortlisted for this field (replaces the previous list)."""
    j = get_for(db, user, field)
    if j is None:
        return None
    j.shortlist = list(dict.fromkeys(programs))  # keep order, no duplicates
    db.commit()
    return j


def summary(j: Journey) -> dict:
    top = ((j.career_result or {}).get("careers") or [None])[0]
    progs = (j.program_result or {}).get("programs") or []
    return {"field": j.field, "field_match": j.field_match,
            "career": top, "career_answered": len(j.career_answers or {}), "career_done": j.career_result is not None,
            "programs": [p.get("name") for p in progs], "has_programs": j.program_result is not None,
            "shortlist": j.shortlist or [],
            "created_at": aware(j.created_at).isoformat(), "updated_at": aware(j.updated_at).isoformat()}


def full(j: Journey) -> dict:
    return {**summary(j), "career_answers": j.career_answers or {}, "career_result": j.career_result,
            "program_inputs": j.program_inputs, "program_result": j.program_result}


def list_for(db: Session, user: User):
    rows = db.scalars(select(Journey).where(Journey.user_id == user.id).order_by(Journey.updated_at.desc())).all()
    return [summary(j) for j in rows]


def get_for(db: Session, user: User, field: str):
    return db.scalar(select(Journey).where(Journey.user_id == user.id, Journey.field == field))
