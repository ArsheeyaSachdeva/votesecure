# 🗳️ VoteSecure — Complete Setup Guide

## Files in this project
```
votesecure/
├── app.py              ← Flask backend (never edit credentials here)
├── index.html          ← Frontend (voters open this in browser)
├── requirements.txt    ← Python dependencies
├── Procfile            ← Tells Railway how to run the app
├── firebase-key.json   ← YOU create this (see Step 1)
└── README.md           ← This file
```

---

## STEP 1 — Firebase Setup (one time, takes 5 min)

Firebase is your shared cloud database — all votes from all voters go here.

1. Go to https://console.firebase.google.com
2. Click **"Add project"** → name it `votesecure` → Continue
3. Disable Google Analytics → **Create project**
4. Left sidebar → **Firestore Database** → **Create database**
   - Choose **"Start in test mode"** → Next → pick any location → **Enable**
5. Get your secret key:
   - Click ⚙️ gear → **Project Settings** → **Service accounts** tab
   - Click **"Generate new private key"** → **Generate key**
   - A `.json` file downloads → **rename it `firebase-key.json`**
   - **Place it in the same folder as `app.py`**

> ⚠️ Never share or commit `firebase-key.json` — it's your master key.

---

## STEP 2 — Gmail App Password (2 min)

You need this so Flask can send OTP emails. Uses YOUR Gmail.

1. Go to https://myaccount.google.com/security
2. Make sure **2-Step Verification** is ON
3. Search "App Passwords" in the search bar → click it
4. App: **Mail** | Device: **Other** → type `VoteSecure` → **Generate**
5. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`)

---

## ── OPTION A: Run Locally ──────────────────────────────────

Good for testing. Voters must be on same WiFi as you.

### Set environment variables

**Mac/Linux** — run in terminal before starting Flask:
```bash
export GMAIL_USER="your_gmail@gmail.com"
export GMAIL_APP_PASS="abcd efgh ijkl mnop"
```

**Windows** — run in Command Prompt:
```cmd
set GMAIL_USER=your_gmail@gmail.com
set GMAIL_APP_PASS=abcd efgh ijkl mnop
```

### Install & run
```bash
pip install flask flask-cors firebase-admin gunicorn
python app.py
```

### Open the app
- **Same computer**: open `index.html` in browser, change API URL to `http://127.0.0.1:5000`
- **Friend on same WiFi**: they open `index.html`, you tell them your IP (shown in terminal)

---

## ── OPTION B: Deploy to Railway (Recommended) ──────────────

Makes it a real website. Anyone anywhere can vote. Free tier is enough.

### 1. Push code to GitHub
```bash
# Create a .gitignore first so you don't upload your secret key!
echo "firebase-key.json" > .gitignore
echo "__pycache__/" >> .gitignore

git init
git add .
git commit -m "VoteSecure initial commit"
```
Then create a repo on https://github.com and push.

### 2. Deploy on Railway
1. Go to https://railway.app → Sign up with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `votesecure` repo → Deploy

### 3. Add Environment Variables (Railway dashboard)
Go to your project → **Variables** tab → add these one by one:

| Variable | Value |
|---|---|
| `GMAIL_USER` | your_gmail@gmail.com |
| `GMAIL_APP_PASS` | abcd efgh ijkl mnop |
| `FIREBASE_JSON` | *(see below)* |

**For `FIREBASE_JSON`:**
- Open your `firebase-key.json` file
- Copy the **entire contents** (the whole JSON)
- Paste it as the value for `FIREBASE_JSON`

Railway will restart automatically. Done!

### 4. Get your URL
Railway dashboard → your project → **Settings** → **Domains**
Your URL looks like: `https://votesecure-production.up.railway.app`

### 5. Update index.html
Open `index.html`, find this line near the bottom:
```javascript
const API = "https://YOUR-APP-NAME.up.railway.app";
```
Replace with your actual Railway URL. Save and share `index.html` with everyone.

---

## Sharing with voters

Once deployed:
- Send everyone the `index.html` file
- They open it in any browser — Chrome, Safari, Firefox, mobile — anything
- No app install, no Python, nothing to run
- All votes go to your Firebase database automatically ✓

---

## View Results / Leaderboard

Open in browser:
```
https://YOUR-APP-NAME.up.railway.app/admin/results
```
Returns JSON. In future you can build a live leaderboard page on top of this.

---

## Change Candidates

Edit the `seed_candidates()` function in `app.py`, then:
1. Go to Firebase Console → Firestore → delete the `candidates` collection
2. Redeploy (Railway auto-redeploys on every git push)

---

## Troubleshooting

| Problem | Fix |
|---|---|
| OTP not received | Check spam folder; verify App Password is correct |
| `firebase-key.json not found` | File must be in same folder as app.py |
| Railway deploy fails | Check logs in Railway dashboard → Deployments |
| `FIREBASE_JSON` parse error | Make sure you copied the entire JSON including `{` and `}` |
| Voters can't connect | Make sure `index.html` has the correct Railway URL |
