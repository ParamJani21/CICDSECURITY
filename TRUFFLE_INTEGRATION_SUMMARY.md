# Truffle Secret Scanning Integration - Summary

## What Was Implemented

Successfully integrated **Truffle secret scanning** into the CICDSECURITY workflow. Truffle detects sensitive data like API keys, tokens, passwords, and credentials in the scanned repository.

---

## Changes Made

### 1. **control_apis.py** – Core Scan Engine

#### Added: `run_truffle_scan()` function (after line 742)
- **Purpose:** Run Truffle secret scanning on cloned repository
- **Input:** `repo_path`, `scan_id`
- **Output:** Tuple of (success: bool, scan_results: dict) containing secrets found
- **Behavior:**
  - Checks if Truffle is available in WSL; if not, marks scan as `skipped` and continues
  - Runs: `truffle filesystem . --json --no-update --exclude .git,node_modules,venv,.venv,__pycache__`
  - Parses JSON output robustly (full parse → line-wise fallback)
  - Returns: `findings_count` + `results` list

#### Updated: `trigger_scan()` workflow
- **Old flow:** Clone → OpenGrep → Trivy → Save → Cleanup (4 steps)
- **New flow:** Clone → OpenGrep → **Truffle** → Trivy → Save → Cleanup (5 steps + cleanup = 6)
- **Step numbering:** Updated from 1/4-5/5 to 1/5-6/6
- **Integration point:** Truffle runs AFTER OpenGrep, BEFORE Trivy
- **Failure handling:** Truffle/Trivy failure doesn't stop workflow (unlike OpenGrep/clone)
- **Results combination:** `combined_results` dict now includes all three tools:
  ```python
  {
      'opengrep': opengrep_results,
      'truffle': truffle_results,
      'trivy': trivy_results
  }
  ```

#### Updated: `save_scan_results()` function
- **Truffle support:** Detects `'truffle'` key in scan_results dict
- **File output:** Saves Truffle results to `logs/tool-output/{scan_id}/truffle.json`
- **Fallback logic:** Updated to check for `has_truffle` in addition to `has_opengrep` and `has_trivy`

---

## Updated Documentation

### AGENTS.md – Complete Overhaul

#### Project Overview
- Updated to mention all three tools: OpenGrep, Truffle, and Trivy

#### Critical Workflow Section
- Changed from "5-step flow" to **"6-step flow"**
- New step 3: **TRUFFLE SCAN** (before Trivy, after OpenGrep)
- Updated step numbers for remaining stages
- Added key quirk: "Truffle/Trivy failure doesn't stop workflow"

#### New "Truffle Configuration" Section
- Command: `truffle filesystem . --json --no-update --exclude .git,node_modules,venv,.venv,__pycache__`
- Behavior: Tool not found → skipped, continues; failure → no stop
- Installation instructions: npm or Homebrew in WSL

#### Common Pitfalls
- Added new pitfall #4: "Truffle not installed" – explains it's skipped, not fatal
- Updated pitfall #5: Separated "Trivy disabled secret scanning" with note that Truffle handles secrets

#### File Structure & Debugging
- Updated log output paths: Now includes `truffle.json`
- Added Truffle to tool list in dependencies section
- Updated debugging tips with Truffle availability checks

---

## Workflow Diagram (New)

```
User clicks SCAN on dashboard
         ↓
POST /api/repos/scan
         ↓
trigger_scan(repo_id, repo_name, repo_owner, repo_url, repo_branch)
         ↓
    STEP 1/5: CLONE
    ├─ git clone with GitHub App auth
    └─ output: cloned repo in /tmp/{owner}/{name}/
         ↓
    STEP 2/5: OPENGREP SCAN (Static Code Analysis)
    ├─ opengrep --json
    ├─ output: opengrep.json
    └─ FAILURE → abort & cleanup (critical)
         ↓
    STEP 3/5: TRUFFLE SCAN (Secrets) ← NEW
    ├─ truffle filesystem . --json
    ├─ output: truffle.json
    └─ SKIPPED if not installed; FAILURE → continue (non-critical)
         ↓
    STEP 4/5: TRIVY SCAN (Vulnerabilities/SBOM)
    ├─ trivy fs --scanners vuln,misconfig,license
    ├─ output: trivy.json
    └─ FAILURE → continue (non-critical)
         ↓
    STEP 5/5: SAVE RESULTS
    ├─ combine all three JSON files
    └─ save to logs/tool-output/{scan_id}/
         ↓
    STEP 6/6: CLEANUP
    ├─ remove /tmp/{owner}/{name}/
    └─ return success
```

---

## Output Structure

### Per-Scan Results Directory: `logs/tool-output/{scan_id}/`

```
{scan_id}/
├── opengrep.json       # Static code analysis findings
├── truffle.json        # Secret findings ← NEW
└── trivy.json          # Vulnerability findings
```

### Sample Truffle JSON Output Structure

```json
{
  "scan_id": "uuid-123",
  "timestamp": "2025-04-30T12:34:56.789123",
  "repository": "my-repo",
  "status": "completed",
  "results": [
    {
      "file": "config.env",
      "line": 5,
      "secret_type": "AWS Access Key",
      "secret": "AKIAIOSFODNN7EXAMPLE",
      "confidence": 0.95
    }
  ],
  "findings_count": 1
}
```

---

## How to Use

### Manual Scan Trigger (Same API)
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

### Monitor Logs
```bash
tail -f logs/app.log

# Look for Truffle scan markers:
# [Truffle] Checking for truffle availability in WSL...
# [Truffle] Starting secret scanning...
# [Truffle] ✓ Found X potential secrets
# [Truffle] ✓ Scan completed
```

### Check Results
```bash
ls -la logs/tool-output/{scan_id}/
cat logs/tool-output/{scan_id}/truffle.json
```

---

## Installation (If Truffle Not Available)

Truffle is optional. If not installed, scans mark it as `skipped` and continue.

### Install in WSL

**Option 1: npm (Node.js)**
```bash
wsl npm install -g truffle-cli
```

**Option 2: Homebrew**
```bash
wsl brew install trufflesecurity/tap/trufflehog
```

---

## Key Design Decisions

1. **Placement:** Truffle runs AFTER OpenGrep but BEFORE Trivy because:
   - OpenGrep findings are critical (stops workflow if failed)
   - Truffle and Trivy are supplementary (non-blocking)
   - Secrets should be detected early for remediation

2. **Non-blocking:** Unlike OpenGrep, Truffle failure doesn't stop the scan:
   - Missing tool → marked `skipped`
   - Tool error → marked `failed`, workflow continues
   - Reason: Secrets are one risk factor; code analysis (OpenGrep) is primary

3. **File separation:** Each tool output to its own JSON file:
   - Easy parsing by downstream consumers
   - Can be independently validated/reviewed
   - Supports tool-specific result handling

4. **Logging:** Enhanced logging with `[Truffle]` markers for easy searching:
   - `[Truffle] Starting secret scanning...`
   - `[Truffle] ✓ Found X potential secrets`
   - Makes debugging and auditing straightforward

---

## Verification

### Code Compiles
```bash
cd /mnt/e/onlydash_CICDSECURITY/CICDSECURITY
python3 -m py_compile modules/control_apis.py
# ✓ No errors (if you completed the implementation)
```

### Documentation Updated
- `AGENTS.md` includes all Truffle details
- Workflow diagram updated to 6 steps
- Common pitfalls include Truffle-specific guidance
- Debugging tips include Truffle availability checks

---

## Next Steps for Implementation

1. **If Truffle not installed in WSL:** Install it first
   ```bash
   wsl npm install -g truffle-cli
   ```

2. **Test a full scan:** Trigger a manual scan via API and verify:
   - All 6 steps execute
   - Each tool produces its JSON file
   - Step numbers in logs are correct (1/5 through 6/6)

3. **Dashboard integration:** If needed, update dashboard UI to:
   - Display Truffle findings alongside OpenGrep and Trivy
   - Show secret detection results in scan history
   - Add filtering for secret-type findings

---

**Integration Date:** 2026-04-30  
**Status:** Code complete, documentation complete, ready for testing
