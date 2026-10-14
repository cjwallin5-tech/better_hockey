"""Accounts: email + password sign-in with a cookie session, and the synced fantasy roster.

Passwords are hashed with scrypt (stdlib). A session is a random token in an HttpOnly cookie; only its
SHA-256 is stored, so a leaked database can't be replayed as live sessions.
"""
import hashlib
import hmac
import logging
import re
import secrets
import smtplib
import time
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

import config

router = APIRouter(prefix="/api")
log = logging.getLogger("uvicorn.error")

COOKIE = "session"
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
MIN_PASSWORD, MAX_PASSWORD = 8, 128
MAX_ROSTER = 60

DDL = """
CREATE TABLE IF NOT EXISTS app_user (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS app_user_email_idx ON app_user (lower(email));
CREATE TABLE IF NOT EXISTS app_session (
    token_hash TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS password_reset (
    token_hash TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS fantasy_state (
    user_id    BIGINT PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    players    JSONB NOT NULL DEFAULT '[]',
    scoring    JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def init_db():
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute(DDL)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got, bytes.fromhex(digest))
    except ValueError:
        return False


_DUMMY_HASH = _hash_password("not-a-real-password")  # so unknown emails cost the same time as wrong passwords


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# Failed-login throttle: per email and per client, in memory (resets on restart; enough to stop guessing).
_FAILS: dict[str, list[float]] = {}
FAIL_WINDOW, FAIL_LIMIT = 15 * 60, 8


def _throttled(key: str) -> bool:
    now = time.time()
    _FAILS[key] = [t for t in _FAILS.get(key, []) if now - t < FAIL_WINDOW]
    return len(_FAILS[key]) >= FAIL_LIMIT


def _fail(*keys: str):
    for k in keys:
        _FAILS.setdefault(k, []).append(time.time())


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _start_session(conn, response: Response, request: Request, user_id: int):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute("DELETE FROM app_session WHERE expires_at < now()")
    conn.execute("INSERT INTO app_session (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                 (_token_hash(token), user_id, expires))
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=secure, path="/")


def current_user(conn, request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return conn.execute(
        """SELECT u.id, u.email FROM app_session s JOIN app_user u ON u.id = s.user_id
           WHERE s.token_hash = %s AND s.expires_at > now()""",
        (_token_hash(token),),
    ).fetchone()


class Credentials(BaseModel):
    email: str
    password: str


@router.post("/auth/register")
def register(body: Credentials, request: Request, response: Response):
    email = body.email.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address.")
    if not (MIN_PASSWORD <= len(body.password) <= MAX_PASSWORD):
        raise HTTPException(400, f"Password must be {MIN_PASSWORD}-{MAX_PASSWORD} characters.")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        try:
            user = conn.execute("INSERT INTO app_user (email, password_hash) VALUES (%s, %s) RETURNING id, email",
                                (email, _hash_password(body.password))).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "An account with that email already exists.")
        _start_session(conn, response, request, user["id"])
    return {"email": user["email"]}


@router.post("/auth/login")
def login(body: Credentials, request: Request, response: Response):
    email = body.email.strip().lower()
    keys = (f"e:{email}", f"ip:{_client(request)}")
    if any(_throttled(k) for k in keys):
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = conn.execute("SELECT id, email, password_hash FROM app_user WHERE lower(email) = %s", (email,)).fetchone()
        ok = _verify_password(body.password[:MAX_PASSWORD], user["password_hash"] if user else _DUMMY_HASH)
        if not (user and ok):
            _fail(*keys)
            raise HTTPException(401, "Wrong email or password.")
        _start_session(conn, response, request, user["id"])
    return {"email": user["email"]}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with psycopg.connect(config.DATABASE_URL) as conn:
            conn.execute("DELETE FROM app_session WHERE token_hash = %s", (_token_hash(token),))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = current_user(conn, request)
    return {"user": {"email": user["email"]} if user else None}


class FantasyState(BaseModel):
    players: list[dict]
    scoring: dict


def _clean_state(state: FantasyState):
    players = []
    for p in state.players[:MAX_ROSTER]:
        if isinstance(p.get("id"), int) and p.get("kind") in ("skater", "goalie") and isinstance(p.get("name"), str):
            players.append({"id": p["id"], "kind": p["kind"], "name": p["name"][:100]})
    scoring = {k: float(v) for k, v in state.scoring.items()
               if isinstance(k, str) and len(k) < 40 and isinstance(v, (int, float)) and not isinstance(v, bool)}
    return players, scoring


@router.get("/fantasy/state")
def get_fantasy_state(request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = current_user(conn, request)
        if not user:
            raise HTTPException(401, "Not signed in")
        row = conn.execute("SELECT players, scoring, updated_at FROM fantasy_state WHERE user_id = %s", (user["id"],)).fetchone()
    return row or {"players": [], "scoring": {}, "updated_at": None}


@router.put("/fantasy/state")
def put_fantasy_state(state: FantasyState, request: Request):
    players, scoring = _clean_state(state)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = current_user(conn, request)
        if not user:
            raise HTTPException(401, "Not signed in")
        conn.execute(
            """INSERT INTO fantasy_state (user_id, players, scoring) VALUES (%s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET players = EXCLUDED.players, scoring = EXCLUDED.scoring, updated_at = now()""",
            (user["id"], Jsonb(players), Jsonb(scoring)),
        )
    return {"players": players, "scoring": scoring}


# --- Password reset ---------------------------------------------------------------------------
RESET_MINUTES = 60
RESET_LIMIT = 5  # reset emails per address / client per hour
_RESETS: dict[str, list[float]] = {}


def _reset_throttled(*keys: str) -> bool:
    now = time.time()
    hit = False
    for k in keys:
        recent = [t for t in _RESETS.get(k, []) if now - t < 3600]
        if len(recent) >= RESET_LIMIT:
            hit = True
        else:
            recent.append(now)
        _RESETS[k] = recent
    return hit


def _send_reset_email(email: str, link: str):
    body = (
        f"Someone asked to reset the password for this NHL Stats account.\n\n"
        f"Reset it here (the link works once and expires in {RESET_MINUTES} minutes):\n{link}\n\n"
        "If that wasn't you, ignore this email; your password hasn't changed."
    )
    if not config.SMTP_HOST:
        log.warning("SMTP_HOST is not set, so no email was sent. Reset link for %s: %s", email, link)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, email, "Reset your NHL Stats password"
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        log.exception("Couldn't send the password reset email to %s", email)


class ForgotRequest(BaseModel):
    email: str


@router.post("/auth/forgot")
def forgot_password(body: ForgotRequest, request: Request, background: BackgroundTasks):
    """Always answers the same way, so it can't be used to find out which emails have accounts."""
    email = body.email.strip().lower()
    answer = {"ok": True}
    if not EMAIL_RE.match(email) or _reset_throttled(f"e:{email}", f"ip:{_client(request)}"):
        return answer
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = conn.execute("SELECT id, email FROM app_user WHERE lower(email) = %s", (email,)).fetchone()
        if not user:
            return answer
        token = secrets.token_urlsafe(32)
        conn.execute("DELETE FROM password_reset WHERE user_id = %s OR expires_at < now()", (user["id"],))
        conn.execute(
            "INSERT INTO password_reset (token_hash, user_id, expires_at) VALUES (%s, %s, now() + make_interval(mins => %s))",
            (_token_hash(token), user["id"], RESET_MINUTES),
        )
    # Sent after the response so how long it takes doesn't reveal whether the account exists.
    background.add_task(_send_reset_email, user["email"], f"{config.PUBLIC_URL}/reset-password?token={token}")
    return answer


class ResetRequest(BaseModel):
    token: str
    password: str


@router.post("/auth/reset")
def reset_password(body: ResetRequest):
    if not (MIN_PASSWORD <= len(body.password) <= MAX_PASSWORD):
        raise HTTPException(400, f"Password must be {MIN_PASSWORD}-{MAX_PASSWORD} characters.")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        # Deleting the row is what makes the link single-use; it only returns a row for a live token.
        row = conn.execute(
            "DELETE FROM password_reset WHERE token_hash = %s AND expires_at > now() RETURNING user_id",
            (_token_hash(body.token),),
        ).fetchone()
        if not row:
            raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
        conn.execute("UPDATE app_user SET password_hash = %s WHERE id = %s", (_hash_password(body.password), row["user_id"]))
        conn.execute("DELETE FROM app_session WHERE user_id = %s", (row["user_id"],))  # sign out everywhere
    return {"ok": True}
