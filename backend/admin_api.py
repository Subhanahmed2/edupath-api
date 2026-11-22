"""
Admin dashboard API: who registered and what each student chose (field questionnaire, career questions and the
careers they got, programs and shortlist, skill gap). Read-only.

Access: only logged-in accounts whose email is in EDUPATH_ADMIN_EMAILS (comma-separated, set on the server).
Everyone else gets 403 - the data is students' personal answers.

  GET /admin/check            -> {admin: true}  (the page uses it to decide what to show)
  GET /admin/stats            -> totals, sign-ups per day, most common fields / careers / shortlisted programs
  GET /admin/users?q=         -> one row per account (email, name, verified, joined, last active, field, careers)
  GET /admin/users/{id}       -> everything one student did, with question texts next to their answers
  GET /admin/export.csv       -> the users table as a spreadsheet
"""
import csv
import io
import os
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

import questionnaire as Q
from auth import current_user
from career_bank import BANK
from db import Assessment, Journey, User, aware, get_db, now

router = APIRouter(prefix="/admin", tags=["admin"])
FIELD_Q = {q["id"]: q["text"] for q in Q.QUESTIONS}
CAREER_Q = {f: {q["id"]: q["text"] for q in b["questions"]} for f, b in BANK.items()}


def admin_emails():
    return {e.strip().lower() for e in os.getenv("EDUPATH_ADMIN_EMAILS", "").split(",") if e.strip()}


def admin_user(user: User = Depends(current_user)) -> User:
    if user.email.lower() not in admin_emails():
        raise HTTPException(403, "This page is for Edu Path admins only.")
    return user


def _iso(dt):
    return aware(dt).isoformat() if dt else None


def _latest_field(rows):
    """Top field and its probability from the newest field-questionnaire result in `rows` (newest first)."""
    for a in rows:
        if a.kind == "field":
            top = (a.result or {}).get("top_fields") or []
            if top:
                return {"field": top[0].get("field"), "probability": top[0].get("probability")}
    return None


def _top_career(j: Journey):
    c = ((j.career_result or {}).get("careers") or [None])[0]
    return c.get("title") if c else None


def _load(db: Session):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    acts, jours = {}, {}
    for a in db.scalars(select(Assessment).order_by(Assessment.created_at.desc(), Assessment.id.desc())):
        acts.setdefault(a.user_id, []).append(a)
    for j in db.scalars(select(Journey).order_by(Journey.updated_at.desc())):
        jours.setdefault(j.user_id, []).append(j)
    return users, acts, jours


def _row(u: User, acts, jours):
    times = [aware(a.created_at) for a in acts] + [aware(j.updated_at) for j in jours]
    return {"id": u.id, "email": u.email, "name": u.name, "verified": bool(u.email_verified),
            "joined": _iso(u.created_at), "last_active": max(times).isoformat() if times else None,
            "field": _latest_field(acts),
            "careers": [{"field": j.field, "career": _top_career(j), "shortlist": len(j.shortlist or [])}
                        for j in jours if _top_career(j)],
            "fields_explored": [j.field for j in jours],
            "activities": len(acts)}


@router.get("/check")
def check(admin: User = Depends(admin_user)):
    return {"admin": True, "email": admin.email}


@router.get("/stats")
def stats(admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    users, acts, jours = _load(db)
    today = now().date()
    per_day = Counter(aware(u.created_at).date() for u in users if aware(u.created_at).date() > today - timedelta(days=14))
    fields = Counter((_latest_field(acts.get(u.id, [])) or {}).get("field") for u in users)
    fields.pop(None, None)
    careers = Counter(_top_career(j) for js in jours.values() for j in js)
    careers.pop(None, None)
    shortlisted = Counter(p for js in jours.values() for j in js for p in (j.shortlist or []))
    kinds = Counter(a.kind for rows in acts.values() for a in rows)
    week = now() - timedelta(days=7)
    return {
        "users": len(users), "verified": sum(1 for u in users if u.email_verified),
        "new_this_week": sum(1 for u in users if aware(u.created_at) >= week),
        "active_this_week": sum(1 for u in users if any(aware(a.created_at) >= week for a in acts.get(u.id, []))),
        "activities": dict(kinds),
        "signups_per_day": [{"day": str(today - timedelta(days=i)), "count": per_day.get(today - timedelta(days=i), 0)}
                            for i in range(13, -1, -1)],
        "top_fields": fields.most_common(7), "top_careers": careers.most_common(10),
        "top_shortlisted": shortlisted.most_common(10),
    }


@router.get("/users")
def users(q: str = "", admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows, acts, jours = _load(db)
    q = q.strip().lower()
    out = [_row(u, acts.get(u.id, []), jours.get(u.id, [])) for u in rows]
    if q:
        out = [r for r in out if q in r["email"].lower() or q in (r["name"] or "").lower()]
    return out


def _field_detail(a: Assessment):
    r = a.result or {}
    return {"id": a.id, "when": _iso(a.created_at),
            "answers": [{"question": FIELD_Q.get(k, k), "answer": v} for k, v in (a.answers or {}).items()],
            "top_fields": [{"field": t.get("field"), "probability": t.get("probability")} for t in r.get("top_fields", [])]}


def _journey_detail(j: Journey):
    qtext = CAREER_Q.get(j.field, {})
    pr = j.program_result or {}
    pi = j.program_inputs or {}
    return {"field": j.field, "field_match": j.field_match, "started": _iso(j.created_at), "updated": _iso(j.updated_at),
            "career_answers": [{"question": qtext.get(k, k), "answer": v} for k, v in (j.career_answers or {}).items()],
            "careers": [{"title": c.get("title"), "match": c.get("match")} for c in (j.career_result or {}).get("careers", [])],
            "program_inputs": {"group": pi.get("inter_group"), "marks": pi.get("marks"), "preferences": pi.get("prefs") or {},
                               "own_words": pi.get("free_text")},
            "programs": [{"name": p.get("name"), "eligibility": p.get("eligibility"), "reason": p.get("reason")}
                         for p in pr.get("programs", [])],
            "shortlist": j.shortlist or []}


@router.get("/users/{user_id}")
def user_detail(user_id: int, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "No such account.")
    acts = db.scalars(select(Assessment).where(Assessment.user_id == u.id)
                      .order_by(Assessment.created_at.desc(), Assessment.id.desc())).all()
    jours = db.scalars(select(Journey).where(Journey.user_id == u.id).order_by(Journey.updated_at.desc())).all()
    skill = [{"when": _iso(a.created_at), "career": (a.result or {}).get("career"),
              "readiness": (a.result or {}).get("readiness"), "todo": (a.result or {}).get("todo", [])}
             for a in acts if a.kind == "skillgap"]
    return {**_row(u, acts, jours),
            "field_questionnaires": [_field_detail(a) for a in acts if a.kind == "field"],
            "journeys": [_journey_detail(j) for j in jours],
            "skill_gaps": skill,
            "timeline": [{"when": _iso(a.created_at), "kind": a.kind,
                          "summary": _summary(a)} for a in acts]}


def _summary(a: Assessment):
    r = a.result or {}
    if a.kind == "field":
        top = r.get("top_fields") or []
        return f"Top field: {top[0]['field']}" if top else "Field questionnaire"
    if a.kind == "career":
        cs = r.get("careers") or []
        return f"{r.get('field')}: {', '.join(c.get('title', '') for c in cs[:3])}"
    if a.kind == "programs":
        return f"{r.get('field')}: {', '.join(p.get('name', '') for p in (r.get('programs') or [])[:3])}"
    if a.kind == "skillgap":
        return f"Skill gap for {r.get('career')}: readiness {r.get('readiness')}"
    return a.kind


@router.get("/export.csv")
def export_csv(admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows, acts, jours = _load(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "name", "verified", "joined", "last_active", "top_field", "field_probability",
                "careers_chosen", "fields_explored", "activities"])
    for u in rows:
        r = _row(u, acts.get(u.id, []), jours.get(u.id, []))
        f = r["field"] or {}
        w.writerow([r["email"], r["name"], r["verified"], r["joined"], r["last_active"], f.get("field", ""),
                    f.get("probability", ""), "; ".join(f"{c['field']}: {c['career']}" for c in r["careers"]),
                    "; ".join(r["fields_explored"]), r["activities"]])
    return Response("﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="edupath-users.csv"'})
