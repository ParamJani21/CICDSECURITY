# GitHub Webhook Implementation - Complete Guide

## Overview
The GitHub webhook listener has been fully implemented to receive and process GitHub App events with signature verification.

## What Was Implemented

### 1. **Webhook Secret Storage** ✅
- Added `github_webhook_secret` field to Settings tab in Dashboard
- Stored securely in `.env` as `GITHUB_WEBHOOK_SECRET`
- Can be updated anytime from Settings → GitHub App Configuration

### 2. **Webhook Listener Endpoint** ✅
- **Endpoint:** `POST /github/webhook`
- **Authentication:** Public (no login required)
- **Features:**
  - HMAC-SHA256 signature verification
  - Payload parsing
  - Event-based handling
  - Comprehensive logging

### 3. **Supported GitHub Events** ✅
- **pull_request**: Handles PR opened, synchronized, closed events
- **push**: Handles push events to branches
- **issues**: Handles issue created, edited, closed events
- **ping**: GitHub webhook configuration test

### 4. **Security Features** ✅
- HMAC-SHA256 signature verification (X-Hub-Signature-256 header)
- Constant-time comparison to prevent timing attacks
- Webhook secret validation
- Comprehensive error logging

---

## How to Setup

### Step 1: Start the Application
```bash
cd /mnt/e/onlydash_CICDSECURITY/CICDSECURITY
python3 run.py
```

### Step 2: Configure Webhook Secret
1. Open Dashboard → **Settings tab**
2. In "GitHub App Configuration" section, find "GitHub Webhook Secret" field
3. Enter your webhook secret (can be any random string, but GitHub will validate it)
4. Click "Save Credentials"
5. Verify in `.env` file: `GITHUB_WEBHOOK_SECRET=your_secret_here`

### Step 3: Configure GitHub App
1. Go to GitHub → Settings → Developer settings → GitHub Apps → Your App
2. Click "Webhooks" section
3. Configure webhook:
   - **Payload URL:** `https://your-ngrok-url.ngrok.io/github/webhook`
   - **Content type:** `application/json`
   - **Secret:** Use the same secret from Step 2
   - **SSL verification:** Enable (recommended)
4. Select events to subscribe to:
   - Pull requests
   - Pushes
   - Issues
   - Any others you need
5. Click "Save"

### Step 4: Test the Webhook
- GitHub will send a **ping** event automatically
- Check application logs: `tail -f logs/app.log`
- Should see: `GitHub webhook received: ping`

---

## Environment Variables

Add to `.env`:
```
GITHUB_APP_ID=your_app_id
GITHUB_APP_NAME=your_app_name
GITHUB_SECRET_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
NGROK_OAUTH_TOKEN=your_ngrok_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret
```

---

## Webhook Endpoint Response Codes

| Code | Meaning | Cause |
|------|---------|-------|
| 200  | Success | Event processed |
| 400  | Bad Request | No JSON payload or missing secret config |
| 403  | Forbidden | Signature verification failed |
| 500  | Server Error | Unexpected error during processing |

---

## Logging

Webhook events are logged to `logs/app.log`:

```
[INFO] GitHub webhook received: pull_request
[INFO] Pull Request opened: org/repo#42 - Add new feature
[DEBUG] Webhook payload: {...}
```

Signature verification failures:
```
[WARNING] GitHub webhook signature verification failed
[WARNING] GitHub webhook received without signature header
[WARNING] GitHub webhook received but GITHUB_WEBHOOK_SECRET not configured
```

---

## Testing with curl

You can test the webhook endpoint with curl (but signature verification will fail):

```bash
curl -X POST http://localhost:5000/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen":"Design for failure."}'
```

Result: `{"status": "error", "message": "No signature provided"}` (expected)

To test with valid signature, use:

```bash
SECRET="your_webhook_secret"
PAYLOAD='{"zen":"Design for failure."}'
SIGNATURE="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)"

curl -X POST http://localhost:5000/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -H "X-GitHub-Event: ping" \
  -d "$PAYLOAD"
```

Result: `{"status": "success", "message": "Webhook configured successfully"}`

---

## Event Handlers

### Pull Request Events
- **opened**: Triggered when a new PR is created
- **synchronize**: Triggered when new commits are pushed
- **closed**: Triggered when PR is merged or closed

Logs: `Pull Request opened: org/repo#42 - Title`

### Push Events
- Triggered when commits are pushed to a branch

Logs: `Push to org/repo:main`

### Issues Events
- **opened**: New issue created
- **closed**: Issue closed

Logs: `Issue opened: org/repo#42 - Title`

---

## Future Enhancements

You can extend the webhook handlers to:
1. **Auto-trigger scans** on PR creation
2. **Block merge** if critical vulnerabilities found
3. **Post results** as PR comments
4. **Create GitHub Check Runs** for scan results
5. **Trigger CI/CD pipelines** on push events

---

## Troubleshooting

### Webhook not delivering events
1. Check GitHub App webhook logs: Settings → GitHub Apps → Your App → Webhooks → Recent Deliveries
2. Verify ngrok tunnel is running: `curl http://localhost:5000/github/webhook` should return error
3. Verify webhook secret matches in both GitHub and `.env`

### Signature verification failing
1. Ensure `GITHUB_WEBHOOK_SECRET` is set in `.env`
2. Check GitHub webhook secret matches `.env` exactly
3. Verify payload is JSON (Content-Type: application/json)

### Events not being logged
1. Check `logs/app.log` for errors
2. Verify events are selected in GitHub App webhook settings
3. Check if webhook secret is configured

---

## Files Modified

- `app/routes.py` - Added `/github/webhook` endpoint and event handlers
- `app/__init__.py` - Added `/github/` to authentication skip list
- `templates/dashboard.html` - Added webhook secret field to Settings
- `static/dashboard.js` - Updated to load/save webhook secret
- `modules/settings.py` - Updated to handle webhook secret parameter
- `modules/env_config.py` - Updated to save/read webhook secret from `.env`

