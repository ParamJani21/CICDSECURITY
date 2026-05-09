# Enhanced run.py - ngrok Auto-Start Guide

## Overview
The `run.py` script has been enhanced to automatically start an ngrok tunnel using the `NGROK_OAUTH_TOKEN` from your `.env` file.

## What's New

### Features
✅ **Automatic ngrok authentication** using .env token  
✅ **Auto-start ngrok tunnel** on Flask startup  
✅ **Public URL display** in console  
✅ **Webhook URL generation** (shows where to configure GitHub)  
✅ **Graceful cleanup** when app stops (Ctrl+C)  
✅ **Error handling** with helpful messages  

### No Breaking Changes
- If `NGROK_OAUTH_TOKEN` is not set, app runs normally on `http://localhost:5000`
- Perfect for both local development (no token) and production setup (with token)

---

## How to Use

### Option 1: Local Development (No ngrok)
```bash
# Run without ngrok - local development only
python3 run.py

# Output:
# 🌐 Local URL: http://localhost:5000
# ⏭️  Skipping ngrok tunnel. Using local Flask server only.
```

### Option 2: With ngrok Tunnel (Public URL)
```bash
# Step 1: Get your ngrok token from https://dashboard.ngrok.com/auth/your-authtoken
# Step 2: Add to .env file or set via Dashboard Settings
NGROK_OAUTH_TOKEN=your_token_here

# Step 3: Run the app
python3 run.py

# Output:
# 🌐 Public URL: https://abc123def456.ngrok.io
# 💡 GitHub Webhook URL: https://abc123def456.ngrok.io/github/webhook
```

---

## Setup Steps

### 1. Get ngrok Token
```bash
# Visit: https://dashboard.ngrok.com/auth/your-authtoken
# Copy your authentication token
```

### 2. Save Token to .env
**Option A: Via Dashboard Settings**
```bash
# 1. python3 run.py (without token, runs locally)
# 2. Open http://localhost:5000
# 3. Go to Settings tab
# 4. Scroll to "GitHub App Configuration"
# 5. Find "Ngrok OAuth Token" field
# 6. Paste your token and click "Save Credentials"
# 7. Verify: cat .env | grep NGROK_OAUTH_TOKEN
```

**Option B: Manual .env Edit**
```bash
# Edit .env and add:
NGROK_OAUTH_TOKEN=your_token_here

# Example:
echo "NGROK_OAUTH_TOKEN=2VkDXXXXXXXXXXXXXXXXX" >> .env
```

### 3. Start Application
```bash
python3 run.py
```

### 4. Use Public URL
```
✅ ngrok authentication successful
🚀 Starting ngrok tunnel on port 5000...
✅ ngrok tunnel started successfully!

🌐 Public URL: https://abc123def456.ngrok.io
```

Copy the public URL and configure your GitHub App webhook!

---

## What Happens on Startup

```
1. Load NGROK_OAUTH_TOKEN from .env
   ├─ If not found: Skip ngrok, run locally only
   └─ If found: Proceed to authentication

2. Authenticate ngrok with token
   ├─ 🔐 Authenticating ngrok...
   └─ ✅ Authentication successful

3. Start ngrok tunnel
   ├─ 🚀 Starting ngrok tunnel on port 5000...
   ├─ (Wait 3 seconds for initialization)
   └─ ✅ ngrok tunnel started successfully!

4. Query ngrok API for public URL
   ├─ GET http://localhost:4040/api/tunnels
   └─ 🌐 Public URL: https://abc123def456.ngrok.io

5. Display webhook URL
   └─ 💡 GitHub Webhook URL: https://abc123def456.ngrok.io/github/webhook

6. Start Flask development server
   └─ Flask app listening on http://0.0.0.0:5000
```

---

## Console Output Examples

### With ngrok Token
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

### Without ngrok Token
```
======================================================================
 CICDSECURITY - GitHub Security Scanning Dashboard
======================================================================

⚠️  WARNING: NGROK_OAUTH_TOKEN not found in .env
   Skipping ngrok tunnel. Set NGROK_OAUTH_TOKEN to enable automatic tunneling.

⏭️  Skipping ngrok tunnel. Using local Flask server only.

======================================================================
🎯 Starting Flask application...
======================================================================

 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

---

## Stopping the Application

Press `Ctrl+C` to stop:
```
^C
🛑 Received interrupt signal...
🛑 Stopping ngrok tunnel...
✅ ngrok tunnel stopped
👋 Goodbye!
```

The script automatically:
1. Stops the ngrok tunnel
2. Stops the Flask server
3. Cleans up resources
4. Exits gracefully

---

## Troubleshooting

### Error: "ngrok command not found"
```
❌ ERROR: ngrok command not found. Install ngrok from https://ngrok.com
```
**Solution:** Install ngrok
```bash
# macOS/Linux
brew install ngrok

# Or download from: https://ngrok.com/download
```

### Error: "ngrok authentication failed"
```
❌ ngrok authentication failed: ...
```
**Solution:** Verify your token
1. Go to https://dashboard.ngrok.com/auth/your-authtoken
2. Copy the correct token
3. Update .env: `NGROK_OAUTH_TOKEN=correct_token_here`
4. Restart the app

### Tunnel not starting
```
⚠️  Could not get tunnel URL from ngrok API
```
**Solution:** 
1. Check ngrok is running: `ps aux | grep ngrok`
2. Check port 4040 is available: `lsof -i :4040`
3. Restart the app: `python3 run.py`

### Webhook not receiving events
1. Verify public URL matches in GitHub App webhook configuration
2. Check ngrok logs: `ngrok logs` in another terminal
3. Verify webhook secret matches in Settings tab
4. Test webhook delivery in GitHub App settings

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NGROK_OAUTH_TOKEN` | Optional | Token from https://dashboard.ngrok.com/auth |
| `GITHUB_APP_ID` | Optional | GitHub App ID for authentication |
| `GITHUB_SECRET_KEY` | Optional | GitHub App RSA private key |
| `GITHUB_WEBHOOK_SECRET` | Optional | Webhook signature verification secret |

---

## Security Notes

⚠️ **Never commit `.env` to version control**
- .env contains sensitive tokens
- Use `.gitignore` to exclude it
- Use environment variables for production

✅ **ngrok token is personal**
- Keep your token secret
- Regenerate if compromised
- Use different tokens for dev/prod

---

## Integration with GitHub Webhook

After app is running with ngrok:

1. **Get the webhook URL** (from console output)
   ```
   https://abc123def456.ngrok.io/github/webhook
   ```

2. **Configure GitHub App**
   - GitHub → Settings → Developer settings → GitHub Apps
   - Click your app → Webhooks
   - Payload URL: `https://abc123def456.ngrok.io/github/webhook`
   - Secret: (from Settings tab in dashboard)
   - Events: Pull requests, Pushes, Issues
   - Click Save

3. **Test webhook**
   - GitHub will send a "ping" event
   - Check application logs:
     ```bash
     tail -f logs/app.log | grep webhook
     ```
   - Should see: `[INFO] GitHub webhook received: ping`

---

## Files Modified

- `run.py` - Enhanced with ngrok auto-start functionality

## Key Functions

| Function | Purpose |
|----------|---------|
| `load_env()` | Load variables from .env |
| `get_ngrok_token()` | Extract NGROK_OAUTH_TOKEN |
| `authenticate_ngrok()` | Run `ngrok config add-authtoken` |
| `start_ngrok_tunnel()` | Start tunnel and get public URL |
| `check_ngrok_status()` | Verify tunnel is still running |
| `cleanup_ngrok()` | Stop tunnel on exit |
| `signal_handler()` | Handle Ctrl+C gracefully |

