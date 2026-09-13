# Groq setup (optional — report prose only)

Hard rule, repeat it to judges: **no LLM in the decision path.** Detection is
geometry; adjudication is deterministic sporting law. Groq only converts
already-decided incident facts into readable report sentences. If the key is
missing or the API fails, `pipeline/explain/groq_explain.py` falls back to a
deterministic template — nothing in the product depends on this.

## 1 · Create the free account
1. Open https://console.groq.com in a browser.
2. Click **Sign up** (top right). Use Google sign-in or email + password.
3. Verify your email if prompted. No card is required for the free tier.

## 2 · Generate the API key
1. Once logged in, you land in the **GroqCloud console**.
2. In the left sidebar, click **API Keys**.
3. Click **Create API Key**.
4. Name it `apexline-hackathon` (names help you revoke cleanly later).
5. Click **Submit / Create**. The key (starts with `gsk_...`) is shown **once**.
6. Click the copy icon immediately. If you lose it, delete it and make a new one.

## 3 · Store the key safely
From the repo root:

```bash
cp .env.example .env        # .env is already in .gitignore
```

Open `.env` and paste:

```
GROQ_API_KEY=gsk_your_key_here
```

Check it can never be committed:

```bash
# (only if you've run `git init` — before that git errors out, which is fine)
git check-ignore -v .env    # must print a match once this is a git repo
```

Never paste the key into code, notebooks, or the deck. If it ever leaks
(screenshot, commit, screen share), revoke it in the console (API Keys → trash
icon) and issue a new one — takes 30 seconds.

## 4 · Load it and test

```bash
pip install groq python-dotenv --break-system-packages   # groq is already in requirements.txt
python3 - << 'PY'
from dotenv import load_dotenv; load_dotenv(".env")  # explicit path — bare load_dotenv() crashes when run via a heredoc
import os
assert os.environ.get("GROQ_API_KEY", "").startswith("gsk_"), "key not loaded"
from pipeline.explain.groq_explain import explain_incident
print(explain_incident({"car": "27", "type_code": "V2", "corner": "T4-exit",
                        "duration_ms": 480, "max_overshoot_m": 0.31,
                        "error_band_m": 0.06, "confidence": 0.94,
                        "band": "auto_flag", "status": "approved"}))
PY
```

You should get one neutral steward-report sentence.

NOTE: the server loads `.env` by itself at startup (see `_load_dotenv` in
server/main.py) — for the product you only need the file to exist. No shell
exports, no python-dotenv required. The snippet above is only a key check. Unset the key and run it
again — you get the template version, proving the graceful degradation you'll
mention on stage.

Free-tier limits (generous for this use: a few hundred requests/day on
`llama-3.3-70b-versatile`) are shown in the console under **Limits** — check
there rather than assuming, since tiers change.
