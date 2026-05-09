"""
PR Scan Handler Module
Handles automated PR scanning with status updates and GitHub integration
"""

import threading
import logging
import json
from datetime import datetime
from modules.control_apis import trigger_scan
from modules.github_status import set_github_status_check
from models.database import db, ScanHistory, User
from flask import current_app

logger = logging.getLogger(__name__)


def trigger_pr_scan(repo_id, repo_name, repo_owner, repo_url, pr_number, pr_title, 
                    pr_head_sha, scan_types=None, user_id=None):
    """
    Trigger a PR scan in the background
    
    This function:
    1. Creates a ScanHistory record with is_pr_scan=True and status=pending
    2. Starts a background thread for the actual scan
    3. Updates GitHub status checks as scan progresses
    
    Args:
        repo_id: Repository ID
        repo_name: Repository name
        repo_owner: Repository owner
        repo_url: Repository URL
        pr_number: Pull request number
        pr_title: Pull request title
        pr_head_sha: PR head commit SHA (for status checks)
        scan_types: List of scan types to run (default: ['sats', 'sbom', 'secret'])
        user_id: User ID who triggered the scan (optional)
    
    Returns:
        dict: {status, scan_id, message}
    """
    try:
        if scan_types is None:
            scan_types = ['sats', 'sbom', 'secret']
        
        # Generate scan ID
        scan_id = f"pr-{pr_number}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        # Get default user if not provided
        if user_id is None:
            admin_user = User.query.filter_by(role='admin').first()
            user_id = admin_user.id if admin_user else 1
        
        # Create ScanHistory record with pending status
        scan_history = ScanHistory(
            user_id=user_id,
            scan_id=scan_id,
            repo_id=str(repo_id),
            repo_name=repo_name,
            repo_owner=repo_owner,
            repo_branch=f'pull/{pr_number}/merge',  # GitHub's merge commit ref
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
        
        # Set GitHub status to pending
        try:
            set_github_status_check(
                repo_owner=repo_owner,
                repo_name=repo_name,
                sha=pr_head_sha,
                state='pending',
                context='cicdsecurity/scan',
                description='Security scan in progress...'
            )
            logger.info(f'Set GitHub status to pending for {repo_owner}/{repo_name}@{pr_head_sha}')
        except Exception as e:
            logger.warning(f'Failed to set GitHub status: {e}')
        
        # Start background scan thread
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
    
    Updates ScanHistory status as scanning progresses:
    - pending → in_progress (when scan starts)
    - in_progress → completed (when scan finishes)
    - in_progress → failed (on error)
    
    Args:
        All PR scan parameters
    """
    start_time = datetime.utcnow()
    scan_history = None
    
    try:
        # Update status to in_progress
        with current_app.app_context():
            scan_history = ScanHistory.query.filter_by(scan_id=scan_id).first()
            if scan_history:
                scan_history.scan_status = 'in_progress'
                db.session.commit()
                logger.info(f'Updated scan {scan_id} to in_progress')
        
        # Set GitHub status to in_progress
        try:
            set_github_status_check(
                repo_owner=repo_owner,
                repo_name=repo_name,
                sha=pr_head_sha,
                state='pending',
                context='cicdsecurity/scan',
                description='Scanning for security vulnerabilities...'
            )
        except Exception as e:
            logger.warning(f'Failed to update GitHub status: {e}')
        
        # Run the actual scan (uses internal branch ref for PR merge commit)
        # PR merge commit URL: https://github.com/owner/repo/pull/123/merge
        pr_merge_url = f'{repo_url.rstrip(".git")}/pull/{pr_number}/merge'
        
        scan_result = trigger_scan(
            repo_id=str(repo_id),
            repo_name=repo_name,
            repo_owner=repo_owner,
            repo_url=pr_merge_url,
            repo_branch=f'pull/{pr_number}/merge',
            scan_types=scan_types,
            is_pr_scan=True,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_head_ref=f'refs/pull/{pr_number}/head'
        )
        
        # Update ScanHistory with results
        with current_app.app_context():
            scan_history = ScanHistory.query.filter_by(scan_id=scan_id).first()
            if scan_history:
                duration = (datetime.utcnow() - start_time).total_seconds()
                scan_history.duration_seconds = int(duration)
                scan_history.completed_at = datetime.utcnow()
                
                if scan_result.get('status') == 'success':
                    scan_history.scan_status = 'completed'
                    
                    # Extract findings summary
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
                    
                    # Store file paths
                    if scan_result.get('files'):
                        files = scan_result['files']
                        scan_history.findings_file_path = files.get('merged')
                        scan_history.opengrep_file_path = files.get('opengrep')
                        scan_history.truffle_file_path = files.get('truffle')
                        scan_history.trivy_file_path = files.get('trivy')
                    
                    db.session.commit()
                    logger.info(f'Scan {scan_id} completed successfully')
                    
                    # Set GitHub status to success
                    summary_data = json.loads(scan_history.summary) if scan_history.summary else {}
                    total_findings = summary_data.get('total_unique', 0)
                    critical_count = summary_data.get('by_severity', {}).get('critical', 0)
                    high_count = summary_data.get('by_severity', {}).get('high', 0)
                    
                    status_state = 'failure' if critical_count > 0 else ('neutral' if high_count > 0 else 'success')
                    status_description = f'Found {total_findings} issues'
                    if critical_count > 0:
                        status_description = f'{critical_count} critical, {high_count} high issues'
                    
                    try:
                        set_github_status_check(
                            repo_owner=repo_owner,
                            repo_name=repo_name,
                            sha=pr_head_sha,
                            state=status_state,
                            context='cicdsecurity/scan',
                            description=status_description,
                            target_url=f'/api/history/{scan_id}'
                        )
                    except Exception as e:
                        logger.warning(f'Failed to set final GitHub status: {e}')
                
                else:
                    # Scan failed
                    scan_history.scan_status = 'failed'
                    db.session.commit()
                    logger.error(f'Scan {scan_id} failed: {scan_result.get("message")}')
                    
                    # Set GitHub status to failure
                    try:
                        set_github_status_check(
                            repo_owner=repo_owner,
                            repo_name=repo_name,
                            sha=pr_head_sha,
                            state='error',
                            context='cicdsecurity/scan',
                            description='Scan failed'
                        )
                    except Exception as e:
                        logger.warning(f'Failed to set GitHub error status: {e}')
    
    except Exception as e:
        logger.exception(f'Error in background PR scan: {e}')
        
        # Update scan status to failed
        with current_app.app_context():
            scan_history = ScanHistory.query.filter_by(scan_id=scan_id).first()
            if scan_history:
                scan_history.scan_status = 'failed'
                duration = (datetime.utcnow() - start_time).total_seconds()
                scan_history.duration_seconds = int(duration)
                scan_history.completed_at = datetime.utcnow()
                db.session.commit()
            
            # Set GitHub status to error
            try:
                set_github_status_check(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    sha=pr_head_sha,
                    state='error',
                    context='cicdsecurity/scan',
                    description=f'Scan error: {str(e)[:50]}'
                )
            except Exception as status_e:
                logger.warning(f'Failed to set GitHub error status: {status_e}')
