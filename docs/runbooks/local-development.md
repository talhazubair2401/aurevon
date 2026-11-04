# Runbook: local development stack

- Start: `docker compose -f infra/compose.yaml up --build` (proxy on :8080, Mailpit on :8025).
- Reset the database: `docker compose -f infra/compose.yaml down -v`, then start again.
- Migrations run automatically in the one-shot `migrate` service before the API starts.
- Logs: `docker compose -f infra/compose.yaml logs -f api worker`. Every API log line is JSON with a `request_id`
  that matches the `X-Request-ID` response header.
- Health (internal only, not routed by the proxy): `docker compose -f infra/compose.yaml exec api python -c
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health/ready').read())"`.
- Worker check: `docker compose -f infra/compose.yaml exec worker celery -A config inspect ping`.
