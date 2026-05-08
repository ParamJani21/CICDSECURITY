# AGENTS.md – CICDSECURITY

## Project Overview

**CICDSECURITY** is a Flask-based security scanning orchestration dashboard for GitHub repositories. It clones repos via GitHub App, runs selectable security scans (SATS, SBOM, SECRET), and serves results via a web dashboard.

**Not a library.** Flask web app with Python business logic. No tests, CI, or build process.

---

## Key Directories & Entry Points

| Path | Purpose |
|------|---------|
| `run.py` | Flask app entry point |
| `app/routes.py` | Dashboard + API endpoints (`/api/repos/scan`, `/api/repos/scan-all`) |
| `modules/control_apis.py` | Core scan workflow: clone → scan (SATS/SBOM/SECRET) → save → cleanup |
| `modules/repos.py` | GitHub App JWT auth, repo fetching |
| `modules/history.py` | Scan history data, get_scan_details |
| `logs/tool-output/{scan_id}/` | Per-scan JSON results (merged.json, opengrep.json, truffle.json, trivy.json) |

---

## How to Run

```bash
cd /mnt/e/onlydash_CICDSECURITY/CICDSECURITY
python3 run.py
# Dashboard at http://localhost:5000
```

**API - Single scan with scan_types:**
```bash
curl -X POST http://localhost:5000/api/repos/scan \
  -H "Content-Type: application/json" \
  -d '{"repo_id":"123","repo_name":"my-repo","repo_owner":"my-org","repo_url":"...","repo_branch":"main","scan_types":["sats","sbom","secret"]}'
```

**API - Scan all repos:**
```bash
curl -X POST http://localhost:5000/api/repos/scan-all \
  -H "Content-Type: application/json" \
  -d '{"scan_types":["sats","sbom","secret"]}'
```

---

## Selectable Scan Types

`trigger_scan()` accepts optional `scan_types` parameter (default: `['sats', 'sbom', 'secret']`):

| Scan Type | Tool | Description |
|-----------|------|-------------|
| `sats` | OpenGrep + Slither | Static code analysis |
| `sbom` | Trivy | Software Bill of Materials (CycloneDX) |
| `secret` | TruffleHog | Secret scanning |

Frontend shows modal with checkboxes to select which scans to run.

---

## Critical Workflow

1. **CLONE** → Git clone via GitHub App token to `/tmp/{owner}/{name}/`
2. **SCANS** → Run selected tools based on `scan_types` parameter
3. **MERGE** → Combine findings in `merge_findings()`
4. **SAVE** → Store to `logs/tool-output/{scan_id}/`
5. **CLEANUP** → Remove cloned repo from `/tmp/`

**Key quirks:**
- OpenGrep/SATS failure stops workflow
- TruffleHog/Trivy failure doesn't stop workflow (returns skipped)
- Scan types stored in merged.json under `scan_types`

---

## GitHub App Authentication

Configured via `.env`:
- `GITHUB_APP_ID` - App ID (e.g., 3056984)
- `GITHUB_PRIVATE_KEY` - RSA private key (escaped `\n` in .env)

`modules/repos.py` handles JWT generation and token refresh.

---

## WSL Execution

All external tools (Git, Trivy, OpenGrep, TruffleHog) run via WSL:

```python
def run_wsl_command(command, cwd=None, timeout=300):
    # Windows paths converted: C:\foo → /mnt/c/foo
```

---

## Common Pitfalls

1. **WSL paths** - Always use `get_wsl_path()` for Windows-to-WSL conversion
2. **Token expiration** - JWT expires after 5 minutes
3. **RSA key format** - `.env` uses escaped `\n`, restored by `env_config.py`
4. **Trivy SBOM only** - Uses `trivy sbom --format cyclonedx`, not vulnerability scans
5. **Missing tools** - Scan continues but marks tool as `skipped`
6. **No tests** - Verify via API and `logs/tool-output/` output

---

## File Structure

```
CICDSECURITY/
├── run.py, requirements.txt, .env
├── app/ (Flask routes, templates, static)
├── modules/ (control_apis.py, repos.py, history.py, etc.)
├── logs/ (app.log, tool-output/{scan_id}/)
└── tmp/ (cloned repos - auto-cleaned)
```

---

## Debugging

- **Logs:** `tail -f logs/app.log`
- **Scan results:** `ls logs/tool-output/{scan_id}/`
- **API test:** `curl http://localhost:5000/api/history`
- **Verify tools:** `wsl git --version`, `wsl trufflehog --version`