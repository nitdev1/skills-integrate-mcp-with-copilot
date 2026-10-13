"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School, with registration
changes restricted to authenticated teachers.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing activities and managing teacher-only registrations")

SESSION_COOKIE_NAME = "teacher_session"
SESSION_MAX_AGE = 8 * 60 * 60
MIN_PASSWORD_HASH_ITERATIONS = 100_000


class LoginRequest(BaseModel):
    username: str
    password: str


@dataclass(frozen=True)
class PasswordHash:
    iterations: int
    salt: bytes
    digest: bytes


@dataclass(frozen=True)
class TeacherAuthConfig:
    password_hashes: dict[str, PasswordHash]
    session_secret: bytes


def _decode_urlsafe_base64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _load_teacher_auth_config() -> TeacherAuthConfig | None:
    credentials_json = os.environ.get("TEACHER_CREDENTIALS_JSON")
    session_secret = os.environ.get("SESSION_SECRET")

    if not any((credentials_json, session_secret)):
        return None
    if not all((credentials_json, session_secret)):
        raise HTTPException(
            status_code=503,
            detail="Teacher authentication is not configured completely",
        )

    try:
        credentials = json.loads(credentials_json)
        if not isinstance(credentials, dict) or not credentials:
            raise ValueError("Teacher credentials must be a non-empty JSON object")

        password_hashes = {}
        for username, password_hash in credentials.items():
            if not username or not isinstance(password_hash, str):
                raise ValueError("Invalid teacher credentials")
            algorithm, iterations_value, salt_value, digest_value = password_hash.split("$")
            iterations = int(iterations_value)
            salt = _decode_urlsafe_base64(salt_value)
            digest = _decode_urlsafe_base64(digest_value)
            if (
                algorithm != "pbkdf2_sha256"
                or iterations < MIN_PASSWORD_HASH_ITERATIONS
                or len(salt) < 16
                or len(digest) != hashlib.sha256().digest_size
            ):
                raise ValueError("Invalid teacher password hash")
            password_hashes[username] = PasswordHash(iterations, salt, digest)
    except (AttributeError, TypeError, ValueError, binascii.Error) as error:
        raise HTTPException(
            status_code=503,
            detail="Teacher authentication is not configured correctly",
        ) from error

    secret = session_secret.encode("utf-8")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="SESSION_SECRET must contain at least 32 bytes",
        )

    return TeacherAuthConfig(
        password_hashes=password_hashes,
        session_secret=secret,
    )


def _verify_password(password: str, password_hash: PasswordHash) -> bool:
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_hash.salt,
        password_hash.iterations,
    )
    return hmac.compare_digest(candidate, password_hash.digest)


def _create_session_token(username: str, secret: bytes) -> str:
    payload = json.dumps(
        {"username": username, "expires_at": int(time.time()) + SESSION_MAX_AGE},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded_payload}.{encoded_signature}"


def _get_authenticated_teacher(
    request: Request,
    config: TeacherAuthConfig,
) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None or token.count(".") != 1:
        return None

    encoded_payload, encoded_signature = token.split(".")
    try:
        expected_signature = hmac.new(
            config.session_secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        supplied_signature = _decode_urlsafe_base64(encoded_signature)
        payload = json.loads(_decode_urlsafe_base64(encoded_payload))
    except (binascii.Error, UnicodeError, ValueError):
        return None

    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    if not isinstance(payload, dict):
        return None

    username = payload.get("username")
    expires_at = payload.get("expires_at")
    if (
        not isinstance(username, str)
        or username not in config.password_hashes
        or type(expires_at) is not int
        or expires_at <= int(time.time())
    ):
        return None
    return username


def require_teacher(request: Request) -> str:
    config = _load_teacher_auth_config()
    if config is None:
        raise HTTPException(
            status_code=503,
            detail="Teacher authentication is not configured",
        )
    username = _get_authenticated_teacher(request, config)
    if username is None:
        raise HTTPException(status_code=401, detail="Teacher login required")
    return username


# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.get("/auth/status")
def get_auth_status(request: Request):
    config = _load_teacher_auth_config()
    if config is None:
        return {"authenticated": False, "username": None}

    username = _get_authenticated_teacher(request, config)
    return {"authenticated": username is not None, "username": username}


@app.post("/auth/login")
def login_for_teacher(credentials: LoginRequest, request: Request, response: Response):
    config = _load_teacher_auth_config()
    if config is None:
        raise HTTPException(
            status_code=503,
            detail="Teacher authentication is not configured",
        )

    password_hash = config.password_hashes.get(credentials.username)
    username_matches = password_hash is not None
    if password_hash is None:
        password_hash = next(iter(config.password_hashes.values()))
    password_matches = _verify_password(credentials.password, password_hash)
    if not (username_matches and password_matches):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_session_token(credentials.username, config.session_secret),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return {"message": "Teacher login successful", "username": credentials.username}


@app.post("/auth/logout")
def logout_teacher(request: Request, response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return {"message": "Logged out"}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, _: str = Depends(require_teacher)):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str,
    _: str = Depends(require_teacher),
):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
