"""
VoteSecure — Flask Backend
Database : Firebase Firestore
OTP      : Gmail SMTP
Config   : Environment variables (Railway dashboard / .env file)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib, secrets, re, smtplib, os, json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import firebase_admin
from firebase_admin import credentials, firestore
from flask import send_file

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/app")
def frontend():
    return send_file("index.html")



@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response

# ═══════════════════════════════════════════════════════════════
#  CONFIG — reads from environment variables
#  Locally:  set these in your .env file (or export in terminal)
#  Railway:  set these in Railway dashboard → Variables tab
# ═══════════════════════════════════════════════════════════════

GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS", "")
FIREBASE_JSON  = os.environ.get("FIREBASE_JSON", "")

# ── FIREBASE INIT ────────────────────────────────────────────
def init_firebase():
    if firebase_admin._apps:
        return
    if FIREBASE_JSON:
        # Railway: credentials stored as JSON string in env var
        cred = credentials.Certificate(json.loads(FIREBASE_JSON))
    elif os.path.exists("firebase-key.json"):
        # Local: credentials stored as a file
        cred = credentials.Certificate("firebase-key.json")
    else:
        raise RuntimeError(
            "No Firebase credentials found!\n"
            "Local: place firebase-key.json in project folder\n"
            "Railway: set FIREBASE_JSON environment variable"
        )
    firebase_admin.initialize_app(cred)

init_firebase()
db             = firestore.client()
voters_col     = db.collection("voters")
candidates_col = db.collection("candidates")
votes_col      = db.collection("votes")

# ── SEED CANDIDATES (once, if empty) ────────────────────────
def seed_candidates():
    if len(candidates_col.limit(1).get()) == 0:
        for c in [
            {"name": "Satish Kumar", "party": "BJP",      "symbol": "🪷"},
            {"name": "Dhruv Khanna", "party": "Congress", "symbol": "✋"},
            {"name": "Priya Sharma", "party": "AAP",      "symbol": "🧹"},
            {"name": "Ramesh Yadav", "party": "SP",       "symbol": "🚲"},
        ]:
            candidates_col.add(c)
        print("[DB] Candidates seeded.")

seed_candidates()

# ── HELPERS ──────────────────────────────────────────────────
def validate_email(e):
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', e))

def validate_phone(phone):
    phone = re.sub(r'[\s\-]', '', phone)
    if phone.startswith("+91"):  phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12: phone = phone[2:]
    return bool(re.match(r'^[6-9]\d{9}$', phone)), phone

def generate_otp():
    return str(secrets.randbelow(900000) + 100000)

def hash_password(pw):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), b"votesecure_v2", 200_000).hex()

def hash_aadhar(a):
    return hashlib.sha256(a.encode()).hexdigest()

def send_otp_email(to_email, otp, name):
    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("[Email] Gmail not configured — skipping send")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"VoteSecure — Your OTP is {otp}"
        msg["From"]    = f"VoteSecure 🗳️ <{GMAIL_USER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;background:#f7f5f0;border-radius:16px;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:40px;">🗳️</span>
            <h2 style="font-family:Georgia,serif;color:#0d0d0f;margin:8px 0 4px;">VoteSecure</h2>
            <p style="color:#7a7a8c;font-size:13px;margin:0;">India's Secure Digital Ballot</p>
          </div>
          <p style="color:#3a3a45;font-size:15px;">Hi <strong>{name}</strong>,</p>
          <p style="color:#3a3a45;font-size:14px;line-height:1.6;">Your one-time password to verify your email is:</p>
          <div style="background:#0d0d0f;color:white;text-align:center;padding:24px;border-radius:12px;margin:20px 0;">
            <span style="font-family:monospace;font-size:40px;font-weight:bold;letter-spacing:12px;">{otp}</span>
          </div>
          <p style="color:#7a7a8c;font-size:12px;">⏱ Expires in 10 minutes. 🔒 Do not share with anyone.</p>
          <hr style="border:none;border-top:1px solid #e0dcd2;margin:20px 0;">
          <p style="color:#7a7a8c;font-size:11px;text-align:center;">If you didn't register on VoteSecure, ignore this email.</p>
        </div>
        """, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(GMAIL_USER, GMAIL_APP_PASS)
            s.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f"[Email] OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email Error] {e}")
        return False

def get_voter_by_email(email):
    docs = voters_col.where("email", "==", email).limit(1).get()
    return (docs[0].id, docs[0].to_dict()) if docs else (None, None)

# ── ROUTES ───────────────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({"status": "VoteSecure backend running ✓"})


@app.route("/register", methods=["POST"])
def register():
    data     = request.get_json(silent=True) or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")
    phone    = (data.get("phone") or "").strip()
    aadhar   = (data.get("aadhar") or "").replace(" ", "")

    if len(name) < 2:              return jsonify({"error": "Enter your full name"}), 400
    if not validate_email(email):  return jsonify({"error": "Invalid email address"}), 400
    if len(password) < 8:          return jsonify({"error": "Password must be at least 8 characters"}), 400
    is_valid, clean_phone = validate_phone(phone)
    if not is_valid:               return jsonify({"error": "Enter a valid 10-digit Indian mobile number"}), 400
    if not re.match(r'^\d{12}$', aadhar): return jsonify({"error": "Aadhar must be exactly 12 digits"}), 400

    if get_voter_by_email(email)[0]:
        return jsonify({"error": "Email already registered"}), 409
    if voters_col.where("phone", "==", clean_phone).limit(1).get():
        return jsonify({"error": "Phone already registered"}), 409

    otp = generate_otp()
    now = datetime.now().isoformat()
    voters_col.add({
        "name": name, "email": email, "password": hash_password(password),
        "phone": clean_phone, "aadhar_hash": hash_aadhar(aadhar),
        "otp": otp, "otp_timestamp": now, "otp_attempts": 0,
        "last_otp_sent": now, "is_verified": False, "has_voted": False, "created_at": now,
    })

    sent = send_otp_email(email, otp, name)
    if sent:
        return jsonify({"message": f"OTP sent to {email}"})
    return jsonify({"message": "Registered! (Email not configured — use OTP below)", "debug_otp": otp})


@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not validate_email(email): return jsonify({"error": "Invalid email"}), 400

    doc_id, user = get_voter_by_email(email)
    if not doc_id:        return jsonify({"error": "Email not registered"}), 404
    if user["is_verified"]: return jsonify({"error": "Already verified — please login"}), 400

    if user.get("last_otp_sent"):
        elapsed = (datetime.now() - datetime.fromisoformat(user["last_otp_sent"])).total_seconds()
        if elapsed < 60:
            return jsonify({"error": f"Wait {int(60-elapsed)}s before resending"}), 429

    otp = generate_otp()
    now = datetime.now().isoformat()
    voters_col.document(doc_id).update({"otp": otp, "otp_timestamp": now, "otp_attempts": 0, "last_otp_sent": now})
    sent = send_otp_email(email, otp, user["name"])
    return jsonify({"message": "OTP resent to " + email, "debug_otp": otp if not sent else None})


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp   = (data.get("otp") or "").strip()

    if not validate_email(email):       return jsonify({"error": "Invalid email"}), 400
    if not re.match(r'^\d{6}$', otp):  return jsonify({"error": "OTP must be 6 digits"}), 400

    doc_id, user = get_voter_by_email(email)
    if not doc_id:          return jsonify({"error": "Email not registered"}), 404
    if user["is_verified"]: return jsonify({"error": "Already verified — please login"}), 400
    if user.get("otp_attempts", 0) >= 5:
        return jsonify({"error": "Too many wrong attempts. Please re-register."}), 429

    if user.get("otp_timestamp"):
        if datetime.now() - datetime.fromisoformat(user["otp_timestamp"]) > timedelta(minutes=10):
            return jsonify({"error": "OTP expired. Click Resend OTP."}), 400

    if user.get("otp") == otp:
        voters_col.document(doc_id).update({"is_verified": True, "otp": None, "otp_attempts": 0})
        return jsonify({"message": "✓ Email verified! You can now login."})

    voters_col.document(doc_id).update({"otp_attempts": firestore.Increment(1)})
    return jsonify({"error": f"Wrong OTP. {5 - user.get('otp_attempts',0) - 1} attempts left."}), 400


@app.route("/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")
    if not email or not password: return jsonify({"error": "Email and password required"}), 400

    doc_id, user = get_voter_by_email(email)
    if not user or user["password"] != hash_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user["is_verified"]:
        return jsonify({"error": "Please verify your email first"}), 403

    return jsonify({"message": "Login successful", "voter_id": doc_id, "name": user["name"], "has_voted": user["has_voted"]})


@app.route("/candidates", methods=["GET"])
def get_candidates():
    return jsonify([{"candidate_id": d.id, **d.to_dict()} for d in candidates_col.get()])


@app.route("/vote", methods=["POST"])
def vote():
    data         = request.get_json(silent=True) or {}
    voter_id     = data.get("voter_id")
    candidate_id = data.get("candidate_id")
    if not voter_id or not candidate_id: return jsonify({"error": "Missing fields"}), 400

    voter_ref = voters_col.document(voter_id)
    voter_doc = voter_ref.get()
    if not voter_doc.exists:          return jsonify({"error": "Voter not found"}), 404
    if voter_doc.to_dict()["has_voted"]: return jsonify({"error": "You have already voted"}), 400

    cand_doc = candidates_col.document(candidate_id).get()
    if not cand_doc.exists: return jsonify({"error": "Invalid candidate"}), 400

    c = cand_doc.to_dict()
    votes_col.add({"candidate_id": candidate_id, "timestamp": datetime.now().isoformat()})
    voter_ref.update({"has_voted": True})
    return jsonify({"message": f"Vote cast for {c['name']} ({c['party']}). Thank you!"})


@app.route("/admin/results", methods=["GET"])
def results():
    vote_counts = {}
    for v in votes_col.get():
        cid = v.to_dict()["candidate_id"]
        vote_counts[cid] = vote_counts.get(cid, 0) + 1

    out = []
    for c in candidates_col.get():
        d = c.to_dict()
        out.append({"candidate_id": c.id, "name": d["name"], "party": d["party"],
                    "symbol": d.get("symbol","🗳️"), "vote_count": vote_counts.get(c.id, 0)})
    out.sort(key=lambda x: x["vote_count"], reverse=True)
    return jsonify({"total_votes": sum(r["vote_count"] for r in out), "results": out})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
