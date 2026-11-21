"""
Sends the 6-digit email codes (sign-up verification and password reset).

With SMTP settings in backend/.env the code is emailed; without them (development) it is printed in the
server console instead, so the flow can be tested with no email account.
  EDUPATH_SMTP_HOST      e.g. smtp.gmail.com
  EDUPATH_SMTP_PORT      587 (STARTTLS) or 465 (SSL)
  EDUPATH_SMTP_USER      the sending account, e.g. edupath.fyp@gmail.com
  EDUPATH_SMTP_PASSWORD  for Gmail: an App Password (Google account -> Security -> 2-Step Verification -> App passwords)
  EDUPATH_MAIL_FROM      optional display sender, default "Edu Path AI <EDUPATH_SMTP_USER>"

Hosts that block outgoing SMTP (e.g. Railway's free and trial plans) can send over HTTPS with Brevo instead:
  EDUPATH_BREVO_API_KEY  Brevo API key (brevo.com -> SMTP & API -> API keys); when set, it is used instead of SMTP
  EDUPATH_MAIL_SENDER    the sender address, verified in Brevo (Senders); defaults to EDUPATH_SMTP_USER
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

import httpx

BREVO_URL = "https://api.brevo.com/v3/smtp/email"

SUBJECTS = {"verify": "Your Edu Path verification code", "reset": "Your Edu Path password reset code",
            "change": "Confirm your Edu Path password change"}
INTROS = {"verify": "Use this code to verify your email and finish creating your Edu Path account:",
          "reset": "Use this code to reset your Edu Path password:",
          "change": "Someone (hopefully you) asked to change your Edu Path password. Use this code to confirm it:"}


class MailError(Exception):
    pass


def _brevo_sender():
    return os.getenv("EDUPATH_MAIL_SENDER") or os.getenv("EDUPATH_SMTP_USER")


def configured():
    if os.getenv("EDUPATH_BREVO_API_KEY") and _brevo_sender():
        return True
    return bool(os.getenv("EDUPATH_SMTP_HOST") and os.getenv("EDUPATH_SMTP_USER") and os.getenv("EDUPATH_SMTP_PASSWORD"))


def send_code(email: str, code: str, purpose: str, minutes: int):
    if not configured():
        print(f"[Edu Path] {purpose} code for {email}: {code}  (SMTP not configured - printed instead of emailed)",
              flush=True)
        return
    _send(email, SUBJECTS[purpose], f"{INTROS[purpose]}\n\n    {code}\n\nThe code expires in {minutes} minutes. "
          "If you didn't ask for it, you can ignore this email.\n\nEdu Path AI")


def send_notice(email: str, subject: str, body: str):
    """Plain security notice (e.g. "your password was changed")."""
    if not configured():
        print(f"[Edu Path] notice to {email}: {subject}", flush=True)
        return
    _send(email, subject, body + "\n\nEdu Path AI")


def _send(email: str, subject: str, body: str):
    if os.getenv("EDUPATH_BREVO_API_KEY"):
        return _send_brevo(email, subject, body)
    user = os.environ["EDUPATH_SMTP_USER"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("EDUPATH_MAIL_FROM", f"Edu Path AI <{user}>")
    msg["To"] = email
    msg.set_content(body)
    host, port = os.environ["EDUPATH_SMTP_HOST"], int(os.getenv("EDUPATH_SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
                s.login(user, os.environ["EDUPATH_SMTP_PASSWORD"]); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, os.environ["EDUPATH_SMTP_PASSWORD"]); s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(str(e)) from e


def _send_brevo(email: str, subject: str, body: str):
    """Transactional email over HTTPS (Brevo API v3) - works where SMTP ports are blocked."""
    try:
        r = httpx.post(BREVO_URL, timeout=15, headers={"api-key": os.environ["EDUPATH_BREVO_API_KEY"],
                                                       "accept": "application/json"},
                       json={"sender": {"name": "Edu Path AI", "email": _brevo_sender()},
                             "to": [{"email": email}], "subject": subject, "textContent": body})
    except httpx.HTTPError as e:
        raise MailError(f"Brevo unreachable: {e}") from e
    if r.status_code >= 300:
        raise MailError(f"Brevo {r.status_code}: {r.text[:200]}")
