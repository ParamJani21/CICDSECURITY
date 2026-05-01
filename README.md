# CICDSECURITY

A Flask-based security scanning orchestration dashboard for GitHub repositories. This tool automates security scans by integrating multiple security tools (OpenGrep, Slither, Trivy, TruffleHog) to scan GitHub repositories via GitHub App authentication.

## Features

- **GitHub App Integration** - Authenticate and scan repositories via GitHub App
- **SATS (Static Analysis)** - OpenGrep + Slither for Python smart contract analysis
- **SBOM (Software Bill of Materials)** - Trivy for generating SBOM (CycloneDX format)
- **Secret Scanning** - TruffleHog for detecting exposed secrets, tokens, and credentials
- **Selectable Scan Types** - Choose which scans to run (SATS, SBOM, SECRET, or any combination)
- **Scan History** - View and manage past scan results
- **Export Reports** - Generate HTML reports of scan findings

## Prerequisites

- Python 3.8+
- WSL (Windows Subsystem for Linux) - for running security tools
- GitHub App credentials (App ID and private key)

## Tools Installation

Install the following security tools in your WSL environment:

```bash
# OpenGrep (Static Code Analysis)
go install github.com/PatrickKhanz/owasp-gpt@latest

# Slither (Python Smart Contract Analysis)
pip install slither-analyzer

# Trivy (SBOM Scanning)
wsl sudo apt-get install wget && \
wsl wget https://github.com/aquasecurity/trivy/releases/download/v0.51.0/trivy_0.51.0_Linux-64bit.tar.gz -O trivy.tar.gz && \
wsl tar zxvf trivy.tar.gz -C /usr/local/bin/ && \
wsl rm trivy.tar.gz

# TruffleHog (Secret Scanning)
go install github.com/trufflesecurity/trufflehog/v3@latest
```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your GitHub App credentials:
   ```
   GITHUB_APP_ID=your_app_id
   GITHUB_PRIVATE_KEY="your_private_key_content"
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Dashboard

Start the Flask application:

```bash
python3 run.py
```

The dashboard will be available at: **http://localhost:5000**

## Usage

1. **Repositories Tab** - View all repositories from your GitHub App
2. **Scan a Repository** - Click "Scan" to trigger a security scan
3. **Select Scan Types** - Choose which scans to run (SATS, SBOM, SECRET)
4. **Scan All Repos** - Trigger scans for all repositories at once
5. **History Tab** - View scan results, expand details, and manage findings
6. **Export Report** - Generate an HTML report of scan findings

## License

MIT License