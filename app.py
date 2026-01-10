from flask import Flask, render_template, redirect, url_for, request, session, abort, jsonify
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "change-me-in-production"  # for demo only

# IMPORTANT: This project is a PHISHING *AWARENESS SIMULATOR*.
# It does NOT collect passwords, tokens, cookies, or any private data.
# Use only with informed consent in training environments.

SIMULATED_EMAILS = [
    {
        "id": "it-reset",
        "subject": "Action required: Password expires today",
        "sender": "IT Support <it-support@example.com>",
        "preview": "Your password expires today. Click to keep access.",
        "body_html": """<p>Hello,</p>
        <p>Our records show your password will expire <strong>today</strong>. To avoid interruption, please confirm your details.</p>
        <p><a class="cta" href="{{ url_for('click_link', email_id='it-reset') }}">Confirm now</a></p>
        <p class="fineprint">If you did not request this, ignore this email.</p>
        """,
        "red_flags": [
            "Creates urgency ("expires today")",
            "Generic greeting ("Hello")",
            "Pressure to click a link immediately",
        ],
    },
    {
        "id": "parcel",
        "subject": "Missed delivery — schedule redelivery",
        "sender": "Delivery Updates <notify@example.com>",
        "preview": "We missed you. Schedule redelivery.",
        "body_html": """<p>We attempted to deliver your parcel but couldn't complete delivery.</p>
        <p>Please schedule a redelivery within <strong>12 hours</strong>:</p>
        <p><a class="cta" href="{{ url_for('click_link', email_id='parcel') }}">Schedule redelivery</a></p>
        <p class="fineprint">Reference: 8492-1120</p>
        """,
        "red_flags": [
            "Unrealistic short deadline",
            "No identifying details (carrier/order)",
            "Encourages quick action",
        ],
    },
    {
        "id": "invoice",
        "subject": "Invoice attached — payment overdue",
        "sender": "Accounts <accounts@example.com>",
        "preview": "Payment is overdue. Review invoice.",
        "body_html": """<p>Hi,</p>
        <p>Your payment is overdue. Please review the invoice and settle immediately to avoid penalties.</p>
        <p><a class="cta" href="{{ url_for('click_link', email_id='invoice') }}">View invoice</a></p>
        <p class="fineprint">Thank you.</p>
        """,
        "red_flags": [
            "Vague sender/organization",
            "Threat of penalties",
            "Pushes to click rather than use known billing channel",
        ],
    },
]

QUIZ = [
    {
        "id": "q1",
        "question": "What is the safest first step if you receive an unexpected email asking you to click a link?",
        "choices": [
            "Click quickly to avoid missing a deadline",
            "Reply asking for more details",
            "Verify via a trusted channel (e.g., company portal or known phone number)",
            "Forward it to friends to see what they think",
        ],
        "answer_index": 2,
        "explain": "Verify using a trusted channel you control (not the email)."
    },
    {
        "id": "q2",
        "question": "Which is a common red flag of phishing?",
        "choices": [
            "Personalized details you already expect",
            "Urgency or threats that push you to act immediately",
            "Clear contact info and normal tone",
            "A message you requested moments ago",
        ],
        "answer_index": 1,
        "explain": "Urgency/threats are often used to bypass careful thinking."
    },
    {
        "id": "q3",
        "question": "If a link looks like 'paypa1.com' instead of 'paypal.com', what should you do?",
        "choices": [
            "Click it; it's probably a new domain",
            "Hover/copy to inspect and avoid clicking; go directly to the real site",
            "Type your password to check if it works",
            "Ignore the spelling; it doesn't matter",
        ],
        "answer_index": 1,
        "explain": "Look‑alike domains are classic phishing. Use the legitimate site directly."
    },
    {
        "id": "q4",
        "question": "Where should you report suspicious emails in an organization (best practice)?",
        "choices": [
            "Public social media",
            "Your IT/security team or the designated reporting mailbox",
            "Random coworkers only",
            "No need to report; just delete",
        ],
        "answer_index": 1,
        "explain": "Reporting helps protect others and improves detection."
    },
    {
        "id": "q5",
        "question": "Two-factor authentication (2FA) helps because…",
        "choices": [
            "It replaces the need for passwords forever",
            "It makes phishing impossible",
            "It adds an extra step so stolen passwords alone are less useful",
            "It only works on social media",
        ],
        "answer_index": 2,
        "explain": "2FA reduces risk if a password is compromised, though phishing can still target 2FA."
    },
]


def get_email(email_id: str):
    for e in SIMULATED_EMAILS:
        if e["id"] == email_id:
            return e
    return None


@app.route("/")
def index():
    return render_template("index.html", emails=SIMULATED_EMAILS)


@app.route("/email/<email_id>")
def view_email(email_id):
    email = get_email(email_id)
    if not email:
        abort(404)
    return render_template("email.html", email=email)


@app.route("/click/<email_id>")
def click_link(email_id):
    email = get_email(email_id)
    if not email:
        abort(404)

    # Record a consent-safe training event in session only (no personal data).
    session.setdefault("events", [])
    session["events"].append({
        "type": "clicked_simulated_link",
        "email_id": email_id,
        "ts": datetime.utcnow().isoformat() + "Z",
    })
    session.modified = True

    return render_template("clicked.html", email=email)


@app.route("/quiz")
def quiz():
    # Provide quiz content to frontend. We intentionally do not ask for credentials.
    return render_template("quiz.html", quiz=QUIZ)


@app.route("/api/quiz")
def api_quiz():
    # JSON endpoint in case you want to build a richer frontend later.
    safe_quiz = [
        {k: v for k, v in q.items() if k in ("id", "question", "choices")}
        for q in QUIZ
    ]
    return jsonify({"quiz": safe_quiz})


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    answers = data.get("answers")
    if not isinstance(answers, dict):
        return jsonify({"ok": False, "error": "Invalid payload"}), 400

    score = 0
    results = []
    for q in QUIZ:
        qid = q["id"]
        user_choice = answers.get(qid)
        correct = (user_choice == q["answer_index"])
        if correct:
            score += 1
        results.append({
            "id": qid,
            "question": q["question"],
            "choices": q["choices"],
            "user_choice": user_choice,
            "answer_index": q["answer_index"],
            "correct": correct,
            "explain": q["explain"],
        })

    session["last_score"] = {"score": score, "total": len(QUIZ)}
    session["last_results"] = results
    session.modified = True

    return jsonify({"ok": True, "score": score, "total": len(QUIZ)})


@app.route("/results")
def results():
    last_score = session.get("last_score")
    last_results = session.get("last_results")
    if not last_score or not last_results:
        return redirect(url_for("quiz"))
    return render_template("result.html", last_score=last_score, last_results=last_results)


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
