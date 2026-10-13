# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Allow authenticated teachers to register and unregister students
- Allow students to view activities and participant lists without logging in
- Protect teacher sessions with signed, HTTP-only cookies

## Getting Started

1. Install the dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Configure teacher accounts and a private session-signing secret in the server environment. Do not commit these values or store teacher passwords in a checked-in file. To generate a PBKDF2-SHA256 password hash for each teacher, run:

   ```
   python - <<'PY'
   import base64
   import getpass
   import hashlib
   import secrets

   password = getpass.getpass("Teacher password: ")
   salt = secrets.token_bytes(16)
   digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
   encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
   print(f"pbkdf2_sha256$600000${encode(salt)}${encode(digest)}")
   PY
   ```

   Put each generated hash in a JSON object keyed by that teacher's username, and provide the object as `TEACHER_CREDENTIALS_JSON`. For example, the value has the shape `{"teacher1":"<hash>","teacher2":"<hash>"}`. Also set a randomly generated `SESSION_SECRET` of at least 32 bytes; generate one with `python -c 'import secrets; print(secrets.token_hex(32))'`. Supply both values through your deployment's environment or secret manager. Without them the site remains available for read-only browsing, while login and registration changes are disabled.

3. Run the application from the repository root:

   ```
   uvicorn app:app --reload --app-dir src
   ```

4. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                           |
| ------ | ----------------------------------------------------------------- | --------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities and participant lists; public                     |
| GET    | `/auth/status`                                                    | Check whether the current browser has a valid teacher session         |
| POST   | `/auth/login`                                                     | Log in with a configured teacher username and password                |
| POST   | `/auth/logout`                                                    | Clear the current teacher session                                      |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Register a student; requires a teacher session                        |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student; requires a teacher session                  |

Teacher sessions expire after eight hours. The browser cookie is HTTP-only and uses `SameSite=Strict`; it is marked `Secure` when served over HTTPS. Use HTTPS in production.

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
