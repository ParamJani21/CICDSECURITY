# Truffle Integration - Quick Reference

## File Changed
- `modules/control_apis.py` → Added 142-line function, updated workflow

## New Function
**`run_truffle_scan(repo_path, scan_id)`** @ Line 743
- Scans for secrets: API keys, tokens, passwords, credentials
- Returns: `(success, results_dict)`

## Workflow (6 Steps)
1. **CLONE** – Git clone repository
2. **OPENGREP** – Static code analysis (critical, blocks on failure)
3. **TRUFFLE** – Secret scanning ← NEW (non-blocking)
4. **TRIVY** – Vulnerability/SBOM scan (non-blocking)
5. **SAVE** – Write results to JSON files
6. **CLEANUP** – Remove cloned repo

## Output Files
```
logs/tool-output/{scan_id}/
├── opengrep.json
├── truffle.json    ← NEW
└── trivy.json
```

## Truffle Command (WSL)
```bash
truffle filesystem . --json --no-update \
  --exclude .git,node_modules,venv,.venv,__pycache__
```

## Log Markers
- `[Truffle] Checking for truffle availability in WSL...`
- `[Truffle] Starting secret scanning...`
- `[Truffle] ✓ Found X potential secrets`

## If Truffle Not Installed
- Scan marks step as `skipped`
- Workflow continues (non-blocking)
- Only `opengrep.json` and `trivy.json` saved

## Install Truffle
```bash
wsl npm install -g truffle-cli
```

## Test It
```bash
# Trigger scan
curl -X POST http://localhost:5000/api/repos/scan \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id":"999","repo_name":"test-repo",
    "repo_owner":"test-owner",
    "repo_url":"https://github.com/ParamJani21/FIND_ALL_JS.git",
    "repo_branch":"main"
  }'

# Monitor logs
tail -f logs/app.log | grep STEP

# Check results
ls logs/tool-output/*/
cat logs/tool-output/*/truffle.json
```

## Key Points
✓ Syntax verified  
✓ All 6 steps numbered  
✓ Truffle function added  
✓ Combined results include Truffle  
✓ Results saved to truffle.json  
✓ Non-blocking on failure  
✓ Documentation updated  

**Status:** Ready for testing
