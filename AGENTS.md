# AGENTS.md – CICDSECURITY

## Project Overview

**CICDSECURITY** is a Flask-based security scanning orchestration dashboard for GitHub repositories. It:
- Clones GitHub repos via GitHub App authentication
- Runs OpenGrep (static code analysis), TruffleHog (secret scanning), and Trivy (vulnerability/SBOM) scans
- Stores results in `logs/tool-output/{scan_id}/` as JSON
- Serves a web dashboard showing overview, repos, and scan history

**Not a library.** Flask web app with Python business logic. No tests, CI, or build process.

---

## Key Directories & Entry Points

| Path | Purpose |
|------|---------|
| `run.py` | Flask app entry point: `from app import create_app` then `app.run(debug=True)` |
| `app/__init__.py` | Flask app factory; sets up logging to `logs/app.log` (rotating: 5MB, 3 backups) |
| `app/routes.py` | Dashboard HTML route + JSON API endpoints (`/api/overview`, `/api/repos`, `/api/history`, `/api/repos/scan`) |
| `modules/control_apis.py` | Core scan workflow (1300+ lines): clone, opengrep, trufflehog, trivy, save, cleanup; uses WSL execution for all external tools |
| `modules/scan_controller.py` | Thin wrapper; imports `*` from `control_apis` |
| `modules/repos.py` | GitHub App JWT auth, installation token generation, repo list fetching |
| `modules/env_config.py` | Loads `.env` and restores escaped newlines in RSA private key |
| `logs/` | App logs (`app.log`, rotating backups), scan output dir (`tool-output/{scan_id}/`) |

---

## How to Run

### Start the Flask app (development mode)
```bash
cd /mnt/e/onlydash_CICDSECURITY/CICDSECURITY
python3 run.py
# Listens on http://localhost:5000 by default
# Note: use_reloader=False in run.py to prevent inotify file-system spam on WSL
```
**USER ONLY WILL RUN THE PYTHON APP.PY COMMAND**

**Logs:**
- Console output + file: `logs/app.log`
- Scan results: `logs/tool-output/{scan_id}/` (opengrep.json, truffle.json, trivy.json)

### Trigger a manual scan via API
```bash
curl -X POST http://localhost:5000/api/repos/scan \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "123",
    "repo_name": "my-repo",
    "repo_owner": "my-org",
    "repo_url": "https://github.com/my-org/my-repo.git",
    "repo_branch": "main"
  }'
```

Endpoint: `app/routes.py:58` → calls `trigger_scan()` from `modules/control_apis.py:971`

---

## Critical Workflow: Scan Execution

**Entry:** `trigger_scan(repo_id, repo_name, repo_owner, repo_url, repo_branch)` in `modules/control_apis.py:1102`

**6-step flow** (logged with ASCII art separators):
1. **CLONE** (`clone_repository` line 214) → WSL `git clone` into `/tmp/{owner}/{name}/`, auth via GitHub App token
2. **OPENGREP SCAN** (`run_opengrep_scan` line 609) → Static code analysis, results to `opengrep.json`
3. **TRUFFLEHOG SCAN** (`run_truffle_scan` line 743) → Secret scanning (API keys, tokens, passwords), results to `truffle.json`
4. **TRIVY SCAN** (`run_trivy_scan` line 870) → Vuln/SBOM scan (`--scanners vuln,misconfig,license`), results to `trivy.json`
5. **SAVE RESULTS** → Combine all three outputs, store metadata in `logs/tool-output/{scan_id}/`
6. **CLEANUP** (`cleanup_cloned_repo` line 505) → Remove cloned repo from `/tmp/`

**TRIVY ONLY SUPPOSE TO DO SBOM SCAN, NO VULNERABILITY SCANNING**
**Key quirks:**
- OpenGrep/clone failure stops workflow
- TruffleHog/Trivy failure doesn't stop workflow (returns skipped if tool unavailable)
- All three results saved to separate JSON files for easy parsing

---

## GitHub App Authentication

Configured via `.env` (RSA private key + app ID):

```python
# modules/repos.py:17
def get_github_app_token():
    # Generates JWT using RSA private key
    # exp: 5 minutes (GitHub requirement, line 59)
    # Returns JWT token for API calls
```

**env_config.py** auto-converts escaped `\n` in `.env` to actual newlines for RSA key parsing.

---

## WSL Execution

**Why WSL?** Windows system; Trivy/Git run via WSL subsystem.

```python
# modules/control_apis.py:70
def run_wsl_command(command, cwd=None, timeout=300):
    # Subprocess wrapper for WSL commands
    # Default timeout: 300s (git clone), 600s+ for scans
```

**Path conversion:** `C:\Users\foo\project` → `/mnt/c/Users/foo/project` (line 39)

---

## TruffleHog Configuration (Secret Scanning)

TruffleHog scans for sensitive data: API keys, tokens, passwords, credentials, etc.

**Command** (line 791 in control_apis.py):
```bash
trufflehog filesystem . \
  --json \
  --no-update \
  --exclude .git,node_modules,venv,.venv,__pycache__,.env,*.pyc
```

**Behavior:**
- If TruffleHog not installed in WSL → scan marked `skipped`, workflow continues
- TruffleHog failure doesn't stop workflow (unlike OpenGrep)
- Results saved to `logs/tool-output/{scan_id}/truffle.json`

**To install TruffleHog in WSL:**
```bash
# Option 1: From source
go install github.com/trufflesecurity/trufflehog/v3@latest

# Option 2: Binary release
wsl curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/install.sh | sh -s -- -b /usr/local/bin

# Option 3: Homebrew (on macOS/WSL)
wsl brew install trufflesecurity/tap/trufflehog
```

---

## Trivy Configuration (SBOM Only)

**SBOM only - no vulnerability scanning** (line 882 in control_apis.py):
```bash
trivy sbom \
  --format cyclonedx \
  . 2>&1 || true
```

Trivy now generates SBOM (Software Bill of Materials) in CycloneDX format. Results stored in `sbom_components` array with component count in `findings_count`. No vulnerability scanning.

---

## Environment & Dependencies

- **Python:** 3.13.11
- **Framework:** Flask 2.3.3
- **Auth:** PyJWT 2.8.1 (GitHub App), cryptography 41.0.7
- **HTTP:** requests 2.31.0
- **External tools:** Git, Trivy, OpenGrep, TruffleHog (called via WSL)
- **.env:** GitHub app credentials (app ID: 3056984, app name: SECURITY, RSA private key)

---

## Logging Architecture

**Dual output** (app/__init__.py:7):
- File: `logs/app.log` (RotatingFileHandler: 5MB, 3 backups, UTF-8)
- Console: stderr
- Level: DEBUG for all modules
- Format: `[timestamp] LEVEL in module: message`

**Scan logs** include ASCII art boxes showing progress (STEP 1/6, STEP 2/6, ..., STEP 6/6).

---

## Common Pitfalls for Agents

1. **WSL paths:** Windows paths not converted → Git/Trivy/TruffleHog fail. Check `get_wsl_path()` if cloning fails.
2. **GitHub App token expiration:** JWT hardcoded to 5 min; if API calls timeout, token likely expired. See `get_github_app_token()`.
3. **RSA key format:** `.env` stores key with escaped `\n`. env_config.py must restore them; verify in logs if auth fails.
4. **TruffleHog not installed:** If TruffleHog missing in WSL, scan marked `skipped` but continues. Install via go or brew in WSL.
5. **Trivy SBOM only:** Trivy now generates SBOM (CycloneDX) instead of vulnerability scans. No vuln/misconfig/license scanning - SBOM components only.
6. **Cleanup doesn't re-run:** If a scan fails mid-execution, `/tmp/{owner}/{name}` may persist. Manual cleanup may be needed.
7. **No tests:** No pytest/unittest suite. Verify changes by triggering a scan via API and checking logs + `logs/tool-output/` output.

---

## File Structure for Quick Navigation

```
CICDSECURITY/
├── run.py                       # Flask entry point
├── requirements.txt             # Python deps (Flask, PyJWT, cryptography, requests)
├── .env                         # GitHub app ID + RSA private key
├── mcp.json                     # MCP server config (Puppeteer browser)
├── TRIVY_SBOM_CONFIG.md         # Trivy scanner details (vuln, misconfig, license)
│
├── app/
│   ├── __init__.py              # Flask factory + logging setup
│   └── routes.py                # Dashboard + API endpoints
│
├── modules/
│   ├── control_apis.py          # Core scan workflow (clone→opengrep→trufflehog→trivy→save→cleanup)
│   ├── repos.py                 # GitHub App auth, repo fetching
│   ├── env_config.py            # .env loader, key decoding
│   ├── scan_controller.py       # Wrapper (imports from control_apis)
│   ├── overview.py              # Dashboard overview data
│   ├── history.py               # Scan history data
│   ├── settings.py              # Settings UI data
│   └── scan_api.py              # Scan API blueprint
│
├── logs/
│   ├── app.log                  # Main Flask logs (rotating)
│   └── tool-output/
│       └── {scan_id}/           # Per-scan results
│           ├── opengrep.json    # OpenGrep (static code analysis)
│           ├── truffle.json     # TruffleHog (secret scanning)
│           └── trivy.json       # Trivy (vulnerability/SBOM)
│
└── tmp/                         # Cloned repos (auto-cleanup after scan)
```

---

## Debugging Tips

- **Check scan status:** Monitor `logs/app.log` in real-time: `tail -f logs/app.log`
- **Inspect failed scan:** Check `logs/tool-output/{scan_id}/` for output from each tool
- **WSL issues:** Run `wsl git --version`, `wsl opengrep --version`, `wsl trufflehog --version` to verify tool availability
- **Auth failures:** Enable debug logging, re-run, search logs for `[Auth]` markers
- **TruffleHog missing:** If TruffleHog scan skipped, install in WSL: `go install github.com/trufflesecurity/trufflehog/v3@latest`
- **Memory/performance:** Monitor Python process; Trivy/TruffleHog scans can be slow on large repos
