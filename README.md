# Rippled AI

> Personal commitment intelligence engine. Observes your meetings, Slack, and email — surfaces what you said you'd do, without becoming another task system.

## Stack

- **API:** FastAPI (Python)
- **Database:** PostgreSQL via Supabase
- **Hosting:** Railway
- **Background jobs:** Celery + Redis

## Local Setup

```bash
# Clone and enter
git clone git@github.com:KevlexNL/rippled-ai.git
cd rippled-ai

# Create virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in .env with real values

# Run dev server
uvicorn app.main:app --reload
```

API docs available at http://localhost:8000/docs (development only).

## Project Structure

```
app/
  main.py          # FastAPI app entry point
  core/
    config.py      # Settings (pydantic-settings)
  api/
    routes/        # Route handlers (one file per domain)
  models/          # Pydantic request/response models
  db/
    client.py      # Supabase client
  services/        # Business logic (detection, lifecycle, clarification)
migrations/        # Alembic database migrations
scripts/           # Utility scripts
```

## Brief Reference

Product and engineering briefs live in the Obsidian vault:
`~/.openclaw/workspace/projects/rippled-ai/Rippled Platform & MVP Brief/`

Start with the Index brief before building anything.

## Deployment

Deployed via Railway. Push to `main` triggers auto-deploy.

Environment variables are set in the Railway dashboard — never commit `.env`.
