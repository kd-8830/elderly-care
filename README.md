# ElderCare

A smart healthcare platform for elderly users, family members and caretakers.
Flask + SQLAlchemy + Postgres, deployed as a Vercel Python serverless app.

This app is a reminder aid. It does not provide medical advice.
Always follow your doctor's instructions.

## Local setup

    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env             # DATABASE_URL=sqlite:///elderly_care.db
    python seed.py                   # demo accounts
    python run.py                    # http://127.0.0.1:5000

Demo accounts (passcode `1234`):

- meera@example.com (elderly)
- ravi@example.com (caretaker)
- anita@example.com (family)

## Deploy

1. Create a Postgres database (Neon or Vercel Postgres). Copy the connection
   string; append `?sslmode=require` if it is not already present.
2. `npm i -g vercel` then `vercel login` and `vercel link` in this folder.
3. Add environment variables (dashboard or CLI):
   `DATABASE_URL`, `SESSION_SECRET`, `CRON_SECRET`.
4. `vercel --prod`.

Health check: `/healthz` returns `{"ok": true}`.