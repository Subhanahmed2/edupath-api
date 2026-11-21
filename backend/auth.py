"""
Accounts: sign up with email verification, log in, log out, password reset, and per-user saved progress.

Flow
  1. sign up (email + strong password) -> account created UNVERIFIED, a 6-digit code is emailed (mailer.py)
  2. verify-email (email + code)       -> account verified; the student is sent to the log-in page
  3. log in                            -> session token. Unverified accounts get 403 and a fresh code instead.
  Forgot password: send-code {purpose: "reset"} -> reset-password (email + code + new password).

Security
  - passwords: PBKDF2-HMAC-SHA256, 200,000 iterations, 16-byte random salt per user (Python stdlib)
  - sessions: random 256-bit token returned once; only its SHA-256 is stored; expires after 30 days
  - login throttling: 5 failed attempts per email per 15 minutes
  - generic "email or password is incorrect" message (does not reveal which accounts exist)
  - email codes: 6 digits from `secrets`, only a SHA-256 is stored, valid 10 minutes, 5 tries per code,
    at most 3 codes per email per 15 minutes; send-code answers the same whether or not the account exists
The browser sends the token as  Authorization: Bearer <token>.

Endpoints
  POST /auth/signup         {email, password, name?}       -> {verify: true, email, expires_in}  (code emailed)
  POST /auth/send-code      {email, purpose: verify|reset}  -> {sent: true, expires_in}         (resend / forgot)
  POST /auth/verify-email   {email, code}                   -> {verified: true}
  POST /auth/reset-password {email, code, new_password}     -> {reset: true}  (logs out every device)
  POST /auth/login          {email, password}               -> {token, user}  · 403 if the email is not verified
  POST /auth/logout
  GET  /auth/me                                  -> user
  PATCH /auth/me      {name}                      -> user  (change display name)
  PUT  /auth/me/avatar {image: data URL | null}  -> user  (PNG/JPEG/WebP, max 200 KB; null removes it)
  POST /auth/change-password/start {current_password}                     -> code emailed (purpose "change")
  POST /auth/change-password {current_password, code, new_password}      -> {changed: true}
       Needs BOTH the current password and the emailed code; wrong current passwords lock the change for
       15 minutes after 5 tries; other devices are signed out; a notice is emailed afterwards.
  GET  /me/state                                 -> {key: value} saved progress
  PUT  /me/state      {items: {key: value|null}} -> save (null deletes)
  GET  /me/history?kind=                         -> activity history (newest first): field, career, programs,
                                                    skillgap, university. /me/assessments is the same list.
  GET  /me/history/{id}                          -> one saved activity in full (inputs + result)
  POST /me/history    {kind, inputs, result}     -> save an activity computed in the browser (skillgap, university)
  Field, career and program results are saved by the API itself when the request carries a log-in token.
"""
import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time
from datetime import timedelta

import mailer
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db import Assessment, AuthSession, EmailCode, User, UserState, aware, get_db, now

router = APIRouter()
ITERATIONS = 200_000
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# progress keys the browser may store on the server (mirrors localStorage keys)
STATE_KEY_RE = re.compile(r"^ep_(result|quiz|shortlist|career|career_.{1,40}|skill_levels|skillgap|marks|progprefs)$")
MAX_STATE_BYTES = 64_000
_failed = {}  # email -> [timestamps] (in memory; resets on restart)
CODE_MINUTES = 10
CODE_TRIES = 5
CODES_PER_WINDOW, CODE_WINDOW_MIN = 3, 15
WRONG_CODE = "That code is wrong or has expired. Check the latest email or ask for a new code."


# ---------------- passwords & tokens ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iters))
        return algo == "pbkdf2_sha256" and hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=_token_hash(token), user_id=user.id, expires_at=now() + timedelta(days=SESSION_DAYS)))
    db.commit()
    return token


def _public(user: User):
    return {"id": user.id, "name": user.name, "email": user.email, "email_verified": user.email_verified,
            "avatar": user.avatar, "created_at": user.created_at.isoformat()}


# ---------------- email codes ----------------
def _code_hash(email: str, purpose: str, code: str) -> str:
    return hashlib.sha256(f"{email}|{purpose}|{code}".encode()).hexdigest()


def _send_code(db: Session, email: str, purpose: str):
    """New code for (email, purpose): older ones stop working. Raises 429 when asked too often."""
    window = now() - timedelta(minutes=CODE_WINDOW_MIN)
    recent = db.scalars(select(EmailCode).where(EmailCode.email == email, EmailCode.created_at >= window)).all()
    if len(recent) >= CODES_PER_WINDOW:
        raise HTTPException(429, f"Too many codes requested. Please wait {CODE_WINDOW_MIN} minutes and try again.")
    db.execute(delete(EmailCode).where(EmailCode.created_at < now() - timedelta(days=1))  # housekeeping
               .execution_options(synchronize_session=False))
    for old in db.scalars(select(EmailCode).where(EmailCode.email == email, EmailCode.purpose == purpose,
                                                  EmailCode.used.is_(False))):
        old.used = True
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(EmailCode(email=email, purpose=purpose, code_hash=_code_hash(email, purpose, code),
                     expires_at=now() + timedelta(minutes=CODE_MINUTES)))
    db.commit()
    try:
        mailer.send_code(email, code, purpose, CODE_MINUTES)
    except mailer.MailError:
        raise HTTPException(502, "We couldn't send the email right now. Please try again in a minute.")


def _check_code(db: Session, email: str, purpose: str, code: str):
    """Use up a valid code, or raise 400 (wrong/expired) / 429 (too many tries)."""
    row = db.scalar(select(EmailCode).where(EmailCode.email == email, EmailCode.purpose == purpose,
                                            EmailCode.used.is_(False)).order_by(EmailCode.created_at.desc()))
    if row is None or aware(row.expires_at) < now():
        raise HTTPException(400, WRONG_CODE)
    if not hmac.compare_digest(row.code_hash, _code_hash(email, purpose, code.strip())):
        row.attempts += 1
        if row.attempts >= CODE_TRIES:
            row.used = True
            db.commit()
            raise HTTPException(429, "Too many wrong codes. Please ask for a new code.")
        db.commit()
        raise HTTPException(400, WRONG_CODE)
    row.used = True


# ---------------- dependencies ----------------
def _user_from_header(authorization: str | None, db: Session):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    sess = db.get(AuthSession, _token_hash(authorization[7:].strip()))
    if sess is None:
        return None
    expires = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=now().tzinfo)
    if expires < now():
        db.delete(sess); db.commit()
        return None
    return db.get(User, sess.user_id)


def current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    user = _user_from_header(authorization, db)
    if user is None:
        raise HTTPException(401, "Please log in.")
    return user


def optional_user(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    return _user_from_header(authorization, db)


# ---------------- request models ----------------
class SignupIn(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)
    name: str | None = Field(None, max_length=80)  # optional; defaults to the part of the email before "@"


# strong password: 8+ characters with upper case, lower case, a number and a symbol (same rule as the frontend)
def password_problem(pw: str):
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    missing = [what for what, rx in (("an upper-case letter", r"[A-Z]"), ("a lower-case letter", r"[a-z]"),
                                     ("a number", r"\d"), ("a symbol", r"[^A-Za-z0-9]")) if not re.search(rx, pw)]
    return f"Password needs {', '.join(missing)}." if missing else None


class SendCodeIn(BaseModel):
    email: str = Field(..., max_length=255)
    purpose: str = Field("verify", pattern="^(verify|reset)$")


class VerifyIn(BaseModel):
    email: str = Field(..., max_length=255)
    code: str = Field(..., max_length=12)


class ResetIn(VerifyIn):
    new_password: str = Field(..., max_length=128)


class LoginIn(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class NameIn(BaseModel):
    name: str = Field(..., max_length=200)


class AvatarIn(BaseModel):
    image: str | None = Field(None, max_length=300_000)


class PwStartIn(BaseModel):
    current_password: str = Field(..., max_length=128)


class PwChangeIn(PwStartIn):
    code: str = Field(..., max_length=12)
    new_password: str = Field(..., max_length=128)


class StateIn(BaseModel):
    items: dict[str, object]


KINDS = ("field", "career", "programs", "skillgap", "university")
CLIENT_KINDS = ("skillgap", "university")  # worked out in the browser; the others are saved by the API


class ActivityIn(BaseModel):
    kind: str = Field(..., pattern=f"^({'|'.join(CLIENT_KINDS)})$")
    inputs: dict = Field(default_factory=dict)
    result: dict


# ---------------- endpoints ----------------
@router.post("/auth/signup")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Please enter a valid email address.")
    problem = password_problem(body.password)
    if problem:
        raise HTTPException(422, problem)
    name = " ".join((body.name or "").split()) or email.split("@")[0]
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.email_verified:
        raise HTTPException(409, "An account with this email already exists. Please log in.")
    if user is None:
        db.add(User(name=name, email=email, password_hash=hash_password(body.password)))
    else:  # signed up before but never verified: nobody has proved they own this email, so start over
        user.name, user.password_hash = name, hash_password(body.password)
    db.commit()
    _send_code(db, email, "verify")
    return {"verify": True, "email": email, "expires_in": CODE_MINUTES * 60}


@router.post("/auth/send-code")
def send_code(body: SendCodeIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Please enter a valid email address.")
    user = db.scalar(select(User).where(User.email == email))
    # same answer either way, so this can't be used to find out who has an account
    if user is not None and (body.purpose == "reset" or not user.email_verified):
        _send_code(db, email, body.purpose)
    return {"sent": True, "expires_in": CODE_MINUTES * 60}


@router.post("/auth/verify-email")
def verify_email(body: VerifyIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(400, WRONG_CODE)
    if user.email_verified:
        return {"verified": True}
    _check_code(db, email, "verify", body.code)
    user.email_verified, user.verified_at = True, now()
    db.commit()
    return {"verified": True}


@router.post("/auth/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    problem = password_problem(body.new_password)
    if problem:
        raise HTTPException(422, problem)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(400, WRONG_CODE)
    _check_code(db, email, "reset", body.code)
    user.password_hash = hash_password(body.new_password)
    if not user.email_verified:  # the code proved they own the email
        user.email_verified, user.verified_at = True, now()
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))  # log out every device
    db.commit()
    _failed.pop(email, None)
    return {"reset": True}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    recent = [t for t in _failed.get(email, []) if time.time() - t < 900]
    if len(recent) >= 5:
        raise HTTPException(429, "Too many attempts. Please wait 15 minutes and try again.")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        _failed[email] = recent + [time.time()]
        raise HTTPException(401, "Email or password is incorrect.")
    _failed.pop(email, None)
    if not user.email_verified:
        try:
            _send_code(db, email, "verify")
            msg = "Please verify your email first. We've sent a new 6-digit code."
        except HTTPException as e:
            if e.status_code != 429:
                raise
            msg = "Please verify your email first. Use the latest code we emailed you."
        raise HTTPException(403, msg)
    return {"token": _new_session(db, user), "user": _public(user)}


@router.post("/auth/logout")
def logout(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    if authorization and authorization.lower().startswith("bearer "):
        db.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(authorization[7:].strip())))
        db.commit()
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return _public(user)


# ---------------- profile ----------------
NAME_RE = re.compile(r"^[^\x00-\x1f<>]{1,80}$")  # printable, no angle brackets
AVATAR_MAX = 200_000  # bytes after decoding
AVATAR_MAGIC = {"png": b"\x89PNG\r\n\x1a\n", "jpeg": b"\xff\xd8\xff", "webp": b"RIFF"}


@router.patch("/auth/me")
def update_me(body: NameIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    name = " ".join(body.name.split())
    if not NAME_RE.match(name):
        raise HTTPException(422, "Use 1-80 characters for your name (no < or >).")
    user.name = name
    db.commit()
    return _public(user)


@router.put("/auth/me/avatar")
def set_avatar(body: AvatarIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.image is None:
        user.avatar = None
    else:
        m = re.match(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$", body.image)
        if not m:
            raise HTTPException(422, "Upload a PNG, JPEG or WebP image.")
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(422, "That image could not be read.")
        if len(raw) > AVATAR_MAX:
            raise HTTPException(413, "That image is too large (max 200 KB after resizing).")
        if not raw.startswith(AVATAR_MAGIC[m.group(1)]) or (m.group(1) == "webp" and raw[8:12] != b"WEBP"):
            raise HTTPException(422, "That file is not a real image.")
        user.avatar = body.image
    db.commit()
    return _public(user)


# ---------------- change password: current password + emailed code ----------------
_pw_failed = {}  # user id -> [timestamps] of wrong current passwords (in memory)


def _check_current(user: User, password: str):
    recent = [t for t in _pw_failed.get(user.id, []) if time.time() - t < 900]
    if len(recent) >= 5:
        raise HTTPException(429, "Too many wrong passwords. Please wait 15 minutes and try again.")
    if not verify_password(password, user.password_hash):
        _pw_failed[user.id] = recent + [time.time()]
        raise HTTPException(401, "Your current password is incorrect.")
    _pw_failed.pop(user.id, None)


@router.post("/auth/change-password/start")
def change_password_start(body: PwStartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _check_current(user, body.current_password)
    _send_code(db, user.email, "change")
    return {"sent": True, "email": user.email, "expires_in": CODE_MINUTES * 60}


@router.post("/auth/change-password")
def change_password(body: PwChangeIn, authorization: str | None = Header(None),
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    _check_current(user, body.current_password)
    problem = password_problem(body.new_password)
    if problem:
        raise HTTPException(422, problem)
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(422, "Choose a password different from your current one.")
    _check_code(db, user.email, "change", body.code)
    user.password_hash = hash_password(body.new_password)
    this = _token_hash(authorization[7:].strip())
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash != this))
    db.commit()
    try:
        mailer.send_notice(user.email, "Your Edu Path password was changed",
                           "Your Edu Path password was just changed and other devices were signed out. "
                           "If this wasn't you, use 'Forgot password?' on the log-in page right away.")
    except mailer.MailError:
        pass  # the change itself succeeded
    return {"changed": True}


@router.get("/me/state")
def get_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(UserState).where(UserState.user_id == user.id)).all()
    return {r.key: r.value for r in rows}


@router.put("/me/state")
def put_state(body: StateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    import json
    bad = [k for k in body.items if not STATE_KEY_RE.match(k)]
    if bad:
        raise HTTPException(422, f"Not a saveable key: {bad}")
    for k, v in body.items.items():
        if v is not None and len(json.dumps(v)) > MAX_STATE_BYTES:
            raise HTTPException(413, f"{k} is too large")
        row = db.scalar(select(UserState).where(UserState.user_id == user.id, UserState.key == k))
        if v is None:
            if row:
                db.delete(row)
        elif row:
            row.value = v
            row.updated_at = now()
        else:
            db.add(UserState(user_id=user.id, key=k, value=v))
    db.commit()
    return {"saved": sorted(body.items)}


def _summary(a: Assessment):
    """Short version of a saved activity for lists (the dashboard history)."""
    r, out = a.result or {}, {"id": a.id, "kind": a.kind, "created_at": aware(a.created_at).isoformat()}
    if a.kind == "field":
        out["top_fields"] = [{"field": t["field"], "probability": t["probability"]} for t in r.get("top_fields", [])]
    elif a.kind == "career":
        out.update(field=r.get("field"), careers=r.get("careers", []))
    elif a.kind == "programs":
        out.update(field=r.get("field"), top_career=r.get("top_career"),
                   programs=[p["name"] for p in r.get("programs", [])])
    elif a.kind == "skillgap":
        out.update(career=r.get("career"), readiness=r.get("readiness"), todo=r.get("todo", []))
    else:
        out["result"] = r
    return out


@router.get("/me/history")
@router.get("/me/assessments")
def history(kind: str | None = None, limit: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Assessment).where(Assessment.user_id == user.id)
    if kind:
        q = q.where(Assessment.kind == kind)
    rows = db.scalars(q.order_by(Assessment.created_at.desc(), Assessment.id.desc()).limit(max(1, min(limit, 100)))).all()
    return [_summary(a) for a in rows]


@router.get("/me/history/{activity_id}")
def history_item(activity_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Assessment, activity_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(404, "Not found.")
    return {**_summary(a), "inputs": a.answers, "result": a.result}


@router.post("/me/history")
def add_history(body: ActivityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    import json
    if len(json.dumps(body.inputs)) + len(json.dumps(body.result)) > MAX_STATE_BYTES:
        raise HTTPException(413, "Too large to save.")
    a = save_activity(db, user, body.kind, body.inputs, body.result,
                      match_on="career_id" if body.kind == "skillgap" else None)
    return {"id": a.id, "saved": True}


def save_activity(db: Session, user: User, kind: str, inputs: dict, result: dict, match_on: str | None = None):
    """Add one history row. If the student's latest row of this kind is the same activity (identical inputs,
    or the same `match_on` value, e.g. the career of a skill-gap plan), update it instead, so page reloads
    and re-ratings don't fill the history with copies."""
    last = db.scalar(select(Assessment).where(Assessment.user_id == user.id, Assessment.kind == kind)
                     .order_by(Assessment.created_at.desc(), Assessment.id.desc()))
    same = last is not None and ((last.answers or {}).get(match_on) == inputs.get(match_on) if match_on
                                 else last.answers == inputs)
    if same:
        last.answers, last.result, last.created_at = inputs, result, now()
        row = last
    else:
        row = Assessment(user_id=user.id, kind=kind, answers=inputs, result=result)
        db.add(row)
    db.commit()
    return row


def save_assessment(db: Session, user: User, answers: dict, result: dict):
    save_activity(db, user, "field", answers, result)
