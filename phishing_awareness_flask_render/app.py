import json
import os
from datetime import datetime

from flask import (
    Flask, render_template, redirect, url_for,
    request, session, abort, jsonify
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
USE_OPENAI = os.getenv("USE_OPENAI", "1") == "1" and bool(os.getenv("OPENAI_API_KEY"))


TITLE_MAP = {
    "cybersecurity": "Cybersecurity Awareness",
}

QUIZ_SCHEMA = {
    "name": "threatlens_ai_quiz",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "quiz": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "category": {"type": "string"},
                        "question": {"type": "string"},
                        "choices": {
                            "type": "array",
                            "minItems": 4,
                            "maxItems": 4,
                            "items": {"type": "string"}
                        },
                        "answer_index": {"type": "integer"},
                        "explain": {"type": "string"}
                    },
                    "required": [
                        "id",
                        "category",
                        "question",
                        "choices",
                        "answer_index",
                        "explain"
                    ]
                }
            }
        },
        "required": ["quiz"]
    }
}

FEEDBACK_SCHEMA = {
    "name": "threatlens_feedback",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "knowledge_gaps": {"type": "array", "items": {"type": "string"}},
            "tailored_scenario": {"type": "string"},
            "risk_explanation": {"type": "string"},
            "warning_signs": {"type": "array", "items": {"type": "string"}},
            "safe_action": {"type": "string"},
            "next_practice_question": {"type": "string"},
        },
        "required": [
            "summary",
            "knowledge_gaps",
            "tailored_scenario",
            "risk_explanation",
            "warning_signs",
            "safe_action",
            "next_practice_question",
        ],
    },
}

TRAINING_SCHEMA = {
    "name": "threatlens_training_material",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "introduction": {"type": "string"},
            "learning_objectives": {
                "type": "array",
                "items": {"type": "string"}
            },
            "mini_lesson": {"type": "string"},
            "example_scenario": {"type": "string"},
            "key_takeaways": {
                "type": "array",
                "items": {"type": "string"}
            },
            "practice_questions": {
                "type": "array",
                "items": {"type": "string"}
            },
            "safe_actions": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": [
            "title",
            "introduction",
            "learning_objectives",
            "mini_lesson",
            "example_scenario",
            "key_takeaways",
            "practice_questions",
            "safe_actions"
        ]
    }
}





def fallback_ai_feedback(scenario, weak_categories, score, total):
    readable = ", ".join(weak_categories) if weak_categories else "general safe behaviour"

    return {
        "summary": f"You scored {score}/{total}. Focus next on {readable}.",
        "knowledge_gaps": weak_categories or ["reinforcement"],
        "tailored_scenario": f"You receive another {TITLE_MAP.get(scenario, 'cybersecurity')} message with urgent wording and a link.",
        "risk_explanation": "Attackers use urgency, confusing instructions and familiar brands to make people act before checking.",
        "warning_signs": [
            "Unexpected request",
            "Urgent deadline",
            "Link, login page or payment instruction in the message",
        ],
        "safe_action": "Use a known official website, app, phone number or internal reporting channel instead of the message link.",
        "next_practice_question": "What trusted channel would you use to verify this before clicking, logging in or paying?",
    }


# =========================
# OPENAI CONFIG
# =========================
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = "gpt-4o-mini"

USE_OPENAI = (
    OPENAI_API_KEY is not None
    and OPENAI_API_KEY.startswith("sk-")
)

def generate_ai_feedback(scenario, quiz_results, score, total):

    weak_categories = sorted({
        r["category"]
        for r in quiz_results
        if not r["correct"]
    })

    # Get user profile for role-based feedback
    session_id = session.get("session_id")
    state = APP_STATE.get(session_id, {})
    profile = state.get("profile", {})

    department = profile.get("department", "General")
    role = profile.get("role", "Employee")

    # Adaptive feedback level
    score_ratio = score / total if total else 0

    if score_ratio < 0.5:
        feedback_level = "supportive beginner feedback"
    elif score_ratio < 0.8:
        feedback_level = "targeted improvement feedback"
    else:
        feedback_level = "advanced awareness reinforcement"

    # =========================
    # LOCAL FALLBACK
    # =========================
    if not USE_OPENAI:

        feedback = fallback_ai_feedback(
            scenario,
            weak_categories,
            score,
            total
        )

        feedback["summary"] = (
            "[LOCAL FALLBACK] "
            + feedback["summary"]
        )

        return feedback

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=OPENAI_API_KEY
        )

        prompt_payload = {
            "department": department,
            "role": role,
            "feedback_level": feedback_level,

            "scenario": scenario,
            "audience": "non-technical adult learner",

            "score": {
                "score": score,
                "total": total
            },

            "weak_categories": weak_categories,

            "incorrect_questions": [
                {
                    "question": r["question"],

                    "user_answer": (
                        r["choices"][r["user_choice"]]
                        if r["user_choice"] is not None
                        else "No answer"
                    ),

                    "correct_answer": (
                        r["choices"][r["answer_index"]]
                    ),

                    "category": r["category"],
                }

                for r in quiz_results
                if not r["correct"]
            ],
        }

        completion = client.chat.completions.create(

            model=OPENAI_MODEL,

            temperature=0.75,

            messages=[

                {
                    "role": "system",

                    "content": (
                        "You are ThreatLens AI, a personalised cybersecurity awareness coach.\n\n"
                        "Give role-specific feedback based on the user's department, role, quiz score, "
                        "and incorrect answers.\n\n"

                        "Rules:\n"
                        "- Make the feedback specific to their workplace role.\n"
                        "- Explain why their mistakes matter in their department.\n"
                        "- Avoid generic cybersecurity advice.\n"
                        "- Use realistic examples they may face at work.\n"
                        "- Be supportive, not scary or judgmental.\n"
                        "- Keep language beginner-friendly.\n"
                        "- Focus only on defensive awareness and safe behaviour.\n"
                        "- Give practical next steps they can actually follow.\n\n"

                        "Examples:\n"
                        "- Finance mistakes should connect to invoice fraud, payment changes, fake suppliers.\n"
                        "- HR mistakes should connect to payroll changes, employee records, impersonation.\n"
                        "- Sales mistakes should connect to fake leads, attachments, CRM login scams.\n"
                        "- Managers should learn about approval pressure and executive impersonation.\n"
                        "- Students should learn about portal, scholarship and account-reset scams.\n\n"

                        "The feedback should feel personally written for this user's role and mistakes."
                    ),
                },

                {
                    "role": "user",

                    "content": (
                        "Generate tailored cybersecurity feedback "
                        "using this structured data:\n"
                        + json.dumps(prompt_payload)
                    ),
                },
            ],

            response_format={
                "type": "json_schema",

                "json_schema": {
                    "name": FEEDBACK_SCHEMA["name"],
                    "strict": True,
                    "schema": FEEDBACK_SCHEMA["schema"],
                },
            },
        )

        feedback = json.loads(
            completion.choices[0].message.content
        )

        return feedback

    except Exception as exc:

        feedback = fallback_ai_feedback(
            scenario,
            weak_categories,
            score,
            total
        )

        feedback["summary"] = (
            "[OPENAI ERROR - LOCAL FALLBACK] "
            + feedback["summary"]
        )

        feedback["debug_error"] = str(exc)

        print("\n========== OPENAI ERROR ==========")
        print(str(exc))
        print("==================================\n")

        return feedback
    
@app.route("/")
def index():
    return render_template("profile.html")

@app.route("/start-assessment", methods=["POST"])
def start_assessment():
    department = request.form.get("department", "").strip()
    role = request.form.get("role", "").strip()

    if not department:
        department = "General"
    if not role:
        role = "Employee"

    session_id = session.get("session_id")
    if not session_id:
        session_id = datetime.utcnow().isoformat()
        session["session_id"] = session_id

    APP_STATE[session_id] = {
        "profile": {
            "department": department,
            "role": role
        }
    }

    session.modified = True

    return redirect(url_for("quiz_scenario", scenario="cybersecurity"))

@app.route("/quiz")
def quiz():
    return redirect(url_for("index"))

APP_STATE = {}


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    answers = data.get("answers")
    scenario = data.get("scenario")

    if not isinstance(answers, dict) or not isinstance(scenario, str):
        return jsonify({"ok": False, "error": "Invalid payload"}), 400

    session_id = session.get("session_id")
    state = APP_STATE.get(session_id, {})

    quiz_data = state.get("active_quiz")
    active_scenario = state.get("active_scenario")

    if not quiz_data or active_scenario != scenario:
        return jsonify({
            "ok": False,
            "error": "Quiz session expired. Please retake the quiz."
        }), 400

    score = 0
    results = []

    for q in quiz_data:
        qid = q["id"]
        raw_choice = answers.get(qid)

        try:
            user_choice = int(raw_choice) if raw_choice is not None else None
        except (TypeError, ValueError):
            user_choice = None

        correct = user_choice == q["answer_index"]

        if correct:
            score += 1

        results.append({
            "id": qid,
            "category": q.get("category", "general"),
            "question": q["question"],
            "choices": q["choices"],
            "user_choice": user_choice,
            "answer_index": q["answer_index"],
            "correct": correct,
            "explain": q["explain"],
        })

    ai_feedback = generate_ai_feedback(scenario, results, score, len(quiz_data))

    state["last_score"] = {
        "score": score,
        "total": len(quiz_data),
        "scenario": scenario,
    }
    state["last_results"] = results
    state["ai_feedback"] = ai_feedback

    APP_STATE[session_id] = state

    return jsonify({"ok": True, "score": score, "total": len(quiz_data)})

@app.route("/results")
def results():
    session_id = session.get("session_id")
    state = APP_STATE.get(session_id, {})

    last_score = state.get("last_score")
    last_results = state.get("last_results")

    if not last_score or not last_results:
        return redirect(url_for("quiz"))

    scenario = last_score.get("scenario")

    return render_template(
        "result.html",
        last_score=last_score,
        last_results=last_results,
        ai_feedback=state.get("ai_feedback"),
        results_title=f"{TITLE_MAP.get(scenario, 'Awareness')} Results",
    )

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({
            "ok": False,
            "error": "No message"
        }), 400

    try:
        from openai import OpenAI

        session_id = session.get("session_id")
        state = APP_STATE.get(session_id, {})

        profile = state.get("profile", {})
        ai_feedback = state.get("ai_feedback", {})
        last_score = state.get("last_score", {})
        training_material = state.get("training_material", {})

        chat_context = {
            "department": profile.get("department", "General"),
            "role": profile.get("role", "Employee"),
            "knowledge_gaps": ai_feedback.get("knowledge_gaps", []),
            "last_score": last_score,
            "training_title": training_material.get("title", "")
        }

        chat_history = state.get("chat_history", [])
        chat_history = chat_history[-6:]

        client = OpenAI(api_key=OPENAI_API_KEY)

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.5,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are ThreatLens AI, a cybersecurity awareness assistant.\n\n"
                        "You ONLY answer questions related to cybersecurity awareness, online safety, "
                        "phishing, scams, passwords, MFA, suspicious links, social engineering, "
                        "safe data handling, privacy, workplace security, and the user's training content.\n\n"
                        "Use the user's department, role, quiz score, knowledge gaps, and previous chat context "
                        "to personalise answers.\n\n"
                        "If the user asks something unrelated, politely refuse and redirect them back "
                        "to cybersecurity learning.\n\n"
                        "Keep answers short, safe, beginner-friendly, and conversational.\n"
                        "Do not answer general knowledge questions, trivia, politics, math, travel, cooking, coding, "
                        "or unrelated topics."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "User training context:\n"
                        + json.dumps(chat_context)
                    ),
                },
                *chat_history,
                {
                    "role": "user",
                    "content": message,
                },
            ],
        )

        reply = completion.choices[0].message.content

        chat_history.append({
            "role": "user",
            "content": message
        })

        chat_history.append({
            "role": "assistant",
            "content": reply
        })

        state["chat_history"] = chat_history[-10:]
        APP_STATE[session_id] = state

        return jsonify({
            "ok": True,
            "reply": reply
        })
    
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 500
        
                
def generate_training_material():
    session_id = session.get("session_id")
    state = APP_STATE.get(session_id, {})

    last_score = state.get("last_score")
    ai_feedback = state.get("ai_feedback")
    last_results = state.get("last_results", [])
    profile = state.get("profile", {})

    if not last_score or not ai_feedback:
        return None

    score_ratio = last_score.get("score", 0) / last_score.get("total", 1)
    
    if score_ratio < 0.5:
        difficulty = "beginner"
    elif score_ratio < 0.8:
        difficulty = "intermediate"
    else:
        difficulty = "advanced awareness reinforcement"

    department = profile.get("department", "General")
    role = profile.get("role", "Employee")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)

        prompt_payload = {
            "department": department,
            "role": role,
            "training_level": difficulty,

            "scenario": last_score.get("scenario"),

            "score": {
                "score": last_score.get("score"),
                "total": last_score.get("total")
            },

            "knowledge_gaps": ai_feedback.get("knowledge_gaps", []),

            "risk_explanation": ai_feedback.get("risk_explanation", ""),

            "safe_action": ai_feedback.get("safe_action", ""),

            "quiz_review": [
                {
                    "question": r["question"],
                    "correct": r["correct"],
                    "category": r.get("category", "general"),
                    "explanation": r.get("explain", "")
                }
                for r in last_results
            ]
        }

        completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.75,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are ThreatLens AI, an adaptive cybersecurity awareness coach.\n\n"
                    "Create personalised, defensive cybersecurity training for non-technical users.\n\n"
                    "Rules:\n"
                    "- Tailor the lesson to the user's department and role.\n"
                    "- Use the user's quiz score and mistakes to decide what to teach.\n"
                    "- Focus on realistic workplace situations they may actually face.\n"
                    "- Explain why their weak areas are risky.\n"
                    "- Give practical safe actions, not technical hacking details.\n"
                    "- Avoid generic cybersecurity textbook content.\n"
                    "- Keep the tone supportive, clear and beginner-friendly.\n"
                    "- Make examples specific to the user's job context.\n\n"
                    "Examples of tailoring:\n"
                    "- HR: payroll change scams, employee impersonation, sensitive staff data.\n"
                    "- Finance: invoice fraud, payment approval scams, fake supplier updates.\n"
                    "- Sales: fake customer attachments, CRM login scams, malicious proposals.\n"
                    "- Education: student portal scams, fake scholarship links, account reset requests.\n"
                    "- Healthcare: patient privacy, fake medical record requests, phishing emails.\n"
                    "- Managers: urgent approval scams, executive impersonation, data-sharing pressure.\n"
                    "- Customer support: emotional manipulation, fake account ownership claims.\n\n"
                    "The final training must feel like it was written specifically for this user."
                )
            },
            {
                "role": "user",
                "content": (
                    "Create a personalised cybersecurity training lesson using this structured data:\n\n"
                    + json.dumps(prompt_payload)
                )
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": TRAINING_SCHEMA["name"],
                "strict": True,
                "schema": TRAINING_SCHEMA["schema"]
            }
        }
    )

        return json.loads(completion.choices[0].message.content)

    except Exception as exc:
        print("Training generation error:", str(exc))
        return {
            "title": "Local Training Material",
            "introduction": "This lesson was generated locally because AI training generation was unavailable.",
            "learning_objectives": [
                "Recognise suspicious messages",
                "Verify links safely",
                "Use trusted channels before acting"
            ],
            "mini_lesson": "Cyber attackers often use urgency, fear and familiar-looking brands to make people click quickly. A safer approach is to pause, check the sender, avoid unexpected links, and use official websites or apps.",
            "example_scenario": "You receive an urgent message saying your account will be locked unless you click a link. Instead of clicking, you open the official website yourself or contact support using a trusted number.",
            "key_takeaways": [
                "Do not trust urgent links automatically",
                "Check the real sender and domain",
                "Use official apps or websites",
                "Report suspicious messages"
            ],
            "practice_questions": [
                "What should you check before clicking a link?",
                "Why is urgency a warning sign?",
                "How can you verify a message safely?"
            ],
            "safe_actions": [
                "Pause before clicking",
                "Use a trusted official channel",
                "Report suspicious messages"
            ]
        }


@app.route("/quiz/<scenario>")
def quiz_scenario(scenario):
    quiz_data = generate_ai_quiz(scenario)

    if not quiz_data:
        abort(404)

    session_id = session.get("session_id")
    if not session_id:
        session_id = datetime.utcnow().isoformat()
        session["session_id"] = session_id

    state = APP_STATE.get(session_id, {})
    state["active_quiz"] = quiz_data
    state["active_scenario"] = scenario
    APP_STATE[session_id] = state

    session.modified = True

    safe_quiz = [
        {k: v for k, v in q.items() if k in ("id", "question", "choices")}
        for q in quiz_data
    ]

    return render_template(
        "quiz.html",
        quiz=safe_quiz,
        quiz_title=f"AI Generated {TITLE_MAP.get(scenario, 'Awareness')} Quiz",
        scenario=scenario,
    )
    
@app.route("/training")
def training():
    session_id = session.get("session_id")
    state = APP_STATE.get(session_id, {})

    material = generate_training_material()

    if not material:
        return redirect(url_for("results"))

    state["training_material"] = material
    APP_STATE[session_id] = state

    return render_template(
        "training.html",
        material=material
    )
    
def generate_ai_quiz(scenario):
    fallback_quiz = None
    session_id = session.get("session_id")
    state = APP_STATE.get(session_id, {})
    profile = state.get("profile", {})

    department = profile.get("department", "General")
    role = profile.get("role", "Employee")

    if not USE_OPENAI:
        return fallback_quiz

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)

        prompt_payload = {
            "scenario": "cybersecurity awareness",
            "department": department,
            "role": role,
            "audience": "non-technical adult learner",
            "requirement": (
                "Generate 5 beginner-friendly multiple-choice cybersecurity awareness questions "
                "tailored to the user's department and role."
            ),
            "allowed_topics": [
                "phishing recognition",
                "link safety",
                "unsafe login pages",
                "password and MFA safety",
                "incident reporting",
                "social engineering",
                "payment verification",
                "safe handling of work data"
            ]
        }

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.8,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are ThreatLens AI, an expert cybersecurity awareness trainer "
                        "for workplace employees and students.\n\n"

                        "Your job is to create realistic, role-specific cybersecurity "
                        "awareness quiz questions.\n\n"

                        "IMPORTANT RULES:\n"
                        "- Questions MUST feel realistic for the user's actual department and role.\n"
                        "- Avoid generic IT-only cybersecurity questions unless the role is IT.\n"
                        "- Use believable workplace scenarios, communication styles and workflows.\n"
                        "- Focus on human decision-making, social engineering and safe behaviour.\n"
                        "- Questions should sound like situations the employee could genuinely face.\n"
                        "- Include department-specific risks.\n"
                        "- Make scenarios practical, modern and believable.\n"
                        "- Avoid repetitive password-only questions.\n"
                        "- Do not generate highly technical hacking content.\n"
                        "- Keep language beginner-friendly.\n\n"

                        "EXAMPLES:\n"
                        "- HR staff → fake employee payroll update requests\n"
                        "- Finance staff → invoice fraud and urgent transfer scams\n"
                        "- Sales staff → fake customer attachments and CRM login scams\n"
                        "- Students → fake scholarship or portal login emails\n"
                        "- Healthcare → patient record phishing and privacy risks\n"
                        "- Managers → impersonation and urgent approval scams\n"
                        "- Customer service → angry-customer social engineering attempts\n"
                        "- Remote workers → MFA fatigue and fake VPN/login pages\n\n"

                        "Each question must:\n"
                        "- contain a short realistic scenario\n"
                        "- test judgment and safe behaviour\n"
                        "- include exactly 4 choices\n"
                        "- have one clearly best answer\n"
                        "- explain WHY the correct answer is safest"
                    )
                },

                {
                    "role": "user",
                    "content": (
                        f"Generate a cybersecurity awareness quiz for:\n\n"
                        f"Department: {department}\n"
                        f"Role: {role}\n\n"

                        "Requirements:\n"
                        "- Create 5 unique multiple choice questions\n"
                        "- Tailor every question to this specific role and department\n"
                        "- Include realistic workplace situations\n"
                        "- Avoid generic cybersecurity trivia\n"
                        "- Make scenarios immersive and believable\n"
                        "- Include phishing, social engineering, unsafe links, data handling, "
                        "verification and scam awareness where appropriate\n"
                        "- Questions should feel like interactive workplace training"
                    )
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": QUIZ_SCHEMA["name"],
                    "strict": True,
                    "schema": QUIZ_SCHEMA["schema"]
                }
            }
        )

        data = json.loads(completion.choices[0].message.content)
        quiz = data["quiz"]

        for i, q in enumerate(quiz):
            q["id"] = f"ai_{scenario}_{i + 1}"

        return quiz

    except Exception as exc:
        print("AI quiz generation error:", str(exc))
        return fallback_quiz
    
    
    
