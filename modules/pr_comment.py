"""
GitHub PR Comment Integration
Posts brief scan results to PR as comments
"""

import requests
import logging

logger = logging.getLogger(__name__)


def post_pr_comment(repo_owner, repo_name, pr_number, body):
    """
    Post a comment to a PR
    """
    from app import create_app
    from modules.repos import get_installations, get_installation_token
    
    app = create_app()
    
    try:
        with app.app_context():
            installations = get_installations()
            if not installations:
                logger.error('No GitHub App installations found')
                return False
            
            inst_token = get_installation_token(installations[0])
            if not inst_token:
                logger.error('No installation token available')
                return False
            
            logger.info(f'Posting PR comment to {repo_owner}/{repo_name}#{pr_number}')
            
            url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments'
            
            headers = {
                'Authorization': f'token {inst_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'CICDSECURITY/1.0'
            }
            
            payload = {'body': body}
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 201:
                logger.info(f'PR comment posted successfully to {repo_owner}/{repo_name}#{pr_number}')
                return True
            else:
                logger.error(f'Failed to post PR comment: {response.status_code} - {response.text}')
                return False
    except Exception as e:
        logger.exception(f'Exception posting PR comment: {e}')
        return False


def generate_scan_summary_comment(findings, scan_id=None):
    """
    Generate a brief markdown comment with scan results
    """
    if not findings:
        return "## 🔍 Security Scan Complete\n\n✅ No security issues found!"
    
    lines = [
        "## 🔍 CICDSECURITY Security Scan Results",
        "",
        "| Severity | File | Line | Finding |",
        "|:---------|:-----|:-----|:--------|"
    ]
    
    severity_order = ['critical', 'high', 'medium', 'low', 'warning', 'info', 'unknown']
    
    sorted_findings = sorted(findings, key=lambda x: (
        severity_order.index(x.get('severity', 'unknown').lower()),
        x.get('file', ''),
        x.get('line', 0)
    ))
    
    for f in sorted_findings[:50]:
        severity = f.get('severity', 'unknown').upper()
        file_path = f.get('file', 'N/A')
        if '/' in file_path:
            file_path = file_path.split('/')[-1]
        line = f.get('line', '-')
        finding = f.get('title', 'N/A')
        if len(finding) > 60:
            finding = finding[:57] + '...'
        
        lines.append(f"| {severity} | `{file_path}` | {line} | {finding} |")
    
    if len(findings) > 50:
        lines.append("")
        lines.append(f"*... and {len(findings) - 50} more findings*")
    
    lines.append("")
    lines.append("---")
    if scan_id:
        lines.append(f"*Scan ID: `{scan_id}`* | ")
    lines.append("*Powered by CICDSECURITY*")
    
    return '\n'.join(lines)
