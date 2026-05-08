"""
Repositories Tab Module - Repository management and scanning
Integrates with GitHub API to fetch installed app repositories
"""

import os
import jwt
import time
import requests
import json
import logging
from modules.env_config import env_config

logger = logging.getLogger(__name__)


def get_github_app_token():
    """
    Generate a JWT token for GitHub App authentication
    RSA private key is automatically converted from escaped newlines (\n) to actual newlines by env_config
    
    Returns:
        JWT token for GitHub App API calls
    """
    try:
        logger.debug("Starting get_github_app_token...")
        app_id = env_config.get_setting('GITHUB_APP_ID')
        secret_key = env_config.get_setting('GITHUB_SECRET_KEY')
        
        logger.debug(f"App ID: {app_id}")
        logger.debug(f"Secret Key present: {bool(secret_key)}")
        logger.debug(f"Secret Key length: {len(secret_key) if secret_key else 0}")
        
        # Debug: Show first and last few characters of the key
        if secret_key:
            logger.debug(f"Secret Key starts with: {secret_key[:100]}...")
            logger.debug(f"Secret Key ends with: ...{secret_key[-100:]}")
            logger.debug(f"Secret Key contains newlines: {'\\n' in secret_key}")
            logger.debug(f"Secret Key line count: {len(secret_key.split('\\n'))}")
            logger.debug(f"Reconstructed RSA key successfully (lines: {len(secret_key.split('\\n'))})")
            
            # Try to identify the issue
            lines = secret_key.split('\n')
            logger.debug(f"First line: '{lines[0]}'")
            logger.debug(f"Last line: '{lines[-1]}'")
            if len(lines) > 1:
                logger.debug(f"Second line starts with: '{lines[1][:50]}...'")
        
        if not app_id or not secret_key:
            logger.error("Missing credentials")
            return None
        
        # The secret_key from env_config.py is already in proper PEM format
        # with newlines properly restored from the stored \n escapes
        
        # Create JWT payload
        payload = {
            'iat': int(time.time()),
            'exp': int(time.time()) + 300,  # 5 minutes (GitHub requires short expiration)
            'iss': app_id
        }
        
        logger.debug(f"JWT Payload: {payload}")
        
        # Encode the JWT with the RSA private key
        token = jwt.encode(payload, secret_key, algorithm='RS256')
        logger.debug(f"✓ Generated JWT token successfully (length: {len(token)})")
        return token
    except Exception as e:
        logger.exception(f"Exception in get_github_app_token: {e}")
        return None


def get_installations():
    """
    Fetch all installations of the GitHub App
    
    Returns:
        List of installation IDs
    """
    try:
        logger.debug("Attempting to get GitHub App installations...")
        token = get_github_app_token()
        if not token:
            logger.error("Failed to generate GitHub App token")
            return []
        
        logger.debug(f"Generated token (first 20 chars): {str(token)[:20]}...")
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CICDSECURITY'
        }
        
        response = requests.get(
            'https://api.github.com/app/installations',
            headers=headers,
            timeout=10
        )
        
        logger.debug(f"Installations API response: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Response body: {response.text[:500]}")
        
        if response.status_code == 200:
            installations = response.json()
            ids = [inst.get('id') for inst in installations]
            logger.debug(f"Found installations: {ids}")
            return ids
        else:
            logger.error(f"Failed to fetch installations: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return []
    
    except Exception as e:
        logger.exception(f"Exception in get_installations: {e}")
        return []


def get_installation_token(installation_id):
    """
    Get an access token for a specific installation
    
    Args:
        installation_id: GitHub App installation ID
    
    Returns:
        Access token for the installation
    """
    try:
        logger.debug(f"Getting token for installation {installation_id}...")
        token = get_github_app_token()
        if not token:
            logger.error("Failed to get JWT token")
            return None
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CICDSECURITY'
        }
        
        url = f'https://api.github.com/app/installations/{installation_id}/access_tokens'
        logger.debug(f"POST to {url}")
        
        response = requests.post(
            url,
            headers=headers,
            timeout=10
        )
        
        logger.debug(f"Installation token response status: {response.status_code}")
        logger.debug(f"Installation token response: {response.text[:500]}")
        
        if response.status_code == 201:
            data = response.json()
            token = data.get('token')
            if token:
                logger.debug(f"✓ Got installation token (first 20 chars): {token[:20]}...")
            else:
                logger.error("No token in response")
            return token
        else:
            logger.error(f"Error getting installation token: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
    
    except Exception as e:
        logger.exception(f"Exception in get_installation_token: {e}")
        return None


def get_repositories():
    """
    Fetch all repositories where GitHub App is installed
    
    Returns:
        List of repositories with details
    """
    try:
        logger.debug("Starting get_repositories...")
        installations = get_installations()
        logger.debug(f"Found {len(installations)} installations: {installations}")
        repositories = []
        
        for installation_id in installations:
            logger.debug(f"Processing installation: {installation_id}")
            token = get_installation_token(installation_id)
            if not token:
                logger.error(f"Failed to get token for installation {installation_id}")
                continue
            
            logger.debug(f"Got token for installation {installation_id}")
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Fetch repositories for this installation
            response = requests.get(
                'https://api.github.com/installation/repositories',
                headers=headers,
                timeout=10
            )
            
            logger.debug(f"Repository fetch response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                repos = data.get('repositories', [])
                logger.debug(f"Found {len(repos)} repositories")
                
                for repo in repos:
                    repositories.append({
                        'name': repo.get('name', 'N/A'),
                        'id': repo.get('id'),
                        'branch': repo.get('default_branch', 'main'),
                        'url': repo.get('html_url', ''),
                        'owner': repo.get('owner', {}).get('login', 'N/A')
                    })
            else:
                logger.error(f"Error fetching installation repositories: {response.text}")
        
        logger.debug(f"Returning {len(repositories)} total repositories")
        # Persist a local cache to speed up subsequent UI loads
        try:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_path = os.path.join(root_dir, '.repos_cache.json')
            with open(cache_path, 'w', encoding='utf-8') as cf:
                json.dump(repositories, cf)
        except Exception as e:
            logger.warning(f"Could not write repos cache: {e}")
        return repositories
    
    except Exception as e:
        logger.exception(f"Error fetching repositories: {e}")
        # Try to return cached repositories if available
        try:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_path = os.path.join(root_dir, '.repos_cache.json')
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as cf:
                    cached = json.load(cf)
                    logger.debug(f"Returning {len(cached)} repositories from cache")
                    return cached
        except Exception as e2:
            logger.warning(f"Could not read repos cache: {e2}")

        return []


def get_repository_by_id(repo_id):
    """Get specific repository details"""
    repos = get_repositories()
    for repo in repos:
        if repo['id'] == repo_id:
            return repo
    return None


def get_repository_branches(owner, repo_name):
    """
    Fetch all branches for a specific repository
    
    Args:
        owner: Repository owner (GitHub username or org name)
        repo_name: Repository name
    
    Returns:
        List of branch names, or empty list if error
    """
    try:
        # Get repositories to find the installation for this repo
        installations = get_installations()
        
        for installation_id in installations:
            token = get_installation_token(installation_id)
            if not token:
                logger.debug(f"Failed to get token for installation {installation_id}")
                continue
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Fetch branches for this repo
            url = f'https://api.github.com/repos/{owner}/{repo_name}/branches'
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                branches = response.json()
                branch_names = [branch['name'] for branch in branches]
                logger.debug(f"Found {len(branch_names)} branches for {owner}/{repo_name}: {branch_names}")
                return branch_names
            elif response.status_code == 404:
                logger.debug(f"Repository {owner}/{repo_name} not found in this installation")
                continue
            else:
                logger.warning(f"Error fetching branches for {owner}/{repo_name}: {response.status_code}")
                continue
        
        logger.warning(f"Could not fetch branches for {owner}/{repo_name}")
        return []
    
    except Exception as e:
        logger.exception(f"Error fetching branches for {owner}/{repo_name}: {e}")
        return []


def get_repository_stats():
    """Get aggregate statistics for all repositories based on scan history"""
    repos = get_repositories()
    
    if not repos:
        return {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'warning': 0,
            'avg_coverage': 0,
            'total_issues': 0
        }
    
    # Import here to avoid circular imports
    from modules.history import get_scan_history
    
    try:
        # Get all scan history
        history = get_scan_history()
        
        # Create a mapping of repo names to their latest scan
        repo_scan_map = {}
        for scan in history:
            repo_name = scan.get('repository', '')
            # Only keep the latest scan for each repo
            if repo_name not in repo_scan_map:
                repo_scan_map[repo_name] = scan
        
        total = len(repos)
        passed = 0
        failed = 0
        warning = 0
        total_issues = 0
        
        # Analyze each repo
        for repo in repos:
            repo_name = repo.get('name', '')
            repo_owner = repo.get('owner', '')
            full_repo_name = f"{repo_owner}/{repo_name}" if repo_owner else repo_name
            
            # Check if repo has been scanned
            if full_repo_name in repo_scan_map:
                scan = repo_scan_map[full_repo_name]
                severity = scan.get('severity', {})
                
                critical = severity.get('CRITICAL', 0)
                high = severity.get('HIGH', 0)
                medium = severity.get('MEDIUM', 0)
                total_findings = scan.get('total_findings', 0)
                
                total_issues += total_findings
                
                # Categorize repo status
                if critical > 0:
                    failed += 1  # Critical issues = Failed
                elif high > 0:
                    warning += 1  # High issues = Warning
                else:
                    passed += 1  # No critical/high = Passed
            else:
                # Repo with no scans - consider as "passed" (no issues found)
                passed += 1
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'warning': warning,
            'avg_coverage': 0,  # Not currently tracked
            'total_issues': total_issues
        }
    except Exception as e:
        print(f"Error calculating repository stats: {e}")
        return {
            'total': len(repos),
            'passed': 0,
            'failed': 0,
            'warning': 0,
            'avg_coverage': 0,
            'total_issues': 0
        }
