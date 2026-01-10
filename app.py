from flask import (
    Flask, render_template, redirect, url_for,
    request, session, abort, jsonify, render_template_string
)
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-me-in-production"  # demo only

# IMPORTANT: Awareness simulator only. No credential collection.

SIMULATED_EMAILS = [
    {
        "id": "it-reset",
        "scenario": "it",
        "subject": "Action required: Password expires today",
        "sender": "IT Support <it-support@example.com>",
        "preview": "Your password expires today. Click to keep access.",
        "body_html": """
            <p>Hello,</p>
            <p>Our records show your password will expire <strong>today</strong>.
               To avoid interruption, please confirm your details.</p>
            <p><a class="cta" href="{{ url_for('click_link', email_id='it-reset') }}">Confirm now</a></p>
            <p class="fineprint">If you did not request this, ignore this email.</p>
        """,
        "red_flags": [
            'Creates urgency ("expires today")',
            "Generic greeting (\"Hello\")",
            "Pressure to click a link immediately",
        ],
    },
    {
        "id": "parcel",
        "scenario": "delivery",
        "subject": "Missed delivery — schedule redelivery",
        "sender": "Delivery Updates <notify@example.com>",
        "preview": "We missed you. Schedule redelivery.",
        "body_html": """
            <p>We attempted to deliver your parcel but couldn't complete delivery.</p>
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
        "scenario": "finance",
        "subject": "Invoice attached — payment overdue",
        "sender": "Accounts <accounts@example.com>",
        "preview": "Payment is overdue. Review invoice.",
        "body_html": """
            <p>Hi,</p>
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

# Scenario-based quizzes (enterprise-style)
QUIZZES = {
    "it": [
        {
            "id": "it_q1",
            "question": "A password-expiry email asks you to click a link. What is the safest first step?",
            "choices": [
                "Click the link quickly to avoid lockout",
                "Reply to the email asking if it's real",
                "Go to the official company password portal (bookmark/known URL) or contact IT via a trusted channel",
                "Forward to coworkers to see if they received it",
            ],
            "answer_index": 2,
            "explain": "Use a trusted channel you control (known portal/phone) — not the email link."
        },
        {
            "id": "it_q2",
            "question": "Which practice best reduces risk if your password is stolen?",
            "choices": [
                "Reusing the same password everywhere",
                "Two-factor authentication (2FA/MFA)",
                "Sharing passwords with teammates",
                "Saving passwords in plain text",
            ],
            "answer_index": 1,
            "explain": "MFA makes a stolen password alone less useful (though not perfect)."
        },
        {
            "id": "it_q3",
            "question": "A login page appears after clicking. What is a strong sign it might be fake?",
            "choices": [
                "The URL domain is slightly misspelled or unfamiliar",
                "The page has a logo",
                "It asks for your username",
                "It loads quickly",
            ],
            "answer_index": 0,
            "explain": "Look-alike domains (typosquatting) are a common phishing trick."
        },
        {
            "id": "it_q4",
            "question": "What should you do if you already clicked a suspicious link (best practice)?",
            "choices": [
                "Do nothing and hope for the best",
                "Immediately report to IT/Security and follow their instructions",
                "Delete the email and move on",
                "Post it on social media",
            ],
            "answer_index": 1,
            "explain": "Reporting quickly helps contain risk and protect others."
        },
        {
            "id": "it_q5",
            "question": "Which is the safest way to verify an email sender?",
            "choices": [
                "Trust the display name (e.g., 'IT Support')",
                "Check the 'Reply-To' and actual address domain, and verify through official contacts",
                "Assume internal emails are always safe",
                "Only look at the subject line",
            ],
            "answer_index": 1,
            "explain": "Phishers spoof display names; verify actual sender details and use trusted channels."
        },
    ],
    "delivery": [
        {
            "id": "del_q1",
            "question": "A delivery SMS/email says 'schedule within 12 hours'. What is the best response?",
            "choices": [
                "Click immediately",
                "Ignore the deadline, open the courier’s official app/site yourself and check tracking",
                "Reply with your address to confirm",
                "Send your card details to reschedule",
            ],
            "answer_index": 1,
            "explain": "Use official apps/sites you navigate to yourself. Don’t trust urgent links."
        },
        {
            "id": "del_q2",
            "question": "What is the safest way to check where a link really goes?",
            "choices": [
                "Click it and see",
                "Hover (mouse) or long-press (mobile) to preview, or copy/paste into a safe checker—prefer not clicking at all",
                "Assume short links are safe",
                "Only look at the text color",
            ],
            "answer_index": 1,
            "explain": "Previewing helps detect mismatched or suspicious URLs."
        },
        {
            "id": "del_q3",
            "question": "A QR code in an email claims you must scan to reschedule delivery. What’s a risk?",
            "choices": [
                "QR codes always open safe pages",
                "QR codes can hide malicious URLs and bypass user scrutiny",
                "QR codes can’t contain links",
                "QR codes only work in banks",
            ],
            "answer_index": 1,
            "explain": "QR phishing ('quishing') hides the URL and can lead to malicious pages."
        },
        {
            "id": "del_q4",
            "question": "Which detail is most suspicious for delivery messages?",
            "choices": [
                "A valid tracking number that matches your order",
                "Carrier name matches your recent purchase",
                "No carrier/order details but asks you to click a link",
                "A message you expected",
            ],
            "answer_index": 2,
            "explain": "Lack of verifiable details is a strong phishing red flag."
        },
        {
            "id": "del_q5",
            "question": "If you must enter details on a delivery page, what should you avoid?",
            "choices": [
                "Using the courier’s official app",
                "Entering your password/card details from an unexpected link",
                "Checking tracking from a bookmarked site",
                "Contacting support via known numbers",
            ],
            "answer_index": 1,
            "explain": "Unexpected links are a common way to steal credentials/payment info."
        },
    ],
    "finance": [
        {
            "id": "fin_q1",
            "question": "An email says an invoice is overdue and asks you to pay via a link. Best action?",
            "choices": [
                "Pay immediately to avoid penalties",
                "Verify the request in your official finance system or via a known contact method",
                "Reply 'Is this real?' and wait",
                "Forward to external vendors",
            ],
            "answer_index": 1,
            "explain": "Finance fraud often pressures fast payment—verify via approved systems/channels."
        },
        {
            "id": "fin_q2",
            "question": "Which is a common sign of Business Email Compromise (BEC)/invoice fraud?",
            "choices": [
                "Normal tone and expected process",
                "A sudden change in bank account/payment instructions",
                "A vendor message you were expecting",
                "Invoices only sent through your portal",
            ],
            "answer_index": 1,
            "explain": "Changing payment details is a classic BEC pattern—always verify."
        },
        {
            "id": "fin_q3",
            "question": "What control best prevents fraudulent payments?",
            "choices": [
                "One person approves and pays",
                "Dual approval + vendor bank detail verification (out-of-band)",
                "Paying from personal accounts",
                "Ignoring approvals if urgent",
            ],
            "answer_index": 1,
            "explain": "Separation of duties and out-of-band verification reduce fraud risk."
        },
        {
            "id": "fin_q4",
            "question": "A message says 'CEO needs urgent wire transfer'. What should you do?",
            "choices": [
                "Do it quickly; CEOs are busy",
                "Verify using a known phone number / in-person confirmation and follow policy",
                "Ask them to send their password to confirm identity",
                "Only check the email signature",
            ],
            "answer_index": 1,
            "explain": "CEO fraud relies on urgency—verify through trusted channels and policy."
        },
        {
            "id": "fin_q5",
            "question": "What should you report to security/finance leadership?",
            "choices": [
                "Only successful fraud",
                "Any suspicious invoice/payment request, even if you didn’t act on it",
                "Only emails with attachments",
                "Only messages from unknown senders",
            ],
            "answer_index": 1,
            "explain": "Reporting near-misses improves detection and protects others."
        },
    ],
}


def get_email(email_id: str):
    for e in SIMULATED_EMAILS:
        if e["id"] == email_id:
            return e
    return None


def get_quiz_for_scenario(scenario: str):
    return QUIZZES.get(scenario)


@app.route("/")
def index():
    return render_template("index.html", emails=SIMULATED_EMAILS)


@app.route("/email/<email_id>")
def view_email(email_id):
    email = get_email(email_id)
    if not email:
        abort(404)

    rendered_body = render_template_string(email["body_html"])
    email_view = dict(email)
    email_view["body_html"] = rendered_body

    return render_template("email.html", email=email_view)


@app.route("/click/<email_id>")
def click_link(email_id):
    email = get_email(email_id)
    if not email:
        abort(404)

    session.setdefault("events", [])
    session["events"].append({
        "type": "clicked_simulated_link",
        "email_id": email_id,
        "scenario": email["scenario"],
        "ts": datetime.utcnow().isoformat() + "Z",
    })
    session["last_scenario"] = email["scenario"]
    session.modified = True

    return render_template("clicked.html", email=email)


# Default quiz route: if user visits /quiz, send them to last scenario quiz (or IT as fallback)
@app.route("/quiz")
def quiz():
    scenario = session.get("last_scenario", "it")
    return redirect(url_for("quiz_scenario", scenario=scenario))


# Scenario quiz route
@app.route("/quiz/<scenario>")
def quiz_scenario(scenario):
    quiz_data = get_quiz_for_scenario(scenario)
    if not quiz_data:
        abort(404)

    title_map = {"it": "IT Security Quiz", "delivery": "Delivery Scam Quiz", "finance": "Finance/BEC Quiz"}
    quiz_title = title_map.get(scenario, "Awareness Quiz")

    return render_template("quiz.html", quiz=quiz_data, quiz_title=quiz_title, scenario=scenario)


# Scenario JSON endpoint (optional for future frontend)
@app.route("/api/quiz/<scenario>")
def api_quiz_scenario(scenario):
    quiz_data = get_quiz_for_scenario(scenario)
    if not quiz_data:
        return jsonify({"ok": False, "error": "Unknown scenario"}), 404

    safe_quiz = [{k: v for k, v in q.items() if k in ("id", "question", "choices")} for q in quiz_data]
    return jsonify({"ok": True, "scenario": scenario, "quiz": safe_quiz})


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    answers = data.get("answers")
    scenario = data.get("scenario")  # comes from frontend
    if not isinstance(answers, dict) or not isinstance(scenario, str):
        return jsonify({"ok": False, "error": "Invalid payload"}), 400

    quiz_data = get_quiz_for_scenario(scenario)
    if not quiz_data:
        return jsonify({"ok": False, "error": "Unknown scenario"}), 400

    score = 0
    results = []
    for q in quiz_data:
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

    # store last results per scenario
    session["last_score"] = {"score": score, "total": len(quiz_data), "scenario": scenario}
    session["last_results"] = results
    session.modified = True

    return jsonify({"ok": True, "score": score, "total": len(quiz_data)})


@app.route("/results")
def results():
    last_score = session.get("last_score")
    last_results = session.get("last_results")
    if not last_score or not last_results:
        return redirect(url_for("quiz"))

    title_map = {"it": "IT Security Results", "delivery": "Delivery Scam Results", "finance": "Finance/BEC Results"}
    results_title = title_map.get(last_score.get("scenario"), "Your Results")

    return render_template(
        "result.html",
        last_score=last_score,
        last_results=last_results,
        results_title=results_title
    )


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
