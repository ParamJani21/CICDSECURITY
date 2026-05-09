"""
GitHub Status Check Integration
Updates PR status checks with scan results
"""

import requests
import logging
from modules.repos import get_github_app_token

logger = logging.getLogger(__name__)


def set_github_status_check(repo_owner, repo_name, sha, state, context, 
                           description, target_url=None):
    """
    Set a GitHub status check on a commit
    
    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        sha: Commit SHA
        state: 'pending', 'success', 'failure', or 'error'
        context: Status context (e.g., 'cicdsecurity/scan')
        description: Human-readable description
        target_url: Link to details (optional)
    
    Returns:
        bool: True if successful
    """
    try:
        # Validate state
        valid_states = ['pending', 'success', 'failure', 'error']
        if state not in valid_states:
            logger.warning(f'Invalid GitHub status state: {state}')
            return False
        
        # Get GitHub token
        token = get_github_app_token()
        if not token:
            logger.warning('No GitHub app token available for status check')
            return False
        
        # Build status check payload
        payload = {
            'state': state,
            'context': context,
            'description': description
        }
        
        if target_url:
            payload['target_url'] = target_url
        
        # GitHub API endpoint
        url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/statuses/{sha}'
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CICDSECURITY/1.0'
        }
        
        # Send status check
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 201:
            logger.info(f'GitHub status check set: {repo_owner}/{repo_name}@{sha[:7]} -> {state}')
            return True
        else:
            logger.warning(f'Failed to set GitHub status: {response.status_code} {response.text}')
            return False
    
    except Exception as e:
        logger.exception(f'Error setting GitHub status check: {e}')
        return False


def create_github_check_run(repo_owner, repo_name, head_sha, name='CICDSECURITY Scan', 
                           status='queued', conclusion=None, details_url=None):
    """
    Create a GitHub Check Run (more detailed than status checks)
    Supports more features like annotations, output, etc.
    
    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        head_sha: Commit SHA
        name: Check run name
        status: 'queued', 'in_progress', 'completed'
        conclusion: 'success', 'failure', 'neutral', 'cancelled', 'skipped', 'timed_out'
        details_url: URL for more details
    
    Returns:
        dict: Check run data if successful, None otherwise
    """
    try:
        # Get GitHub token
        token = get_github_app_token()
        if not token:
            logger.warning('No GitHub app token available for check run')
            return None
        
        # Build payload
        payload = {
            'name': name,
            'head_sha': head_sha,
            'status': status
        }
        
        if conclusion:
            payload['conclusion'] = conclusion
        
        if details_url:
            payload['details_url'] = details_url
        
        # GitHub API endpoint
        url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/check-runs'
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.checks-preview+json',
            'User-Agent': 'CICDSECURITY/1.0'
        }
        
        # Send check run creation
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 201:
            check_run = response.json()
            logger.info(f'GitHub check run created: {repo_owner}/{repo_name}@{head_sha[:7]} -> {name}')
            return check_run
        else:
            logger.warning(f'Failed to create GitHub check run: {response.status_code} {response.text}')
            return None
    
    except Exception as e:
        logger.exception(f'Error creating GitHub check run: {e}')
        return None


def update_github_check_run(repo_owner, repo_name, check_run_id, status='in_progress', 
                           conclusion=None, details_url=None, output=None):
    """
    Update an existing GitHub Check Run
    
    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        check_run_id: Check run ID
        status: 'queued', 'in_progress', 'completed'
        conclusion: 'success', 'failure', 'neutral', 'cancelled', 'skipped', 'timed_out'
        details_url: URL for more details
        output: dict with 'title', 'summary', 'text', 'annotations'
    
    Returns:
        bool: True if successful
    """
    try:
        # Get GitHub token
        token = get_github_app_token()
        if not token:
            logger.warning('No GitHub app token available for check run update')
            return False
        
        # Build payload
        payload = {
            'status': status
        }
        
        if conclusion:
            payload['conclusion'] = conclusion
        
        if details_url:
            payload['details_url'] = details_url
        
        if output:
            payload['output'] = output
        
        # GitHub API endpoint
        url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/check-runs/{check_run_id}'
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.checks-preview+json',
            'User-Agent': 'CICDSECURITY/1.0'
        }
        
        # Send check run update
        response = requests.patch(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info(f'GitHub check run updated: {repo_owner}/{repo_name}#{check_run_id} -> {status}')
            return True
        else:
            logger.warning(f'Failed to update GitHub check run: {response.status_code} {response.text}')
            return False
    
    except Exception as e:
        logger.exception(f'Error updating GitHub check run: {e}')
        return False
