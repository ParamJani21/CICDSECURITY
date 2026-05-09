"""
PR Scan Handler Module
Handles automated PR scanning with status updates and GitHub integration
"""

import threading
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


def trigger_pr_scan(repo_id, repo_name, repo_owner, repo_url, pr_number, pr_title, 
                    pr_head_sha, scan_types=None, user_id=None):
    """
    Trigger a PR scan in the background
    """
    try:
        from flask import current_app
        from models.database import db, ScanHistory, User
        
        if scan_types is None:
            scan_types = ['sats', 'sbom', 'secret']
        
        scan_id = f"pr-{pr_number}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        if user_id is None:
            admin_user = User.query.filter_by(role='admin').first()
            user_id = admin_user.id if admin_user else 1
        
        scan_history = ScanHistory(
            user_id=user_id,
            scan_id=scan_id,
            repo_id=str(repo_id),
            repo_name=repo_name,
            repo_owner=repo_owner,
            repo_branch=f'pull/{pr_number}/merge',
            is_pr_scan=True,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_head_ref=f'refs/pull/{pr_number}/head',
            scan_types=json.dumps(scan_types),
            scan_status='pending',
            started_at=datetime.utcnow()
        )
        
        db.session.add(scan_history)
        db.session.commit()
        
        logger.info(f'Created ScanHistory record for PR #{pr_number}: {scan_id}')
        
        scan_thread = threading.Thread(
            target=_run_pr_scan_background,
            args=(scan_id, repo_id, repo_name, repo_owner, repo_url, pr_number, 
                    pr_title, pr_head_sha, scan_types, user_id),
            daemon=True
        )
        scan_thread.start()
        
        return {
            'status': 'success',
            'scan_id': scan_id,
            'pr_number': pr_number,
            'message': f'PR scan triggered for PR #{pr_number}'
        }
    
    except Exception as e:
        logger.exception(f'Error triggering PR scan: {e}')
        return {
            'status': 'error',
            'message': f'Failed to trigger PR scan: {str(e)}'
        }


def _run_pr_scan_background(scan_id, repo_id, repo_name, repo_owner, repo_url, 
                            pr_number, pr_title, pr_head_sha, scan_types, user_id):
    """
    Background worker function for PR scanning
    """
    from app import create_app
    from modules.github_status import set_github_status_check
    from modules.control_apis import trigger_scan
    from models.database import db, ScanHistory
    
    start_time = datetime.utcnow()
    app = create_app()
    
    def update_status(state, description):
        try:
            set_github_status_check(
                repo_owner=repo_owner,
                repo_name=repo_name,
                sha=pr_head_sha,
                state=state,
                context='cicdsecurity/scan',
                description=description
            )
        except Exception:
            pass
    
    try:
        with app.app_context():
            scan_history = ScanHistory.query.filter_by(scan_id=scan_id).first()
            if scan_history:
                scan_history.scan_status = 'in_progress'
                db.session.commit()
        
        update_status('pending', 'Scanning for security vulnerabilities...')
        
        with app.app_context():
            pr_url = f'{repo_url.rstrip(".git")}/pull/{pr_number}'
            
            scan_result = trigger_scan(
                repo_id=str(repo_id),
                repo_name=repo_name,
                repo_owner=repo_owner,
                repo_url=pr_url,
                repo_branch='main',
                scan_types=scan_types,
                is_pr_scan=True,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_head_ref=f'refs/pull/{pr_number}/head'
            )
        
        with app.app_context():
            scan_history = ScanHistory.query.filter_by(scan_id=scan_id).first()
            if scan_history:
                duration = (datetime.utcnow() - start_time).total_seconds()
                scan_history.duration_seconds = int(duration)
                scan_history.completed_at = datetime.utcnow()
                
                if scan_result and scan_result.get('status') == 'success':
                    scan_history.scan_status = 'completed'
                    
                    if scan_result.get('findings'):
                        findings = scan_result['findings']
                        summary = {
                            'total_unique': len(findings),
                            'by_severity': {},
                            'by_category': {},
                            'tool_breakdown': scan_result.get('tool_breakdown', {})
                        }
                        
                        for finding in findings:
                            severity = finding.get('severity', 'unknown')
                            category = finding.get('category', 'unknown')
                            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
                            summary['by_category'][category] = summary['by_category'].get(category, 0) + 1
                        
                        scan_history.summary = json.dumps(summary)
                    
                    if scan_result.get('files'):
                        files = scan_result['files']
                        scan_history.findings_file_path = files.get('merged')
                        scan_history.opengrep_file_path = files.get('opengrep')
                        scan_history.truffle_file_path = files.get('truffle')
                        scan_history.trivy_file_path = files.get('trivy')
                    
                    db.session.commit()
                    logger.info(f'Scan {scan_id} completed successfully')
                    
                    summary_data = json.loads(scan_history.summary) if scan_history.summary else {}
                    total_findings = summary_data.get('total_unique', 0)
                    critical_count = summary_data.get('by_severity', {}).get('critical', 0)
                    high_count = summary_data.get('by_severity', {}).get('high', 0)
                    
                    if critical_count > 0:
                        update_status('failure', f'{critical_count} critical, {high_count} high issues')
                    elif high_count > 0:
                        update_status('neutral', f'Found {total_findings} issues')
                    else:
                        update_status('success', f'Found {total_findings} issues')
                
                else:
                    scan_history.scan_status = 'failed'
                    db.session.commit()
                    logger.error(f'Scan {scan_id} failed: {scan_result.get("message") if scan_result else "Unknown error"}')
                    update_status('error', 'Scan failed')

    except Exception as e:
        logger.exception(f'Error in background PR scan: {e}')
        
        with app.app_context():
            scan_history = ScanHistory.query.filter_by(scan_id=scan_id).first()
            if scan_history:
                scan_history.scan_status = 'failed'
                duration = (datetime.utcnow() - start_time).total_seconds()
                scan_history.duration_seconds = int(duration)
                scan_history.completed_at = datetime.utcnow()
                db.session.commit()
            
            update_status('error', f'Scan error: {str(e)[:50]}')
