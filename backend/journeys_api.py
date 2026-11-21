"""
Read a student's journeys (one per field: career answers + result, program profile + recommendation).
Saving happens automatically in /career/step and /programs/recommend (main.py -> database/journeys.py).

  GET /me/journeys          -> every field this student has explored (newest first)
  GET /me/journeys/{field}  -> one field in full (null if nothing is saved for it yet)
  PUT /me/journeys/{field}/shortlist {programs: [names]} -> the programs shortlisted for that field
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import current_user
from db import User, get_db, journeys

router = APIRouter()


class ShortlistIn(BaseModel):
    programs: list[str] = Field(default_factory=list, max_length=40)


@router.get("/me/journeys")
def list_journeys(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return journeys.list_for(db, user)


@router.get("/me/journeys/{field}")
def get_journey(field: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = journeys.get_for(db, user, field)
    return journeys.full(j) if j else None  # "nothing yet" is a normal answer, not an error


@router.put("/me/journeys/{field}/shortlist")
def put_shortlist(field: str, body: ShortlistIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    names = [p.strip()[:120] for p in body.programs if p.strip()]
    j = journeys.set_shortlist(db, user, field, names)
    if j is None:
        raise HTTPException(404, "Nothing saved for this field yet.")
    return {"field": field, "shortlist": j.shortlist}
