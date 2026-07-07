# Training Operations Center v6.10

Fix release for authenticated CSV exports.

## Run
```bash
docker compose up --build
```

Open: http://localhost:3000

Default login:
```text
admin / admin123
```

## v6.10 Fixes
- Report exports now download through the logged-in React session.
- No more new browser tab showing `login required`.
- Student CSV export also uses authenticated download.

## If Docker uses old cache
```bash
docker compose build --no-cache frontend
 docker compose up
```
