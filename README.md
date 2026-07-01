# Training Operations Tracker v5.1

Dockerized Streamlit app for managing instructor-led training, public class signup, lab POD readiness, course completions, certificates, and reporting.

## v5.1 Highlights

- Public-facing training portal inside the same app
- Compact public upcoming class tiles
- Click a specific class tile, then submit signup details for that selected class
- Public registration status lookup by email
- Instructor/admin login with user management
- Course, instructor, attendee, and session management
- Signup request approval, waitlist, and drop workflow
- Course roster view with POD readiness indicators
- New Lab Builder Queue with account, snapshot, docs, and ready indicators
- End-of-course completion editing and bulk completion updates
- Certificate issued tracking
- Excel exports for reports, rosters, signups, and lab queues
- SQLite persistence using a Docker volume

## Run Locally

```bash
docker compose up --build
```

Open:

```text
http://localhost:8501
```

## Default Login

```text
Username: admin
Password: admin123
```

Change the password after first launch by creating another admin user or setting the environment variable below before the first database is created.

```yaml
environment:
  - DEFAULT_ADMIN_PASSWORD=ChangeMeNow123!
```

## Public Portal

When the app opens and no one is signed in, users land on the public signup portal. They can:

- View upcoming classes
- Request a seat
- Check registration status by email
- Go to Instructor/Admin Sign In

After logging in, admins can also access **Public Portal Preview** from the sidebar.

## Network Deployment Notes

For internal network use, place this behind your normal reverse proxy or internal DNS name, for example:

```text
http://training.company.local
```

Recommended additions before broader production use:

- Put behind HTTPS using NGINX, Caddy, Traefik, or an enterprise load balancer
- Set a strong default admin password before first launch
- Restrict container host access
- Back up the `/data/training_tracker.db` volume
- Consider PostgreSQL if multiple concurrent instructors will be using it heavily

## Data Persistence

The app uses SQLite at:

```text
/data/training_tracker.db
```

The Docker compose file maps this to a named Docker volume.

## Files

- `app/app.py` - Streamlit application
- `Dockerfile` - container build
- `docker-compose.yml` - local deployment
- `requirements.txt` - Python dependencies
