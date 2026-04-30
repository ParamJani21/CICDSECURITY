# Trivy SBOM Configuration - CICDSECURITY

## ✅ Configuration Summary

The Trivy security scanner has been configured to **SBOM-only mode** with **secret scanning disabled**.

**Modified:** `modules/control_apis.py` - `run_trivy_scan()` function

---

## 🔍 What Trivy Scans Now

### ✅ ENABLED SCANNERS (3 scanners)

| Scanner | Purpose | Description |
|---------|---------|-------------|
| **vuln** | Vulnerability Scanning | Detects known vulnerabilities in third-party dependencies |
| **misconfig** | Misconfiguration Scanning | Identifies configuration issues in infrastructure code (Terraform, K8s, etc.) |
| **license** | License Compliance | Checks for license compatibility and compliance issues |

### ❌ DISABLED SCANNERS

| Scanner | Status | Reason |
|---------|--------|--------|
| **secret** | DISABLED | Not required per requirements |
| **rootfs** | DISABLED | Not needed for SBOM |

---

## 📋 Command Configuration

**Current Trivy Command** (Line 800-808):
```bash
trivy fs \
  --format json \
  --scanners vuln,misconfig,license \
  --exit-code 0 \
  --no-progress \
  .
```

### Command Breakdown:
- `trivy fs` - Filesystem scan mode
- `--format json` - Output in JSON format for parsing
- `--scanners vuln,misconfig,license` - **Only these three scanners enabled**
- `--exit-code 0` - Always exit with success (don't fail the workflow)
- `--no-progress` - Suppress progress output
- `.` - Scan current directory recursively

---

## 📊 Output Structure

Trivy results are saved to: `logs/tool-output/{scan_id}/trivy.json`

**Sample JSON structure:**
```json
{
  "scan_id": "uuid-123",
  "timestamp": "2025-04-30T12:34:56.789123",
  "repository": "repo_name",
  "status": "completed",
  "results": [
    {
      "Target": "package.json",
      "Type": "npm",
      "Vulnerabilities": [
        {
          "VulnerabilityID": "CVE-2021-12345",
          "Severity": "HIGH",
          "Title": "Package XYZ Remote Code Execution",
          "Description": "...",
          "PkgName": "dependency-name",
          "InstalledVersion": "1.0.0"
        }
      ]
    }
  ],
  "findings_count": 5
}
```

---

## 🔧 Configuration Details

### Lines Modified: 743-808

**Before:**
```python
def run_trivy_scan(repo_path, scan_id):
    """Run Trivy security scan on repository using WSL"""
    # ...
    trivy_cmd = (
        f'cd {wsl_repo_path} && '
        f'trivy fs '
        f'--format json '
        f'--exit-code 0 '
        f'--no-progress '
        f'. 2>&1 || true'
    )
```

**After:**
```python
def run_trivy_scan(repo_path, scan_id):
    """
    Run Trivy SBOM (Software Bill of Materials) scan on repository using WSL
    
    ✅ ENABLED SCANNERS:
       - vuln       : Scans for known vulnerabilities in dependencies
       - misconfig  : Scans for misconfigurations in infrastructure code
       - license    : Scans for license compliance issues
    
    ❌ DISABLED SCANNERS:
       - secret     : Secret/credential scanning is DISABLED
    """
    # ...
    logger.info('[Trivy] Starting SBOM (Software Bill of Materials) scan...')
    logger.info('[Trivy] Scanning for: vulnerability, misconfig, license')
    logger.info('[Trivy] Disabled: secret scanning')
    
    trivy_cmd = (
        f'cd {wsl_repo_path} && '
        f'trivy fs '
        f'--format json '
        f'--scanners vuln,misconfig,license '
        f'--exit-code 0 '
        f'--no-progress '
        f'. 2>&1 || true'
    )
```

---

## 📍 Scan Workflow Integration

The modified Trivy scan is **Step 3 of 5** in the complete workflow:

```
1. CLONE REPOSITORY
2. RUN OPENGREP SCAN (static code analysis)
3. RUN TRIVY SCAN    ← Modified (SBOM-only, no secrets)
4. SAVE RESULTS
5. CLEANUP
```

---

## 🚀 How to Use

### Manual Scan via API:
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

### Results Location:
- **Trivy Results:** `logs/tool-output/{scan_id}/trivy.json`
- **OpenGrep Results:** `logs/tool-output/{scan_id}/opengrep.json`
- **Combined Scan Log:** `logs/`

---

## 📝 Logging

Enhanced logging has been added to indicate:
- Scanner status: `[Trivy] Starting SBOM (Software Bill of Materials) scan...`
- Enabled scanners: `[Trivy] Scanning for: vulnerability, misconfig, license`
- Disabled features: `[Trivy] Disabled: secret scanning`

Monitor logs during scan execution:
```bash
tail -f logs/app.log | grep Trivy
```

---

## ⚙️ To Modify Configuration

**Location:** `modules/control_apis.py` → Line 804

### Add Additional Scanners:
```python
--scanners vuln,misconfig,license,rbac
```

### Remove a Scanner:
```python
--scanners vuln,license  # Removes misconfig
```

### Re-enable Secret Scanning (not recommended):
```python
--scanners vuln,misconfig,license,secret
```

---

## 📚 Related Files

| File | Purpose |
|------|---------|
| `modules/control_apis.py:743-872` | Trivy scan implementation |
| `modules/control_apis.py:956-1139` | Main workflow orchestration |
| `app/routes.py:58-95` | Manual scan trigger endpoint |
| `modules/scan_api.py` | Scan API routes |

---

## 🔗 References

- **Trivy Documentation:** https://aquasecurity.github.io/trivy/
- **SBOM (Software Bill of Materials):** https://en.wikipedia.org/wiki/Software_bill_of_materials
- **Trivy Scanners:** https://aquasecurity.github.io/trivy/latest/scanners/

---

**Last Updated:** 2025-04-30
**Configuration Status:** ✅ SBOM-Only Mode Enabled
