# Truffle Integration - Testing & Validation Phase

## Changes Made to Fix Flask Logging

### 1. **app/__init__.py** - Logging Configuration
- Changed werkzeug level from DEBUG to INFO (line 34) to reduce noise
- Added suppression for Flask serving/security loggers (lines 36-37)
- Added suppression for watchdog observers and inotify_buffer (lines 46-48)
- This eliminates the inotify event spam while keeping meaningful application logs

### 2. **run.py** - Flask Server Configuration
- Changed from `app.run(debug=True)` to `app.run(debug=True, use_reloader=False)` (line 6)
- `use_reloader=False` disables Flask's auto-reload file watcher, eliminating the watchdog spam
- Debug mode remains enabled for exception handling and error pages

## Why These Changes Help

**Problem:** Flask's development server includes:
1. **Werkzeug file watcher** (watchdog) - monitors files for changes to auto-reload
2. **inotify buffer** - logs every file system event (thousands per second)
3. This resulted in logs being polluted with DEBUG-level events, making scan execution hard to follow

**Solution:**
- Disable the reloader (we don't need auto-reload for scanning)
- Suppress watchdog/werkzeug DEBUG logs to show only WARNING+ messages
- Keep app DEBUG logs for scan execution visibility

## Expected Behavior After Changes

1. **Flask startup** - Clean, minimal output:
   ```
   [timestamp] INFO in app: App initialized, logging configured. Logs writing to logs/app.log
   WARNING:werkzeug:WARNING: This is a development server...
   WARNING:werkzeug:Running on http://127.0.0.1:5000
   ```

2. **Scan execution** - Clean workflow logs with all 6 steps visible:
   ```
   ╔════════════════════════════════════════════════════════════════════════════╗
   ║ STEP 1/6: CLONING REPOSITORY
   [timestamp] INFO in modules: 🔍 CLONING: repo-id...

   ║ STEP 2/6: RUNNING OPENGREP SCAN
   [timestamp] INFO in modules: 🔍 OPENGREP SCAN...
   [timestamp] INFO in modules: [OpenGrep] Starting scan...

   ║ STEP 3/6: RUNNING TRUFFLE SCAN (SECRETS)
   [timestamp] INFO in modules: 🔍 TRUFFLE SCAN...
   [timestamp] INFO in modules: [Truffle] Checking for truffle availability...

   ║ STEP 4/6: RUNNING TRIVY SCAN
   [timestamp] INFO in modules: 🔍 TRIVY SCAN...

   ║ STEP 5/6: SAVING RESULTS
   [timestamp] INFO in modules: Saving OpenGrep results to opengrep.json...
   [timestamp] INFO in modules: Saving Truffle results to truffle.json...
   [timestamp] INFO in modules: Saving Trivy results to trivy.json...

   ║ STEP 6/6: CLEANUP
   [timestamp] INFO in modules: Cleaning up cloned repo...
   ```

## Files Modified

1. `/mnt/e/onlydash_CICDSECURITY/CICDSECURITY/app/__init__.py` (lines 34-48)
2. `/mnt/e/onlydash_CICDSECURITY/CICDSECURITY/run.py` (line 6)

## Testing Plan

1. **Start Flask app:**
   ```bash
   cd /mnt/e/onlydash_CICDSECURITY/CICDSECURITY
   python3 run.py
   ```
   - Expect: Clean startup with no inotify spam
   - Check: First 20 lines of logs/app.log should be meaningful, not file-system events

2. **Trigger test scan via API:**
   ```bash
   curl -X POST http://localhost:5000/api/repos/scan \
     -H "Content-Type: application/json" \
     -d '{
       "repo_id": "test-123",
       "repo_name": "test-repo",
       "repo_owner": "test-org",
       "repo_url": "https://github.com/ParamJani21/FIND_ALL_JS.git",
       "repo_branch": "main"
     }'
   ```
   - Response: `{"scan_id": "scan_xxx", "status": "pending"}`

3. **Monitor logs for workflow completion:**
   - Watch for all 6 STEPs in logs
   - Look for `[Truffle]` prefix logs
   - Check for completion message

4. **Verify output files:**
   - Check `logs/tool-output/{scan_id}/` directory
   - Files should exist: `opengrep.json`, `truffle.json`, `trivy.json`
   - Each JSON should be valid and contain expected structure

## Next Steps

After testing, verify:
- [ ] Flask app starts cleanly without inotify spam
- [ ] API responds to scan request
- [ ] All 6 workflow steps visible in logs
- [ ] STEP 3/6 (Truffle) executes (or marks as skipped if not installed)
- [ ] All three JSON files created
- [ ] Truffle JSON has proper structure (`status`, `findings_count`, `results`)
- [ ] Scan completion logged with summary metrics

## Known Limitations

1. **Truffle installation:** Currently not installed in WSL; scan will mark as `skipped` but continue
   - To enable: `wsl npm install -g @trufflesecurity/trufflehog` or install via Homebrew
   
2. **GitHub App auth:** Requires valid `.env` with GitHub App credentials
   - If auth fails, clone step will fail and stop workflow
   - Check logs for auth errors if clone fails

3. **Network access:** Requires internet to clone GitHub repos
   - If network restricted, clone will fail

4. **Tool availability:** OpenGrep and Trivy must be available in WSL
   - If missing, those scans will fail/skip accordingly
