# Webhook Quick Start - Testing Guide

## Prerequisites
✅ Application running: `python3 run.py`
✅ ngrok configured with tunnel active
✅ GitHub App created with webhook capability

## 5-Minute Setup

### 1. Add Webhook Secret (1 minute)
```bash
# Login to Dashboard
# Go to Settings Tab
# Fill in: GitHub Webhook Secret = "my-super-secret-webhook"
# Click Save Credentials
# Verify: cat .env | grep GITHUB_WEBHOOK_SECRET
```

### 2. Configure GitHub Webhook (2 minutes)
```bash
# GitHub → Settings → Developer settings → Your App → Webhooks
# Payload URL: https://your-ngrok-url.ngrok.io/github/webhook
# Secret: my-super-secret-webhook
# Events: Pull requests, Pushes, Issues
# Click Save
# GitHub will send a "ping" event automatically
```

### 3. Verify in Logs (1 minute)
```bash
# Terminal where app is running:
tail -f logs/app.log | grep webhook

# Expected output:
# [INFO] GitHub webhook received: ping
# [INFO] Webhook configured successfully
```

### 4. Test with Real Event (1 minute)
```bash
# Create a test PR in your GitHub repo
# Watch logs:
tail -f logs/app.log | grep "Pull Request"

# Expected output:
# [INFO] Pull Request opened: user/repo#1 - Test PR
```

---

## Webhook Verification

### Check if webhook is working:
```bash
# Look at GitHub webhook logs
# GitHub App → Webhooks → Recent Deliveries
# Click on each delivery to see:
# - Request headers (includes signature)
# - Request body (payload)
# - Response code
# - Response body
```

### Test signature verification locally:
```bash
#!/bin/bash
SECRET="my-super-secret-webhook"
PAYLOAD='{"zen":"Design for failure."}'

# Compute signature
SIGNATURE="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)"

echo "Testing with signature: $SIGNATURE"

# Send request
curl -X POST http://localhost:5000/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -H "X-GitHub-Event: ping" \
  -d "$PAYLOAD" -v

# Expected response:
# {"status":"success","message":"Webhook configured successfully"}
```

---

## What You'll See

### In Application Logs
```
[2025-05-09 14:23:45,123] [INFO] GitHub webhook received: pull_request
[2025-05-09 14:23:45,124] [DEBUG] Webhook payload: {...}
[2025-05-09 14:23:45,125] [INFO] Pull Request opened: user/repo#42 - Add new feature
```

### In GitHub Webhook Logs
Each delivery shows:
- ✅ Status: 200
- 📤 Request: POST /github/webhook with JSON payload
- 📥 Response: {"status":"success","message":"..."}

---

## Troubleshooting

### Webhook not working?
1. Check ngrok tunnel: `curl https://your-ngrok-url.ngrok.io/github/webhook -v`
2. Verify secret in `.env`: `grep GITHUB_WEBHOOK_SECRET .env`
3. Check GitHub App webhook logs for errors
4. Look at application logs: `tail -f logs/app.log`

### Getting 403 (Signature verification failed)?
1. Verify webhook secret matches exactly in GitHub App and `.env`
2. Check no trailing/leading spaces: `echo "$GITHUB_WEBHOOK_SECRET" | od -c`
3. Make sure `Content-Type: application/json` in GitHub webhook config

### Not seeing ping event?
1. Go to GitHub App → Webhooks → Click "Send ping"
2. Watch logs for: `GitHub webhook received: ping`
3. If no log, webhook URL might be incorrect

---

## Next Steps

After webhook is working, you can:
1. **Auto-trigger scans** on PR events
2. **Post scan results** to PR comments
3. **Block merges** if critical vulns found
4. **Create GitHub Checks** with scan results

See `WEBHOOK_IMPLEMENTATION.md` for implementation examples.

