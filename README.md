# Phishing Awareness Simulator (Flask)

This is a **cybersecurity awareness training simulator**. It shows *simulated* phishing-style emails.
When a user clicks a simulated link, the app immediately explains red flags and then serves an awareness quiz.

✅ Designed to be safe:
- **Does not** collect passwords, tokens, cookies, or any personal data
- Stores only anonymous training events in the **Flask session**
- Intended for **consensual training** / demos

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open:
- http://127.0.0.1:5000

## Project structure

```
phishing_awareness_flask/
  app.py
  requirements.txt
  README.md
  templates/
    base.html
    index.html
    email.html
    clicked.html
    quiz.html
    result.html
    about.html
  static/
    css/style.css
    js/quiz.js
```

## Ideas to build on

- Add admin-only dashboard (local auth) showing aggregate results
- Add more email scenarios (CEO fraud, OAuth consent scam, QR phishing)
- Internationalize (UK/US variants)
- Add a "Report this email" button & teach reporting workflow

## Deploy on Render (simple Heroku-like option)

1. Ensure `requirements.txt` includes `gunicorn` (already included in this zip).
2. Push this project to GitHub.
3. In Render: **New → Web Service → Connect repo**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `./start.sh`
4. Render will give you a public HTTPS URL you can email to your supervisor.

Notes:
- Render free tier may sleep when idle; first load can be slower.

