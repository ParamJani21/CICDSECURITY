# CICDSECURITY - Quick Analysis Summary

## What is CICDSECURITY?

A **Flask web dashboard** that automates security scanning of GitHub repositories using multiple tools:
- **OpenGrep** (SATS - Code Analysis)
- **TruffleHog** (Secret Scanning)
- **Trivy** (SBOM - Dependency Inventory)

## Architecture at a Glance

```
User Dashboard (Web Browser)
    ↓
Flask Routes (app/routes.py - 1,384 lines)
    ↓
Core Scan Orchestration (modules/control_apis.py - 1,504 lines)
    ├── Clone Repository (GitHub App + Git)
    ├── Run Scans (OpenGrep, TruffleHog, Trivy)
    ├── Merge Findings (Deduplicate, Normalize)
    └── Save Results (JSON to logs/tool-output/{scan_id}/)
    ↓
SQLite Database (cicdsecurity.db)
    ├── Users (bcrypt passwords, encrypted GitHub credentials)
    ├── Sessions (8-hour expiration)
    ├── Audit Logs (action tracking)
    ├── User Preferences (UI settings)
    └── Scan History (metadata)
```

## Key Technologies

| Layer | Technology |
|-------|-----------|
| **Web Framework** | Flask 2.3.3 (Python) |
| **Database** | SQLite 3 + SQLAlchemy ORM |
| **Authentication** | JWT (GitHub App), bcrypt (passwords) |
| **Security Tools** | OpenGrep, TruffleHog, Trivy (WSL/Linux) |
| **Frontend** | Jinja2 + Bootstrap 5 + Vanilla JavaScript |
| **Networking** | GitHub API v3, ngrok (optional) |

## The 6-Step Scan Workflow

```
1. CLONE
   └─ GitHub App OAuth → Git clone with auth token → Verify

2-4. SCAN (selective)
   ├─ OpenGrep → JSON findings (code issues)
   ├─ TruffleHog → JSON lines (secrets)
   └─ Trivy → CycloneDX (dependencies)

5. MERGE
   ├─ Normalize severity (CRITICAL/MEDIUM/LOW)
   ├─ Deduplicate by (file, line, type)
   ├─ Exclude .git/ artifacts
   └─ Track sources (which tools found each issue)

6. SAVE
   ├─ logs/tool-output/{scan_id}/merged.json
   ├─ logs/tool-output/{scan_id}/opengrep.json
   ├─ logs/tool-output/{scan_id}/truffle.json
   └─ logs/tool-output/{scan_id}/trivy.json

7. CLEANUP
   └─ Remove /tmp/{owner}/{repo}/
```

## Three Scan Types Explained

### SATS (Scan Type: `sats`)
- **Tool:** OpenGrep/Semgrep
- **Purpose:** Find code security issues (SQL injection, XSS, hardcoded secrets, etc.)
- **Output:** JSON with findings array
- **Risk Levels:** CRITICAL, MEDIUM, LOW

### SBOM (Scan Type: `sbom`)
- **Tool:** Trivy
- **Purpose:** Generate Software Bill of Materials (what dependencies are used)
- **Output:** CycloneDX format (components + dependencies)
- **Use:** Supply chain security, license tracking, vulnerability correlation

### SECRET (Scan Type: `secret`)
- **Tool:** TruffleHog
- **Purpose:** Detect exposed credentials (AWS keys, GitHub tokens, private keys, DB passwords)
- **Output:** JSON lines with detector results
- **Risk Levels:** CRITICAL (private keys), HIGH (API keys), MEDIUM (others)

## GitHub App Authentication

```
1. Load App ID + RSA Private Key (from encrypted DB or .env)
2. Create JWT payload with 5-minute expiration
3. Sign with RS256 (RSA private key)
4. Call GitHub API: GET /app/installations
5. Get installation access token: POST /installations/{id}/access_tokens
6. Clone repo: git clone https://x-access-token:{token}@github.com/...
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts with encrypted GitHub credentials |
| `sessions` | Active user sessions (8-hour lifetime) |
| `audit_logs` | Action audit trail |
| `user_preferences` | UI themes, scan settings |
| `scan_history` | Scan metadata and results |

**Security:** Passwords hashed with bcrypt (12 rounds), account lockout after 5 failed attempts (15 min)

## File Structure Overview

```
CICDSECURITY/
├── run.py                      # Flask app entry point
├── requirements.txt            # Dependencies (Flask, SQLAlchemy, PyJWT, etc.)
├── .env                        # GitHub App credentials (create manually)
├── cicdsecurity.db             # SQLite database (auto-created)
│
├── app/
│   ├── __init__.py            # Flask app factory
│   ├── routes.py              # Dashboard + API endpoints (1,384 lines)
│   └── auth_routes.py         # Login/user management
│
├── modules/
│   ├── control_apis.py        # Core scan orchestration (1,504 lines)
│   ├── repos.py               # GitHub API integration (436 lines)
│   ├── history.py             # Scan result retrieval
│   ├── overview.py            # Dashboard statistics
│   ├── settings.py            # Configuration management
│   ├── scan_api.py            # Scan API endpoints
│   └── env_config.py          # .env file management
│
├── models/database.py         # SQLAlchemy models (309 lines)
├── auth/                      # Authentication decorators & utilities
├── utils/                     # Crypto & utility functions
├── validators/                # Input validation
│
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS, JavaScript
├── logs/
│   ├── app.log               # Application logs
│   └── tool-output/          # Scan results
│       └── {scan_id}/
│           ├── merged.json
│           ├── opengrep.json
│           ├── truffle.json
│           └── trivy.json
│
└── tmp/                       # Cloned repos (auto-cleanup)
```

## Key Characteristics

### Strengths
- ✅ **Fully Automated** - Clone, scan, merge, save in one workflow
- ✅ **Selectable Scans** - Choose which scans to run (SATS, SBOM, SECRET)
- ✅ **Multi-Tool** - Results merged intelligently from 3 different tools
- ✅ **Secure** - GitHub App OAuth, encrypted credentials, bcrypt passwords
- ✅ **Deduplication** - Same issue found by 2 tools = 1 entry with sources tracked
- ✅ **Historical Tracking** - All scans stored with metadata for trending
- ✅ **Web Dashboard** - Easy visualization and filtering of results

### Important Quirks
- ⚠️ **WSL Support** - Automatically runs tools via WSL on Windows or directly on Linux
- ⚠️ **Tool Failures** - OpenGrep failure stops workflow; TruffleHog/Trivy failures don't
- ⚠️ **.git/ Filtering** - Findings from .git/ directory are excluded (auth token artifacts)
- ⚠️ **JWT Expiration** - Tokens expire after 5 minutes (GitHub requirement)
- ⚠️ **Shallow Clone** - Uses `--depth 1 --single-branch` for performance

## API Endpoints (Key Examples)

```
POST /api/repos/scan
  Trigger scan for single repo
  
GET /api/history
  Get all scan history with stats
  
GET /api/history/{scan_id}
  Get detailed results for specific scan
  
GET /api/history/filter
  Filter findings by severity, tool, category
  
POST /api/scan/cleanup
  Manually cleanup cloned repo
```

## Setup Checklist

- [ ] Python 3.8+
- [ ] Create .env with GitHub App ID & private key
- [ ] pip install -r requirements.txt
- [ ] Install OpenGrep (apt-get install opengrep or pip install semgrep)
- [ ] Install TruffleHog (go install github.com/trufflesecurity/trufflehog/v3@latest)
- [ ] Install Trivy (wget + tar to /usr/local/bin/)
- [ ] python3 run.py
- [ ] Create admin user at http://localhost:5000/login
- [ ] Dashboard ready at http://localhost:5000

## Code Statistics

| Component | Lines | Purpose |
|-----------|-------|---------|
| control_apis.py | 1,504 | Core scan orchestration |
| app/routes.py | 1,384 | Web routes & APIs |
| modules/repos.py | 436 | GitHub integration |
| models/database.py | 309 | Database models |
| **Total** | **3,633** | Core application |

## What It Solves

1. **Manual Security Scanning** → Automated multi-tool orchestration
2. **Tool Fragmentation** → Unified dashboard with merged findings
3. **Private Repo Access** → GitHub App OAuth handles authentication
4. **Result Tracking** → Historical database with filtering
5. **Duplicate Findings** → Intelligent deduplication with source tracking

## Perfect For

- **CI/CD Integration** - Automated security scanning on every PR/commit
- **Repository Audits** - Scan multiple repos and compare results
- **Supply Chain Security** - SBOM generation for all dependencies
- **Secret Detection** - Proactive scanning for exposed credentials
- **Security Dashboards** - Web UI for team visibility

---

For detailed analysis, see **ANALYSIS_REPORT.txt** (912 lines)
