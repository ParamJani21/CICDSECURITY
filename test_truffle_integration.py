#!/usr/bin/env python3
"""
Test script to validate Truffle integration in CICDSECURITY.

Tests:
1. Flask app starts cleanly (no errors)
2. Triggers a test scan via API
3. Monitors for Truffle execution (STEP 3/6)
4. Verifies output files created (opengrep.json, truffle.json, trivy.json)
5. Checks Truffle results structure

Usage:
    python3 test_truffle_integration.py
"""

import subprocess
import time
import requests
import json
import os
import sys
import signal
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log(msg, level='INFO'):
    prefix = f"[{level}]"
    if level == 'INFO':
        print(f"{BLUE}{prefix}{RESET} {msg}")
    elif level == 'SUCCESS':
        print(f"{GREEN}{prefix}{RESET} {msg}")
    elif level == 'ERROR':
        print(f"{RED}{prefix}{RESET} {msg}")
    elif level == 'WARN':
        print(f"{YELLOW}{prefix}{RESET} {msg}")

def start_flask_app():
    """Start Flask app in background."""
    log("Starting Flask app (use_reloader=False to reduce inotify spam)...")
    
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    process = subprocess.Popen(
        [sys.executable, 'run.py'],
        cwd='/mnt/e/onlydash_CICDSECURITY/CICDSECURITY',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )
    
    return process

def wait_for_flask(max_wait=10):
    """Poll Flask health until it's ready."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            resp = requests.get('http://localhost:5000/api/overview', timeout=2)
            if resp.status_code == 200:
                log("Flask app is ready!", 'SUCCESS')
                return True
        except Exception:
            pass
        
        time.sleep(0.5)
    
    log("Flask app did not start within timeout", 'ERROR')
    return False

def trigger_test_scan():
    """Trigger a test scan via API."""
    log("Triggering test scan via API...")
    
    # Use a simple public test repo
    payload = {
        "repo_id": "test-123",
        "repo_name": "test-repo",
        "repo_owner": "test-org",
        "repo_url": "https://github.com/ParamJani21/FIND_ALL_JS.git",
        "repo_branch": "main"
    }
    
    try:
        resp = requests.post(
            'http://localhost:5000/api/repos/scan',
            json=payload,
            timeout=10
        )
        
        if resp.status_code == 202:
            result = resp.json()
            scan_id = result.get('scan_id')
            log(f"Scan triggered successfully! Scan ID: {scan_id}", 'SUCCESS')
            return scan_id
        else:
            log(f"Failed to trigger scan: {resp.status_code} {resp.text}", 'ERROR')
            return None
    except Exception as e:
        log(f"API request failed: {e}", 'ERROR')
        return None

def monitor_flask_logs(flask_process, scan_id, timeout=180):
    """Monitor Flask output for Truffle execution."""
    log(f"Monitoring Flask logs for STEP 3/6 (Truffle) and scan completion (timeout: {timeout}s)...")
    
    truffle_found = False
    completion_found = False
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        line = flask_process.stdout.readline()
        
        if not line:
            time.sleep(0.1)
            continue
        
        line = line.strip()
        
        # Look for key markers
        if 'STEP 3/6' in line and 'TRUFFLE' in line:
            log(f"✓ Found Truffle step: {line}", 'SUCCESS')
            truffle_found = True
        
        if 'STEP 6/6' in line or 'Scan completed' in line:
            log(f"✓ Found completion: {line}", 'SUCCESS')
            completion_found = True
        
        if 'ERROR' in line or 'FAILED' in line:
            log(f"⚠ {line}", 'WARN')
        
        # Keep printing meaningful lines
        if any(x in line for x in ['[Truffle]', 'STEP', 'findings', 'success']):
            print(f"  {line}")
        
        if truffle_found and completion_found:
            log("Scan appears to have completed successfully", 'SUCCESS')
            return True
    
    log(f"Timeout reached. Truffle found: {truffle_found}, Completion found: {completion_found}", 'WARN')
    return truffle_found

def verify_output_files(scan_id):
    """Verify that output JSON files were created."""
    if not scan_id:
        log("No scan ID provided, skipping file verification", 'WARN')
        return False
    
    log(f"Verifying output files for scan {scan_id}...")
    
    output_dir = Path(f'/mnt/e/onlydash_CICDSECURITY/CICDSECURITY/logs/tool-output/{scan_id}')
    
    if not output_dir.exists():
        log(f"Output directory not found: {output_dir}", 'ERROR')
        return False
    
    expected_files = [
        'opengrep.json',
        'truffle.json',
        'trivy.json'
    ]
    
    all_found = True
    for filename in expected_files:
        filepath = output_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            log(f"✓ Found {filename} ({size} bytes)", 'SUCCESS')
            
            # Try to parse JSON to verify structure
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    if filename == 'truffle.json':
                        # Verify Truffle structure
                        if 'status' in data:
                            log(f"  └─ status: {data['status']}", 'INFO')
                        if 'findings_count' in data:
                            log(f"  └─ findings: {data['findings_count']}", 'INFO')
            except Exception as e:
                log(f"  └─ Failed to parse JSON: {e}", 'WARN')
        else:
            log(f"✗ Missing {filename}", 'ERROR')
            all_found = False
    
    return all_found

def main():
    """Main test flow."""
    print(f"\n{BLUE}{'='*70}")
    print("CICDSECURITY Truffle Integration Test")
    print('='*70 + f"{RESET}\n")
    
    flask_process = None
    
    try:
        # Step 1: Start Flask
        flask_process = start_flask_app()
        time.sleep(2)  # Give it a moment to initialize
        
        if not wait_for_flask():
            log("Aborting: Flask app failed to start", 'ERROR')
            return 1
        
        # Step 2: Trigger scan
        scan_id = trigger_test_scan()
        if not scan_id:
            log("Aborting: Failed to trigger scan", 'ERROR')
            return 1
        
        # Step 3: Monitor logs
        scan_success = monitor_flask_logs(flask_process, scan_id, timeout=300)
        
        # Step 4: Verify files
        time.sleep(5)  # Wait a bit for final writes
        files_ok = verify_output_files(scan_id)
        
        # Summary
        print(f"\n{BLUE}{'='*70}")
        print("Test Results")
        print('='*70 + f"{RESET}\n")
        
        if scan_success and files_ok:
            log("✓ All tests passed! Truffle integration is working.", 'SUCCESS')
            return 0
        else:
            if not scan_success:
                log("✗ Scan execution may have failed or timed out", 'ERROR')
            if not files_ok:
                log("✗ Output files not found or incomplete", 'ERROR')
            return 1
    
    except KeyboardInterrupt:
        log("\nTest interrupted by user", 'WARN')
        return 1
    
    finally:
        if flask_process:
            log("Shutting down Flask app...")
            flask_process.send_signal(signal.SIGTERM)
            try:
                flask_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                flask_process.kill()
            log("Flask app stopped", 'INFO')

if __name__ == '__main__':
    sys.exit(main())
