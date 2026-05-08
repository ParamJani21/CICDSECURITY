# PHASE 3 - GENUINE FEATURE ROADMAP (Based on Actual Codebase Audit)

## Current Implementation Status

### ✅ What We Have (Phase 1 & 2 Complete)
- Authentication system (login, password change, lockout)
- Database models and ORM
- Scan execution (OpenGrep, TruffleHog, Trivy)
- Dashboard UI with user menu
- Performance optimization (lazy loading, caching)
- Findings filtering (.git/ exclusion)
- Settings tab for GitHub credentials (UI only, stored in .env)
- HTML report generation (all scans, no filtering)
- Brute force protection (5 attempts lockout)
- Audit logging

### ⚠️ Partial Implementation (Needs Work)
- **CSRF Protection:** Only SameSite cookie; missing token validation on forms
- **Rate Limiting:** Brute force only; NO API endpoint protection
- **Credentials Management:** Can edit in UI but stored plaintext in .env (not encrypted)

### ❌ Missing Features (Not Implemented)
- Real-time scan status updates (WebSocket/SSE)
- Advanced search & filtering UI (findings by severity, tool, file)
- Findings filtering API (query params for /api/history)
- Filtered report export (PDF, CSV, XLSX)
- PDF/CSV/XLSX export formats
- Two-factor authentication (2FA/TOTP)
- API rate limiting (endpoints unprotected)
- CSRF token validation

---

## Phase 3 - Feature Priority Roadmap

### TIER 1: CRITICAL (Must Have for Production) - 8-10 hours

#### 1.1 Search & Filter Findings UI
**Why:** Users can't find critical issues in a list of 100+ findings
**What:**
- Search box: search by filename, title, message, CWE
- Filter dropdowns: severity (CRITICAL/HIGH/MEDIUM/LOW), tool (OpenGrep/TruffleHog/Trivy), category (secrets/code)
- Real-time filtering of displayed findings
- Save filter presets (e.g., "Show only CRITICAL from Truffle")
- Export filtered findings to report

**Files to Modify:**
- `templates/dashboard.html` - Add filter UI below history header
- `static/dashboard.js` - Add filterFindings(), applyFilters(), clearFilters()
- `app/routes.py` - Add /api/history/filter endpoint with query params

**Effort:** 3-4 hours

---

#### 1.2 Advanced Report Export (PDF + CSV)
**Why:** Currently only HTML export; PDF needed for compliance/audits
**What:**
- PDF export using WeasyPrint or ReportLab
- CSV export (findings table with all metadata)
- XLSX export (multi-sheet: summary + findings + statistics)
- Apply filters to export (export only CRITICAL findings, etc)
- Professional formatting with company branding

**Files to Modify:**
- `app/routes.py` - New endpoints: /api/export/pdf, /api/export/csv, /api/export/xlsx
- `requirements.txt` - Add reportlab or weasyprint
- `templates/` - PDF template if using template approach

**Effort:** 4-5 hours

---

#### 1.3 CSRF Token Protection (Complete)
**Why:** Currently only cookie-based; forms vulnerable to CSRF attacks
**What:**
- Add Flask-WTF for CSRF token generation
- Add `{{ csrf_token() }}` to all forms (login, change-password, settings)
- Validate tokens on form submissions
- Return 403 on invalid token

**Files to Modify:**
- `requirements.txt` - Add Flask-WTF
- `app/__init__.py` - Initialize CSRF protection
- `templates/login.html` - Add token field
- `templates/change_password.html` - Add token field
- `templates/dashboard.html` - Add token to settings form

**Effort:** 2-3 hours

---

#### 1.4 Secure Credentials Storage
**Why:** Currently storing GitHub keys in plaintext .env
**What:**
- Encrypt secrets in database (use cryptography library)
- Store App ID and Secret Key in users table (encrypted)
- Decrypt on-the-fly when needed for GitHub API calls
- Update UI to handle encrypted storage
- Add "Test Credentials" button to validate before saving

**Files to Modify:**
- `models/database.py` - Add encrypted_github_key, encrypted_github_app_id to User model
- `app/routes.py` - Update /api/settings/github POST endpoint
- `modules/repos.py` - Decrypt credentials before use
- `static/dashboard.js` - Add test credentials functionality

**Effort:** 3-4 hours

---

### TIER 2: HIGH VALUE (Nice to Have, High Impact) - 6-8 hours

#### 2.1 API Endpoint Rate Limiting
**Why:** Prevent API abuse, brute force on scan endpoints
**What:**
- Use Flask-Limiter for rate limiting
- Limit login attempts: 5 per minute per IP
- Limit API calls: 30 scans per hour per user
- Limit export: 5 exports per minute per user
- Return 429 Too Many Requests when exceeded

**Files to Modify:**
- `requirements.txt` - Add Flask-Limiter
- `app/__init__.py` - Initialize limiter
- `auth/decorators.py` - Add @limiter decorators
- `app/routes.py` - Add rate limits to /api/* endpoints

**Effort:** 2-3 hours

---

#### 2.2 Real-Time Scan Status Updates
**Why:** Users don't know when scan completes; currently must refresh manually
**What:**
- WebSocket connection (Flask-SocketIO) or Server-Sent Events (SSE)
- Emit events as scan progresses: started → cloned → scanned → merged → saved → complete
- Toast notifications when scan finishes
- Live findings count as tools report
- Remove polling; replace with event-driven updates

**Files to Modify:**
- `requirements.txt` - Add Flask-SocketIO (or use SSE)
- `app/__init__.py` - Initialize SocketIO
- `app/routes.py` - Add WebSocket event handlers
- `modules/control_apis.py` - Emit progress events during scan
- `static/dashboard.js` - Listen to WebSocket events, update UI
- `templates/dashboard.html` - Add toast notifications

**Effort:** 4-5 hours

---

#### 2.3 Two-Factor Authentication (2FA/TOTP)
**Why:** Credential security; required for enterprise deployments
**What:**
- Generate TOTP (Time-based One-Time Password) with pyotp
- QR code for authenticator apps (Google Authenticator, Authy)
- User setup flow: enable 2FA → show QR → scan → verify code
- Login flow: username/password → 6-digit code prompt
- Recovery codes for account recovery if device lost

**Files to Modify:**
- `requirements.txt` - Add pyotp, qrcode
- `models/database.py` - Add totp_secret, totp_enabled to User model
- `app/auth_routes.py` - Add /auth/2fa/setup, /auth/2fa/verify endpoints
- `templates/` - Create 2fa-setup.html, 2fa-verify.html
- `static/` - Add 2FA form handling JavaScript

**Effort:** 3-4 hours

---

### TIER 3: NICE TO HAVE (Lower Priority) - 5-7 hours

#### 3.1 Finding Statistics & Analytics Dashboard
**Why:** No insights into security trends, vulnerability distribution
**What:**
- Chart: Findings over time (line chart)
- Chart: Severity distribution (pie chart)
- Chart: Tool comparison (bar chart - OpenGrep vs TruffleHog vs Trivy findings)
- Metrics: Most vulnerable repos, highest severity findings
- Trends: Are we fixing findings faster? Is count increasing?

**Files to Modify:**
- `templates/dashboard.html` - Add analytics tab
- `static/dashboard.js` - Add chart rendering (Chart.js or similar)
- `app/routes.py` - Add /api/analytics endpoint

**Effort:** 3-4 hours

---

#### 3.2 User Management & Roles (Multi-User Support)
**Why:** Currently only one admin; need multi-team support
**What:**
- Admin dashboard to create/edit/disable users
- Roles: Admin (full access), Auditor (read-only), Operator (scan only)
- Show who ran each scan (user_id in scan history)
- Team assignments
- User activity log

**Files to Modify:**
- `templates/dashboard.html` - Add users management tab
- `app/routes.py` - Add /api/users/* CRUD endpoints
- `models/database.py` - Already has role field, add team support
- `static/dashboard.js` - Add users UI management

**Effort:** 4-5 hours

---

#### 3.3 Scheduled Scans & Automation
**Why:** Manual scans only; need continuous security
**What:**
- Schedule periodic scans (daily, weekly, monthly)
- Scan on GitHub webhook events (push to main, new PR)
- Background job queue (APScheduler)
- Schedule management UI
- Enable/disable per repo

**Files to Modify:**
- `requirements.txt` - Add APScheduler
- `modules/scheduler.py` - New file for background jobs
- `models/database.py` - Add ScanSchedule model
- `app/routes.py` - Add /api/schedules/* endpoints
- `templates/dashboard.html` - Add schedules UI

**Effort:** 5-6 hours

---

## Recommended Execution Order

### **PHASE 3A (Weeks 1-2) - SECURITY & USABILITY - 10-12 hours**
1. ✅ Search & Filter Findings (3-4 hrs)
2. ✅ CSRF Token Protection (2-3 hrs)
3. ✅ Secure Credentials Storage (3-4 hrs)
4. ✅ Advanced Report Export - PDF/CSV (4-5 hrs)

**Result:** Secure, usable production-ready dashboard

---

### **PHASE 3B (Weeks 3-4) - PROTECTION & REAL-TIME - 6-8 hours**
1. ✅ API Rate Limiting (2-3 hrs)
2. ✅ Real-Time Scan Updates (4-5 hrs)

**Result:** Fast, protected API; live scan status

---

### **PHASE 3C (Weeks 5-6) - ENTERPRISE - 7-9 hours**
1. ✅ Two-Factor Authentication (3-4 hrs)
2. ✅ Analytics Dashboard (3-4 hrs)
3. ✅ User Management & Roles (4-5 hrs)

**Result:** Enterprise-ready multi-user system

---

### **PHASE 3D (Optional) - ADVANCED - 5-6 hours**
1. ✅ Scheduled Scans & Webhooks (5-6 hrs)

**Result:** Fully automated continuous security

---

## Summary Table: What's Missing vs What's Needed

| Feature | Needed? | Status | TIER | Hours |
|---------|---------|--------|------|-------|
| Search & Filter Findings | YES | ❌ | 1 | 3-4 |
| PDF/CSV Export | YES | ❌ | 1 | 4-5 |
| CSRF Tokens | YES | ⚠️ | 1 | 2-3 |
| Secure Credentials | YES | ⚠️ | 1 | 3-4 |
| API Rate Limiting | YES | ⚠️ | 2 | 2-3 |
| Real-Time Updates | MAYBE | ❌ | 2 | 4-5 |
| 2FA/TOTP | MAYBE | ❌ | 2 | 3-4 |
| Analytics | NO | ❌ | 3 | 3-4 |
| User Management | NO | ⚠️ | 3 | 4-5 |
| Scheduled Scans | NO | ❌ | 3 | 5-6 |

---

## Your Preferences Noted

You requested:
1. **Advanced Search & Filtering with Filtered Export** ✅ → TIER 1.1 + 1.2
2. **Settings Management** ✅ Already exists (TIER 1.4 improves security)
3. **Real-Time Updates** ✅ → TIER 2.2
4. **Report Generation** ✅ Already HTML (TIER 1.2 adds PDF/CSV)
5. **Security Enhancements** ✅ → TIER 1.3, 2.1

**Recommendation:** Start with PHASE 3A (Tiers 1.1-1.4) = 12-14 hours for a production-ready, secure dashboard.

---

## What's Your Priority?

Choose one:
- **PHASE 3A ONLY** (Security + Usability): 10-12 hours
- **PHASE 3A + 3B** (Add Real-Time): 16-20 hours
- **FULL PHASE 3** (All features): 30+ hours
- **Custom** (pick specific features)

I'll create detailed implementation plans once you decide! 🚀
