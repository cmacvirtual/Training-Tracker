# Training Operations Tracker v3

A Dockerized Streamlit app for managing instructor-led training operations.

## v3 Highlights

- Instructor login system with Admin-created accounts
- Default first-run admin account: `admin` / `admin123`
- Course roster view for a specific class session
- Lab POD readiness tracking per student
- Visual POD readiness indicator that changes between red, orange, and green
- POD name / ID and setup notes per enrolled student
- Roster export for selected class session
- Instructors, attendees, courses, sessions, enrollments, completions, certificates, dashboard, and Excel export

## Run

```bash
docker compose up --build
```

Open:

```text
http://localhost:8501
```

## First Login

```text
Username: admin
Password: admin123
```

To change the first-run default password before the database is created, set:

```bash
DEFAULT_ADMIN_PASSWORD=yourStrongPassword
```

Example:

```bash
DEFAULT_ADMIN_PASSWORD='ChangeMe123!' docker compose up --build
```

## Data Storage

The app uses SQLite at `/data/training_tracker.db` inside the container. The Docker Compose file mounts this to a local `./data` folder.

## Notes

This authentication is intended for a lightweight internal tool. For internet-facing production use, place the app behind SSO, reverse proxy authentication, or another enterprise identity provider.
