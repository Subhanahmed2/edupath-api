"""
Edu Path tables. All are created automatically on startup (database.migrate.init_db).

  users          account: name, email (unique), salted PBKDF2 password hash, email_verified, avatar (small image)
  email_codes    6-digit sign-up / password-reset / password-change codes: only a hash of the code, expiry, attempts
  auth_sessions  login sessions: SHA-256 of the session token (the raw token is never stored), expiry
  user_state     the student's progress as JSON per key, shared by every device of the account
                 (questionnaire answers in progress, field result, career answers per field, marks, skill ratings...)
  assessments    activity history: kind = field | career | programs | skillgap | university
  journeys       ONE ROW PER FIELD a student explores: its career answers and result, its program profile and
                 recommendation, and the programs shortlisted for it - a second field gets its own row
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .connection import now


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)  # data:image/...;base64 (resized, max ~200 KB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmailCode(Base):
    __tablename__ = "email_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[str] = mapped_column(String(10))  # "verify" | "reset" | "change"
    code_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 - the plain code is never stored
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)  # used, replaced by a newer code, or locked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserState(Base):
    __tablename__ = "user_state"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="field")
    answers: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Journey(Base):
    """field -> career -> programs for ONE field of ONE student."""
    __tablename__ = "journeys"
    __table_args__ = (UniqueConstraint("user_id", "field"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(60))
    field_match: Mapped[float | None] = mapped_column(Float, nullable=True)  # the model's fit for this field
    career_answers: Mapped[dict] = mapped_column(JSON, default=dict)   # career question id -> chosen option
    career_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # top careers once finished
    program_inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # marks, preferences, own words
    program_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # the full recommendation shown
    shortlist: Mapped[list | None] = mapped_column(JSON, nullable=True)  # programs the student saved for THIS field
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
