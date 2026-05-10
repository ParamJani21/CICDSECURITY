# CICDSECURITY - Security Scanning Orchestration Dashboard

A Flask-based security scanning dashboard that automates security scans for GitHub repositories using multiple security tools.

## Features

- **GitHub App Integration** - Authenticate and scan repositories via GitHub App
- **Automated PR Scanning** - Automatically scans pull requests when opened/updated
- **PR Toggle** - Enable/disable automatic PR scanning from Settings
- **GitHub Status Checks** - Real-time commit status on PRs
- **PR Comments** - Posts scan results summary as PR comment
- **Selectable Scan Types** - Choose which scans to run (SATS, SBOM, SECRET)
- **Scan History** - View and manage past scan results
- **Export Reports** - Generate HTML reports of scan findings

## Prerequisites

- Python 3.10+
- GitHub App (create at github.com/settings/apps)
- ngrok (for webhook access)
- WSL (Windows Subsystem for Linux) for Windows users

## Installation

### 1. Clone/Download the Project

```bash
cd /path/to/CICDSECURITY
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Security Tools (WSL/Linux)

```bash
# OpenGrep (static analysis)
curl -fsSL https://raw.githubusercontent.com/opengrep/opengrep/main/install.sh | bash

# Slither (smart contract analysis - optional)
pip install slither-analyzer

# Trivy (SBOM generation)
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin v0.70.0

# TruffleHog (secret scanning)
git clone https://github.com/trufflesecurity/trufflehog.git
cd trufflehog && go install
```

Verify tools:
```bash
git --version
opengrep --version
slither --version
trufflehog --version
trivy --version
```

## Setup Flow

### 1. Create GitHub App

1. Go to: https://github.com/settings/apps/new
2. Set name (e.g., "CICDSECURITY")
3. Enter the random URL at the HomepageURL and webhookURL(TEMP)
4. Permissions:
   - Contents: Read
   - Pull requests: Read & Write
   - Commit statuses: Read & Write
   - Checks: Read & Write
5. Subscribe to events: `Pull requests`
6. Create Gihub app.
7. Find private key generation...and generate private key (download .pem file)

### 2. Run the Application

```bash
python3 run.py
```

Access at: `http://localhost:5000`

### 3. Configure via Dashboard

1. **Login** with your admin credentials (created during first setup):
   - If no admin exists, you'll be prompted to create one on the login page

2. **Configure GitHub App Settings** (in Settings Tab):
   - **GitHub App ID** - From your GitHub App settings
   - **GitHub App Name** - The name you gave your app
   - **GitHub Secret Key** - Paste the entire private key (.pem file contents)
   - **Ngrok OAuth Token** - From ngrok.com dashboard
   - **Ngrok Subdomain** - Optional custom subdomain for ngrok
   - **Webhook Secret** - Generate a random string for verification

3. **Configure GitHub Webhook**:
   - Go to your GitHub App settings > Webhooks
   - Add webhook URL (shown in terminal when app starts): `https://your-subdomain.ngrok.io/github/webhook`
   - Set webhook secret matching your dashboard

4. **Install GitHub App** on your organization/repositories

**Note:** Ngrok tunnel is automatically started when `Ngrok OAuth Token` is configured. The webhook URL will be displayed in the terminal.

### 4. Toggle PR Scanning

In Settings tab:
- Enable toggle = All PRs auto-scan
- Disable toggle = PRs logged but not scanned

## Default Credentials

On first run, you'll be prompted to create an admin account with your chosen username and password. No default password - you create it yourself!

**Important: Change password after first login!**

## Scan Types

| Type | Tool | Description |
|------|------|-------------|
| **SATS** | OpenGrep | Static code analysis |
| **SBOM** | Trivy | Software Bill of Materials |
| **SECRET** | TruffleHog | Secret/token detection |

## API Endpoints

```bash
# Manual scan
curl -X POST http://localhost:5000/api/repos/scan \
  -H "Content-Type: application/json" \
  -d '{"repo_id":"123","repo_name":"repo","repo_owner":"org","repo_url":"...","repo_branch":"main","scan_types":["sats","sbom","secret"]}'

# Toggle PR scan
curl -X POST http://localhost:5000/api/settings/pr-scan \
  -H "Content-Type: application/json" \
  -d '{"pr_scan_enabled": false}'
```

## Troubleshooting

### Check logs
```bash
tail -f logs/app.log
```

### Verify tools installed
```bash
which opengrep trufflehog trivy git
```

### Test webhook
```bash
# Generate signature
SECRET="your_webhook_secret"
PAYLOAD='{"action":"opened","pull_request":{"number":1}}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)

curl -X POST http://localhost:5000/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  -H "X-GitHub-Event: pull_request" \
  -d "$PAYLOAD"
```

## Project Structure

```
CICDSECURITY/
├── run.py                 # App entry point
├── requirements.txt      # Dependencies
├── .env                  # Auto-created config
├── app/                  # Flask app
│   ├── __init__.py
│   ├── routes.py
│   └── templates/
├── modules/              # Core logic
│   ├── control_apis.py
│   ├── pr_scan_handler.py
│   ├── github_status.py
│   └── pr_comment.py
├── models/               # Database
│   └── database.py
├── static/               # Frontend
│   ├── dashboard.js
│   └── styles.css
└── logs/                 # Output
    ├── app.log
    └── tool-output/
```

## Need Help?

1. Check `logs/app.log` for errors
2. Verify all tools are in PATH
3. Ensure ngrok tunnel is active
4. Verify GitHub App permissions and webhook