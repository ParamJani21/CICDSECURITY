# Complete Startup Guide - From Zero to Webhooks

## Quick Start (3 Steps)

### Step 1: Get ngrok Token
```bash
# Visit: https://dashboard.ngrok.com/auth/your-authtoken
# Copy your token (looks like: 2VkDXXXXXXXXXXXXXXXXX)
```

### Step 2: Save Token to .env
```bash
# Option A: Via Dashboard (Recommended)
python3 run.py
# → Open http://localhost:5000
# → Settings tab → GitHub Webhook Secret → "Ngrok OAuth Token" field
# → Paste token → Save

# Option B: Direct .env edit
echo "NGROK_OAUTH_TOKEN=your_token_here" >> .env
```

### Step 3: Start App with Tunnel
```bash
python3 run.py

# You'll see:
# ======================================================================
#  CICDSECURITY - GitHub Security Scanning Dashboard
# ======================================================================
# 🌐 Public URL: https://abc123def456.ngrok.io
# 💡 GitHub Webhook URL: https://abc123def456.ngrok.io/github/webhook
```

---

## Configure GitHub Webhook

1. Go to: GitHub → Settings → Developer settings → GitHub Apps → Your App
2. Click "Webhooks" section
3. Fill in:
   - **Payload URL:** `https://abc123def456.ngrok.io/github/webhook` (from run.py output)
   - **Content type:** `application/json`
   - **Secret:** (Use any string - also update in Settings tab)
   - **Events:** Pull requests, Pushes, Issues
4. Click "Save"

---

## Test It

```bash
# 1. In terminal with running app, watch logs:
tail -f logs/app.log | grep webhook

# 2. Create a test PR on GitHub
# 3. Watch logs show:
#    [INFO] GitHub webhook received: pull_request
#    [INFO] Pull Request opened: user/repo#1 - Title
```

---

## What run.py Does Now

### Flow
```
1. Load .env file
2. Check for NGROK_OAUTH_TOKEN
   ├─ If missing: Run locally only (http://localhost:5000)
   └─ If found: Continue to ngrok setup
3. Authenticate ngrok: ngrok config add-authtoken <token>
4. Start tunnel: ngrok http 5000
5. Get public URL from ngrok API
6. Display webhook URL in console
7. Start Flask development server
```

### Startup Output
```
======================================================================
 CICDSECURITY - GitHub Security Scanning Dashboard
======================================================================
📝 Environment: Development
🔧 Flask Debug: Enabled
🌐 Local URL: http://localhost:5000
======================================================================

🔌 ngrok Configuration:
   Token found: 2VkDXXXX...XXXXX

🔐 Authenticating ngrok with token...
✅ ngrok authentication successful

🚀 Starting ngrok tunnel on port 5000...
   Waiting for tunnel to initialize...
✅ ngrok tunnel started successfully!

======================================================================
🌐 Public URL: https://abc123def456.ngrok.io
======================================================================

💡 GitHub Webhook URL:
   https://abc123def456.ngrok.io/github/webhook

📖 Documentation:
   - Webhook Setup: See WEBHOOK_QUICK_START.md
   - Full Guide: See WEBHOOK_IMPLEMENTATION.md

======================================================================
🎯 Starting Flask application...
======================================================================

 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

---

## Cleanup

Press `Ctrl+C`:
```
^C
🛑 Received interrupt signal...
🛑 Stopping ngrok tunnel...
✅ ngrok tunnel stopped
👋 Goodbye!
```

Automatically:
- ✅ Stops ngrok tunnel
- ✅ Stops Flask server
- ✅ Cleans up resources
- ✅ Exits gracefully

---

## Environment Variables

### Required for Webhooks
```bash
# In .env:
NGROK_OAUTH_TOKEN=your_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret
```

### Optional
```bash
GITHUB_APP_ID=your_app_id
GITHUB_SECRET_KEY=your_private_key
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| ngrok not found | Install: `brew install ngrok` or https://ngrok.com/download |
| Auth failed | Verify token at https://dashboard.ngrok.com/auth/your-authtoken |
| Tunnel won't start | Check port 5000 is free: `lsof -i :5000` |
| Webhook not delivering | Verify URL matches GitHub webhook config |

---

## Next Steps

After webhooks are working, you can:

1. **Auto-trigger scans** on PR events
2. **Post results** to PR comments
3. **Block merges** if critical vulns found
4. **Create GitHub Checks** with scan results

See `WEBHOOK_IMPLEMENTATION.md` for code examples.

