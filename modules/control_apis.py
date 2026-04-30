"""
Control APIs Module - Repository Cloning & Scanning Control
Handles Git operations using GitHub App authentication and WSL execution
"""

import os
import subprocess
import logging
import json
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from modules.repos import get_installation_token, get_installations, get_repositories

logger = logging.getLogger(__name__)


def get_tmp_directory():
    """
    Get the /tmp directory path in CICDSECURITY root
    
    Returns:
        Path to /tmp directory
    """
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tmp_dir = os.path.join(root_dir, 'tmp')
        
        # Ensure tmp directory exists
        os.makedirs(tmp_dir, exist_ok=True)
        logger.info(f'✓ TMP directory ready: {tmp_dir}')
        return tmp_dir
    except Exception as e:
        logger.exception(f'Error creating tmp directory: {e}')
        return None


def get_wsl_path(windows_path):
    """
    Convert Windows path to WSL path
    Example: C:\\Users\\user\\project -> /mnt/c/Users/user/project
    
    Args:
        windows_path: Windows file path
    
    Returns:
        WSL path string
    """
    try:
        # Normalize the path
        windows_path = os.path.normpath(windows_path)
        
        # If path contains drive letter (C:, D:, etc)
        if len(windows_path) > 1 and windows_path[1] == ':':
            drive = windows_path[0].lower()
            rest = windows_path[2:].replace('\\', '/')
            wsl_path = f'/mnt/{drive}{rest}'
            logger.debug(f'Converted Windows path to WSL: {windows_path} -> {wsl_path}')
            return wsl_path
        else:
            # Already a Unix-like path
            logger.debug(f'Path is already Unix-like: {windows_path}')
            return windows_path
    except Exception as e:
        logger.exception(f'Error converting path to WSL format: {e}')
        return windows_path


def run_wsl_command(command, cwd=None, timeout=300):
    """
    Execute a command - works on Linux (direct) or Windows+WSL
    
    Args:
        command: Command string to execute
        cwd: Current working directory
        timeout: Command timeout in seconds (default: 300 for git clone, can be 600 for scans)
    
    Returns:
        Tuple of (success: bool, stdout: str, stderr: str)
    """
    try:
        logger.info(f'[WSL] Executing command: {command}')
        if cwd:
            logger.info(f'[WSL] Working directory: {cwd}')
        
        # Check if WSL is available, otherwise run directly on Linux
        wsl_available = False
        try:
            result = subprocess.run(
                ['which', 'wsl'],
                capture_output=True,
                text=True,
                timeout=5
            )
            wsl_available = result.returncode == 0
        except Exception:
            pass
        
        if wsl_available:
            # Use WSL on Windows
            cmd_list = ['wsl', '-e', 'bash', '-c', command]
            logger.debug(f'[WSL] Running via WSL: {cmd_list}')
        else:
            # Run directly on Linux (no WSL needed)
            cmd_list = ['bash', '-c', command]
            logger.debug(f'[WSL] Running directly (no WSL): {cmd_list}')
        
        # Execute the command
        result = subprocess.run(
            cmd_list,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        success = result.returncode == 0
        stdout = result.stdout
        stderr = result.stderr
        
        if success:
            logger.info(f'[WSL] ✓ Command succeeded (exit code: {result.returncode})')
            logger.debug(f'[WSL] stdout: {stdout[:500]}')
        else:
            logger.error(f'[WSL] ✗ Command failed (exit code: {result.returncode})')
            logger.error(f'[WSL] stderr: {stderr[:500]}')
        
        return success, stdout, stderr
    
    except subprocess.TimeoutExpired:
        logger.error('[WSL] ✗ Command timed out (5 minutes)')
        return False, '', 'Command timed out after 300 seconds'
    except Exception as e:
        logger.exception(f'[WSL] Exception executing command: {e}')
        return False, '', str(e)


def get_repo_installation_id(repo_owner, repo_name):
    """
    Find the installation ID for a specific repository
    
    Args:
        repo_owner: Repository owner/organization
        repo_name: Repository name
    
    Returns:
        Installation ID or None
    """
    try:
        logger.info(f'Finding installation ID for {repo_owner}/{repo_name}...')
        
        repos = get_repositories()
        logger.debug(f'Fetched {len(repos)} total repositories')
        
        for repo in repos:
            if repo.get('owner') == repo_owner and repo.get('name') == repo_name:
                # We need to find the right installation
                # For now, we'll use the first installation and hope it works
                # In a real scenario, we'd track which installation manages which repo
                installations = get_installations()
                if installations:
                    installation_id = installations[0]
                    logger.info(f'✓ Found installation ID: {installation_id}')
                    return installation_id
        
        # If exact match not found, try first installation
        installations = get_installations()
        if installations:
            logger.warning(f'Repository not found in exact match, using first installation')
            return installations[0]
        
        logger.error(f'No installations found for {repo_owner}/{repo_name}')
        return None
    
    except Exception as e:
        logger.exception(f'Error finding installation ID: {e}')
        return None


def cleanup_directory_force(path, retries=3):
    """
    Forcefully remove a directory, handling Windows file locks
    
    Args:
        path: Directory path to remove
        retries: Number of retry attempts
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.debug(f'[Cleanup] Attempting to forcefully remove: {path}')
        
        for attempt in range(retries):
            try:
                # Try using shutil first
                shutil.rmtree(path)
                logger.info(f'[Cleanup] ✓ Removed directory (attempt {attempt + 1})')
                return True
            except PermissionError as e:
                logger.warning(f'[Cleanup] Permission denied on attempt {attempt + 1}, retrying...')
                
                if attempt < retries - 1:
                    import time
                    time.sleep(0.5)  # Short delay before retry
                    continue
                
                # Last attempt: try using Windows command
                try:
                    logger.info('[Cleanup] Attempting Windows rmdir command...')
                    result = subprocess.run(
                        ['cmd', '/c', 'rmdir', '/s', '/q', path],
                        capture_output=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        logger.info('[Cleanup] ✓ Removed directory using Windows command')
                        return True
                except Exception as e2:
                    logger.warning(f'[Cleanup] Windows command also failed: {e2}')
                
                raise
    
    except Exception as e:
        logger.error(f'[Cleanup] Failed to remove directory: {e}')
        return False


def clone_repository(repo_id, repo_name, repo_owner, repo_url, repo_branch='main'):
    """
    Clone a GitHub repository using GitHub App authentication
    Runs git clone in WSL and stores in /tmp directory
    
    Args:
        repo_id: Repository ID
        repo_name: Repository name
        repo_owner: Repository owner
        repo_url: Repository HTTPS URL
        repo_branch: Branch to clone (default: main)
    
    Returns:
        Dict with status and details
    """
    try:
        logger.info('=' * 80)
        logger.info(f'🔍 CLONE REQUEST: {repo_owner}/{repo_name} (ID: {repo_id})')
        logger.info(f'   Branch: {repo_branch}')
        logger.info(f'   URL: {repo_url}')
        logger.info('=' * 80)
        
        # Get tmp directory
        tmp_dir = get_tmp_directory()
        if not tmp_dir:
            logger.error('Failed to get tmp directory')
            return {
                'status': 'error',
                'message': 'Failed to initialize tmp directory',
                'repo_id': repo_id,
                'repo_name': repo_name
            }
        
        # Create repo-specific directory
        repo_dir = os.path.join(tmp_dir, repo_owner, repo_name)
        logger.info(f'📁 Clone destination: {repo_dir}')
        
        # Get installation token for authentication
        logger.info('[Auth] Getting GitHub App installation token...')
        installation_id = get_repo_installation_id(repo_owner, repo_name)
        
        if not installation_id:
            logger.error('[Auth] Failed to get installation ID')
            return {
                'status': 'error',
                'message': 'Failed to get GitHub App installation ID',
                'repo_id': repo_id,
                'repo_name': repo_name
            }
        
        logger.debug(f'[Auth] Installation ID: {installation_id}')
        
        installation_token = get_installation_token(installation_id)
        if not installation_token:
            logger.error('[Auth] Failed to get installation token')
            return {
                'status': 'error',
                'message': 'Failed to get GitHub App installation token',
                'repo_id': repo_id,
                'repo_name': repo_name
            }
        
        logger.info(f'[Auth] ✓ Got installation token (first 20 chars): {installation_token[:20]}...')
        
        # Construct authenticated URL with token
        # Format: https://x-access-token:TOKEN@github.com/owner/repo.git
        if '@' in repo_url:
            # URL might already have auth, strip it
            repo_url = repo_url.split('@')[1]
            if repo_url.startswith('//'):
                repo_url = repo_url[2:]
        
        authenticated_url = f'https://x-access-token:{installation_token}@github.com/{repo_owner}/{repo_name}.git'
        logger.debug(f'[Auth] Authenticated URL prepared (token hidden)')
        
        # Convert paths for WSL
        wsl_repo_dir = get_wsl_path(repo_dir)
        logger.info(f'[WSL] WSL path: {wsl_repo_dir}')
        
        # Clean up existing clone if it exists
        logger.info('[Clone] Checking for existing clone...')
        if os.path.exists(repo_dir):
            logger.warning(f'[Clone] Directory already exists, cleaning up: {repo_dir}')
            if not cleanup_directory_force(repo_dir):
                logger.error('[Clone] Failed to clean existing directory')
                return {
                    'status': 'error',
                    'message': f'Failed to clean existing repository - directory locked or in use',
                    'repo_id': repo_id,
                    'repo_name': repo_name
                }
            logger.info('[Clone] ✓ Cleaned up existing directory')
        
        # Prepare parent directory
        os.makedirs(repo_dir, exist_ok=True)
        wsl_parent_dir = get_wsl_path(os.path.join(tmp_dir, repo_owner))
        logger.info(f'[Clone] Creating parent directory: {wsl_parent_dir}')
        mkdir_cmd = f'mkdir -p {wsl_parent_dir}'
        success, stdout, stderr = run_wsl_command(mkdir_cmd)
        if not success:
            logger.error('[Clone] Failed to create parent directory')
            return {
                'status': 'error',
                'message': f'Failed to create directory: {stderr}',
                'repo_id': repo_id,
                'repo_name': repo_name
            }
        
        logger.info('[Clone] ✓ Parent directory ready')
        
        # Clone the repository
        logger.info(f'[Clone] Starting git clone...')
        logger.info(f'[Clone] Cloning from: {repo_owner}/{repo_name}')
        logger.info(f'[Clone] Branch: {repo_branch}')
        
        clone_cmd = (
            f'git clone '
            f'--branch {repo_branch} '
            f'--depth 1 '
            f'--single-branch '
            f'{authenticated_url} '
            f'{wsl_repo_dir}'
        )
        
        logger.debug(f'[Clone] Git command (token hidden): '
                    f'git clone --branch {repo_branch} --depth 1 --single-branch '
                    f'https://x-access-token:***@github.com/{repo_owner}/{repo_name}.git {wsl_repo_dir}')
        
        success, stdout, stderr = run_wsl_command(clone_cmd)
        
        if not success:
            logger.error('[Clone] ✗ Git clone failed')
            logger.error(f'[Clone] Error: {stderr}')
            return {
                'status': 'error',
                'message': f'Git clone failed: {stderr}',
                'repo_id': repo_id,
                'repo_name': repo_name,
                'error_details': stderr[:500]
            }
        
        logger.info('[Clone] ✓ Git clone completed successfully')
        logger.info(f'[Clone] stdout: {stdout[:300]}')
        
        # Verify clone
        logger.info('[Clone] Verifying cloned repository...')
        verify_cmd = f'ls -la {wsl_repo_dir}'
        success, stdout, stderr = run_wsl_command(verify_cmd)
        
        if success:
            logger.info('[Clone] ✓ Repository verified')
            logger.info(f'[Clone] Contents: {stdout[:300]}')
        else:
            logger.warning('[Clone] ⚠ Failed to verify repository')
        
        # Get clone details
        logger.info('[Clone] Gathering clone details...')
        details_cmd = f'cd {wsl_repo_dir} && git log -1 --format="%H %s %ai"'
        success, commit_info, _ = run_wsl_command(details_cmd)
        
        clone_info = {
            'repo_id': repo_id,
            'repo_name': repo_name,
            'repo_owner': repo_owner,
            'repo_url': repo_url,
            'branch': repo_branch,
            'clone_path': repo_dir,
            'wsl_path': wsl_repo_dir,
            'cloned_at': datetime.now().isoformat(),
            'commit_info': commit_info.strip() if success else 'Unknown'
        }
        
        logger.info('=' * 80)
        logger.info(f'✅ CLONE SUCCESSFUL: {repo_owner}/{repo_name}')
        logger.info(f'   Path: {repo_dir}')
        logger.info(f'   Branch: {repo_branch}')
        logger.info(f'   Commit: {clone_info["commit_info"][:50]}...' if len(clone_info.get('commit_info', '')) > 50 else f'   Commit: {clone_info.get("commit_info")}')
        logger.info('=' * 80)
        
        return {
            'status': 'success',
            'message': f'Successfully cloned {repo_owner}/{repo_name}',
            'repo_id': repo_id,
            'repo_name': repo_name,
            'repo_owner': repo_owner,
            'clone_details': clone_info
        }
    
    except Exception as e:
        logger.exception(f'Exception in clone_repository: {e}')
        return {
            'status': 'error',
            'message': f'Exception during clone: {str(e)}',
            'repo_id': repo_id,
            'repo_name': repo_name,
            'error_details': str(e)
        }


def get_cloned_repos():
    """
    Get list of all cloned repositories in /tmp
    
    Returns:
        List of cloned repository info
    """
    try:
        logger.info('[List] Getting list of cloned repositories...')
        
        tmp_dir = get_tmp_directory()
        if not tmp_dir:
            logger.error('[List] Failed to get tmp directory')
            return []
        
        cloned_repos = []
        
        if not os.path.exists(tmp_dir):
            logger.warning(f'[List] Tmp directory does not exist: {tmp_dir}')
            return []
        
        # Walk through directory structure: /tmp/owner/repo_name
        for owner in os.listdir(tmp_dir):
            owner_path = os.path.join(tmp_dir, owner)
            
            if not os.path.isdir(owner_path):
                continue
            
            logger.debug(f'[List] Scanning owner: {owner}')
            
            for repo_name in os.listdir(owner_path):
                repo_path = os.path.join(owner_path, repo_name)
                
                if not os.path.isdir(repo_path):
                    continue
                
                try:
                    # Get git info if possible
                    git_dir = os.path.join(repo_path, '.git')
                    is_git = os.path.exists(git_dir)
                    
                    # Get directory size
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(repo_path):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            if os.path.exists(fp):
                                total_size += os.path.getsize(fp)
                    
                    # Get commit info
                    commit_info = 'Unknown'
                    if is_git:
                        try:
                            result = subprocess.run(
                                ['git', '-C', repo_path, 'log', '-1', '--format=%H %s'],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                commit_info = result.stdout.strip()
                        except Exception as e:
                            logger.debug(f'[List] Failed to get git info for {owner}/{repo_name}: {e}')
                    
                    repo_info = {
                        'owner': owner,
                        'name': repo_name,
                        'path': repo_path,
                        'is_git': is_git,
                        'size_bytes': total_size,
                        'size_mb': round(total_size / (1024 * 1024), 2),
                        'commit': commit_info,
                        'created_at': datetime.fromtimestamp(
                            os.path.getctime(repo_path)
                        ).isoformat()
                    }
                    
                    cloned_repos.append(repo_info)
                    logger.debug(f'[List] Found cloned repo: {owner}/{repo_name} ({repo_info["size_mb"]}MB)')
                
                except Exception as e:
                    logger.warning(f'[List] Error processing {owner}/{repo_name}: {e}')
                    continue
        
        logger.info(f'[List] ✓ Found {len(cloned_repos)} cloned repositories')
        return cloned_repos
    
    except Exception as e:
        logger.exception(f'[List] Exception in get_cloned_repos: {e}')
        return []


def cleanup_cloned_repo(repo_owner, repo_name):
    """
    Remove a cloned repository from /tmp
    
    Args:
        repo_owner: Repository owner
        repo_name: Repository name
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info('=' * 80)
        logger.info(f'🗑️  CLEANUP REQUEST: {repo_owner}/{repo_name}')
        logger.info('=' * 80)
        
        tmp_dir = get_tmp_directory()
        if not tmp_dir:
            logger.error('[Cleanup] Failed to get tmp directory')
            return False
        
        repo_path = os.path.join(tmp_dir, repo_owner, repo_name)
        logger.info(f'[Cleanup] Target path: {repo_path}')
        
        if not os.path.exists(repo_path):
            logger.warning(f'[Cleanup] ⚠ Path does not exist: {repo_path}')
            return False
        
        if not os.path.isdir(repo_path):
            logger.error(f'[Cleanup] ✗ Path is not a directory: {repo_path}')
            return False
        
        try:
            logger.info(f'[Cleanup] Removing directory...')
            
            # Define error handler for Windows file permission issues on git files
            def handle_remove_error(func, path, exc_info):
                """Error handler for shutil.rmtree that handles Windows file locks"""
                import stat
                exc_type, exc_val, exc_tb = exc_info
                if exc_type and (exc_type == PermissionError or exc_type == OSError):
                    try:
                        logger.debug(f'[Cleanup] Fixing permissions on: {path}')
                        # Make file writable and try again
                        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                        func(path)
                        logger.debug(f'[Cleanup] Successfully deleted after chmod: {path}')
                    except Exception as e:
                        logger.warning(f'[Cleanup] Could not fix permissions on {path}: {e}')
                else:
                    logger.error(f'[Cleanup] Unexpected error removing {path}: {exc_val}')
            
            # Remove directory with error handler for permission issues
            shutil.rmtree(repo_path, onerror=handle_remove_error)
            logger.info(f'[Cleanup] ✓ Successfully removed: {repo_path}')
            
            # Try to clean up empty owner directory
            owner_path = os.path.join(tmp_dir, repo_owner)
            if os.path.exists(owner_path) and len(os.listdir(owner_path)) == 0:
                logger.info(f'[Cleanup] Removing empty owner directory: {owner_path}')
                os.rmdir(owner_path)
                logger.info(f'[Cleanup] ✓ Removed empty owner directory')
            
            logger.info('=' * 80)
            logger.info(f'✅ CLEANUP SUCCESSFUL: {repo_owner}/{repo_name}')
            logger.info('=' * 80)
            return True
        
        except Exception as e:
            logger.exception(f'[Cleanup] Exception removing directory: {e}')
            return False
    
    except Exception as e:
        logger.exception(f'[Cleanup] Exception in cleanup_cloned_repo: {e}')
        return False


def get_logs_directory():
    """
    Get the logs directory path
    
    Returns:
        Path to logs directory
    """
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(root_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir
    except Exception as e:
        logger.exception(f'Error getting logs directory: {e}')
        return None


def generate_scan_id():
    """
    Generate a unique scan ID
    
    Returns:
        Unique scan ID string
    """
    return str(uuid.uuid4())


def run_opengrep_scan(repo_path, scan_id):
    """
    Run OpenGrep scan on repository using WSL
    
    Args:
        repo_path: Path to cloned repository
        scan_id: Unique scan identifier
    
    Returns:
        Tuple of (success: bool, scan_results: dict)
    """
    try:
        logger.info('=' * 80)
        logger.info(f'🔍 OPENGREP SCAN: {scan_id}')
        logger.info(f'   Repository: {repo_path}')
        logger.info('=' * 80)
        
        # Convert path for WSL
        wsl_repo_path = get_wsl_path(repo_path)
        logger.info(f'[OpenGrep] WSL path: {wsl_repo_path}')
        
        # Detect whether `opengrep` or `semgrep` is available in WSL (prefer opengrep)
        logger.info('[OpenGrep] Checking for opengrep/semgrep availability in WSL...')
        check_tool_cmd = 'command -v opengrep || command -v semgrep || true'
        success, tool_path, stderr = run_wsl_command(check_tool_cmd)

        tool_name = None
        if success and tool_path and tool_path.strip():
            # `command -v` returns the absolute path; use the basename as command
            tool_path = tool_path.strip().splitlines()[0]
            tool_name = os.path.basename(tool_path)
            logger.info(f'[OpenGrep] ✓ Found tool: {tool_name} at {tool_path}')
        else:
            logger.error('[OpenGrep] ✗ Neither opengrep nor semgrep found in WSL PATH')
            return False, {
                'error': 'opengrep/semgrep not found',
                'message': 'Please install opengrep or semgrep in WSL and ensure it is in PATH',
                'scan_id': scan_id
            }

        # Run scan with the discovered tool
        logger.info('[OpenGrep] Starting scan...')
        logger.info('[OpenGrep] Scanning all file types in repository...')

        # Build scan command - use auto or scan without specific configs
        opengrep_cmd = (
            f'cd {wsl_repo_path} && '
            f"{tool_name} --json "
            f'--config=auto '
            f'--quiet '
            f'. 2>&1 || true'
        )

        logger.debug(f'[OpenGrep] Command: {opengrep_cmd}')
        
        success, stdout, stderr = run_wsl_command(opengrep_cmd, timeout=600)
        
        if not success and not stdout:
            logger.warning(f'[OpenGrep] ⚠ Scan command had issues, but continuing...')
            logger.warning(f'[OpenGrep] stderr: {stderr[:500]}')
        
        logger.info('[OpenGrep] ✓ Scan completed')

        # Build base results structure
        scan_results = {
            'scan_id': scan_id,
            'timestamp': datetime.now().isoformat(),
            'repository': os.path.basename(repo_path),
            'raw_output': stdout,
            'status': 'completed'
        }

        # Parse JSON output robustly: try full-document parse, then line-based fallback
        findings = []
        try:
            if stdout and stdout.strip():
                try:
                    parsed = json.loads(stdout)
                    # semgrep/opengrep may return a dict with 'results' or a list
                    if isinstance(parsed, dict) and 'results' in parsed:
                        findings = parsed.get('results', []) or []
                    elif isinstance(parsed, list):
                        findings = parsed
                    else:
                        # Unexpected top-level structure; try line-wise parsing next
                        findings = []
                except Exception:
                    # Fallback: attempt to decode JSON objects from individual lines
                    json_lines = []
                    for line in stdout.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            json_lines.append(obj)
                        except Exception:
                            continue
                    findings = json_lines
            else:
                findings = []
        except Exception as e:
            logger.warning(f'[OpenGrep] Error parsing JSON output: {e}')
            findings = []

        scan_results['results'] = findings
        scan_results['findings_count'] = len(findings)

        if findings:
            logger.info(f'[OpenGrep] ✓ Found {len(findings)} potential issues')
        else:
            logger.info('[OpenGrep] ✓ No issues found')

        logger.info('=' * 80)
        logger.info(f'✅ OPENGREP SCAN COMPLETE: {scan_id}')
        logger.info(f'   Findings: {scan_results.get("findings_count", 0)}')
        logger.info('=' * 80)

        return True, scan_results
    
    except Exception as e:
        logger.exception(f'Exception in run_opengrep_scan: {e}')
        return False, {
            'error': str(e),
            'scan_id': scan_id,
            'status': 'failed'
        }


def run_truffle_scan(repo_path, scan_id):
    """
    Run TruffleHog secret scanning on repository using WSL
    """
    try:
        logger.info('=' * 80)
        logger.info(f'🔍 TRUFFLEHOG SCAN (SECRETS): {scan_id}')
        logger.info(f'   Repository: {repo_path}')
        logger.info('=' * 80)
        
        wsl_repo_path = get_wsl_path(repo_path)
        logger.info(f'[TruffleHog] WSL path: {wsl_repo_path}')
        
        # Check if TruffleHog is available
        logger.info('[TruffleHog] Checking for trufflehog availability...')
        check_cmd = 'command -v trufflehog || true'
        success, tool_path, stderr = run_wsl_command(check_cmd)
        
        if not (success and tool_path and tool_path.strip()):
            logger.warning('[TruffleHog] ✗ TruffleHog not found - skipping')
            return True, {
                'scan_id': scan_id,
                'timestamp': datetime.now().isoformat(),
                'repository': os.path.basename(repo_path),
                'status': 'skipped',
                'message': 'TruffleHog not installed',
                'results': [],
                'findings_count': 0
            }
        
        logger.info(f'[TruffleHog] ✓ Found at {tool_path.strip()}')
        logger.info('[TruffleHog] Starting secret scanning...')
        
        trufflehog_cmd = (
            f'cd {wsl_repo_path} && '
            f'trufflehog filesystem . '
            f'--json '
            f'--no-update '
            f'2>&1 || true'
        )
        
        success, stdout, stderr = run_wsl_command(trufflehog_cmd, timeout=600)
        logger.info('[TruffleHog] ✓ Scan completed')
        
        # Parse JSON output
        secrets = []
        try:
            if stdout and stdout.strip():
                json_lines = []
                for line in stdout.splitlines():
                    line = line.strip()
                    if line and line.startswith('{'):
                        try:
                            obj = json.loads(line)
                            if 'DetectorType' in obj:
                                json_lines.append(obj)
                        except:
                            continue
                secrets = json_lines
        except Exception as e:
            logger.warning(f'[TruffleHog] Error parsing output: {e}')
        
        scan_results = {
            'scan_id': scan_id,
            'timestamp': datetime.now().isoformat(),
            'repository': os.path.basename(repo_path),
            'raw_output': stdout,
            'status': 'completed',
            'results': secrets,
            'findings_count': len(secrets)
        }
        
        logger.info(f'[TruffleHog] ✓ Found {len(secrets)} secrets')
        logger.info('=' * 80)
        
        return True, scan_results
    
    except Exception as e:
        logger.exception(f'Exception in run_truffle_scan: {e}')
        return False, {
            'error': str(e),
            'scan_id': scan_id,
            'status': 'error',
            'results': [],
            'findings_count': 0
        }


def run_trivy_scan(repo_path, scan_id):
    """
    Run Trivy security scan on repository using WSL
    
    Args:
        repo_path: Path to cloned repository
        scan_id: Unique scan identifier
    
    Returns:
        Tuple of (success: bool, scan_results: dict)
    """
    try:
        logger.info('=' * 80)
        logger.info(f'🔐 TRIVY SCAN: {scan_id}')
        logger.info(f'   Repository: {repo_path}')
        logger.info('=' * 80)
        
        # Convert path for WSL
        wsl_repo_path = get_wsl_path(repo_path)
        logger.info(f'[Trivy] WSL path: {wsl_repo_path}')
        
        # Check if Trivy is available in WSL
        logger.info('[Trivy] Checking for trivy availability in WSL...')
        check_tool_cmd = 'command -v trivy || true'
        success, tool_path, stderr = run_wsl_command(check_tool_cmd)

        if not (success and tool_path and tool_path.strip()):
            logger.warning('[Trivy] ✗ Trivy not found in WSL PATH - skipping Trivy scan')
            return True, {
                'scan_id': scan_id,
                'timestamp': datetime.now().isoformat(),
                'repository': os.path.basename(repo_path),
                'status': 'skipped',
                'message': 'Trivy not installed',
                'results': [],
                'findings_count': 0
            }
        
        logger.info(f'[Trivy] ✓ Found trivy at {tool_path.strip()}')

        # Run Trivy scan - scan filesystem for vulnerabilities
        logger.info('[Trivy] Starting filesystem vulnerability scan...')

        trivy_cmd = (
            f'cd {wsl_repo_path} && '
            f'trivy fs '
            f'--format json '
            f'--exit-code 0 '
            f'--no-progress '
            f'. 2>&1 || true'
        )

        logger.debug(f'[Trivy] Command: {trivy_cmd}')
        
        success, stdout, stderr = run_wsl_command(trivy_cmd, timeout=600)
        
        if not success and not stdout:
            logger.warning(f'[Trivy] ⚠ Scan command had issues, but continuing...')
            logger.warning(f'[Trivy] stderr: {stderr[:500]}')
        
        logger.info('[Trivy] ✓ Scan completed')

        # Build base results structure
        scan_results = {
            'scan_id': scan_id,
            'timestamp': datetime.now().isoformat(),
            'repository': os.path.basename(repo_path),
            'raw_output': stdout,
            'status': 'completed'
        }

        # Parse JSON output robustly - handle both Vulnerabilities AND Secrets
        vulnerabilities = []
        secrets = []
        try:
            if stdout and stdout.strip():
                try:
                    # Find JSON start - skip log lines
                    lines = stdout.strip().split('\n')
                    json_start = 0
                    for i, line in enumerate(lines):
                        if line.strip().startswith('{'):
                            json_start = i
                            break
                    json_str = '\n'.join(lines[json_start:])
                    parsed = json.loads(json_str)
                    
                    # Trivy returns Results array
                    if isinstance(parsed, dict) and 'Results' in parsed:
                        results = parsed.get('Results', []) or []
                        for result in results:
                            if isinstance(result, dict):
                                # Get Vulnerabilities
                                vulns = result.get('Vulnerabilities', []) or []
                                vulnerabilities.extend(vulns)
                                # Get Secrets
                                secs = result.get('Secrets', []) or []
                                secrets.extend(secs)
                    elif isinstance(parsed, list):
                        vulnerabilities = parsed
                except Exception as parse_err:
                    logger.warning(f'[Trivy] Error parsing JSON: {parse_err}')
                    # Try line-wise parsing
                    json_lines = []
                    for line in stdout.splitlines():
                        line = line.strip()
                        if line and line.startswith('{'):
                            try:
                                obj = json.loads(line)
                                json_lines.append(obj)
                            except Exception:
                                continue
                    # Check for results in parsed lines
                    for obj in json_lines:
                        if isinstance(obj, dict) and 'Results' in obj:
                            for r in obj.get('Results', []):
                                vulnerabilities.extend(r.get('Vulnerabilities', []))
                                secrets.extend(r.get('Secrets', []))
            else:
                vulnerabilities = []
                secrets = []
        except Exception as e:
            logger.warning(f'[Trivy] Error parsing output: {e}')
            vulnerabilities = []
            secrets = []

        # Combine vulnerabilities and secrets
        all_results = vulnerabilities + secrets
        scan_results['results'] = all_results
        scan_results['findings_count'] = len(all_results)
        scan_results['vulnerabilities_count'] = len(vulnerabilities)
        scan_results['secrets_count'] = len(secrets)

        if vulnerabilities:
            logger.info(f'[Trivy] ✓ Found {len(vulnerabilities)} vulnerabilities')
        else:
            logger.info('[Trivy] ✓ No vulnerabilities found')

        logger.info('=' * 80)
        logger.info(f'✅ TRIVY SCAN COMPLETE: {scan_id}')
        logger.info(f'   Findings: {scan_results.get("findings_count", 0)}')
        logger.info('=' * 80)

        return True, scan_results
    
    except Exception as e:
        logger.exception(f'Exception in run_trivy_scan: {e}')
        return False, {
            'error': str(e),
            'scan_id': scan_id,
            'status': 'failed'
        }


def save_scan_results(scan_results, scan_id):
    """
    Save scan results to logs directory (handles both OpenGrep and Trivy results)
    
    Args:
        scan_results: Either a dict with 'opengrep' and 'trivy' keys, or single tool result
        scan_id: Unique scan identifier
    
    Returns:
        Path to output directory or None
    """
    try:
        logger.info('[Save] Saving scan results...')
        
        logs_dir = get_logs_directory()
        if not logs_dir:
            logger.error('[Save] Failed to get logs directory')
            return None
        
        # Create tool-output directory
        output_dir = os.path.join(logs_dir, 'tool-output', scan_id)
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f'[Save] Output directory: {output_dir}')
        
        # Determine if we have tools
        has_opengrep = isinstance(scan_results, dict) and 'opengrep' in scan_results
        has_truffle = isinstance(scan_results, dict) and 'truffle' in scan_results
        has_trivy = isinstance(scan_results, dict) and 'trivy' in scan_results
        
        saved_files = []
        
        # Save OpenGrep results if present
        if has_opengrep:
            opengrep_file = os.path.join(output_dir, 'opengrep.json')
            try:
                with open(opengrep_file, 'w', encoding='utf-8') as f:
                    json.dump(scan_results['opengrep'], f, indent=2, default=str)
                
                file_size = os.path.getsize(opengrep_file)
                logger.info(f'[Save] ✓ OpenGrep results saved: {opengrep_file} ({file_size} bytes)')
                saved_files.append(opengrep_file)
            except Exception as e:
                logger.exception(f'[Save] Error writing OpenGrep results: {e}')
        
        # Save Truffle results if present
        if has_truffle:
            truffle_file = os.path.join(output_dir, 'truffle.json')
            try:
                with open(truffle_file, 'w', encoding='utf-8') as f:
                    json.dump(scan_results['truffle'], f, indent=2, default=str)
                
                file_size = os.path.getsize(truffle_file)
                logger.info(f'[Save] ✓ Truffle results saved: {truffle_file} ({file_size} bytes)')
                saved_files.append(truffle_file)
            except Exception as e:
                logger.exception(f'[Save] Error writing Truffle results: {e}')
        
        # Save Trivy results if present
        if has_trivy:
            trivy_file = os.path.join(output_dir, 'trivy.json')
            try:
                with open(trivy_file, 'w', encoding='utf-8') as f:
                    json.dump(scan_results['trivy'], f, indent=2, default=str)
                
                file_size = os.path.getsize(trivy_file)
                logger.info(f'[Save] ✓ Trivy results saved: {trivy_file} ({file_size} bytes)')
                saved_files.append(trivy_file)
            except Exception as e:
                logger.exception(f'[Save] Error writing Trivy results: {e}')
        
        # Save Merged results if present
        has_merged = isinstance(scan_results, dict) and 'merged' in scan_results
        if has_merged:
            merged_file = os.path.join(output_dir, 'merged.json')
            try:
                with open(merged_file, 'w', encoding='utf-8') as f:
                    json.dump(scan_results['merged'], f, indent=2, default=str)
                
                file_size = os.path.getsize(merged_file)
                logger.info(f'[Save] ✓ Merged results saved: {merged_file} ({file_size} bytes)')
                saved_files.append(merged_file)
            except Exception as e:
                logger.exception(f'[Save] Error writing Merged results: {e}')
        
        # Fallback: if scan_results doesn't have opengrep/trivy keys, save as single opengrep.json
        if not (has_opengrep or has_trivy) and isinstance(scan_results, dict):
            results_file = os.path.join(output_dir, 'opengrep.json')
            try:
                with open(results_file, 'w', encoding='utf-8') as f:
                    json.dump(scan_results, f, indent=2, default=str)
                
                file_size = os.path.getsize(results_file)
                logger.info(f'[Save] ✓ Results saved to: {results_file} ({file_size} bytes)')
                saved_files.append(results_file)
            except Exception as e:
                logger.exception(f'[Save] Error writing results file: {e}')
        
        if saved_files:
            logger.info(f'[Save] Total files saved: {len(saved_files)}')
            return output_dir
        else:
            logger.error('[Save] No files were saved')
            return None
    
    except Exception as e:
        logger.exception(f'Exception in save_scan_results: {e}')
        return None


def merge_findings(opengrep_results, truffle_results, trivy_results, scan_id):
    """
    Merge findings from all 3 tools (OpenGrep, TruffleHog, Trivy) into unified structure.
    Removes duplicates by file + line + issue type, but keeps all tool sources.
    """
    logger.info('=' * 80)
    logger.info('🔄 MERGING FINDINGS FROM ALL TOOLS')
    logger.info('=' * 80)
    
    merged_findings = []
    seen_issues = {}
    finding_id = 1
    
    def normalize_severity(sev):
        sev_lower = str(sev).upper() if sev else 'INFO'
        if sev_lower in ['ERROR', 'CRITICAL', 'HIGH']:
            return 'CRITICAL'
        elif sev_lower in ['WARNING', 'MEDIUM']:
            return 'MEDIUM'
        return 'LOW'
    
    def get_issue_type(item, source):
        if source == 'opengrep':
            check_id = item.get('check_id', '')
            if 'private-key' in check_id or 'secret' in check_id:
                return 'private_key'
            elif 'sql' in check_id.lower() or 'injection' in check_id.lower():
                return 'sql_injection'
            elif 'eval' in check_id.lower():
                return 'code_injection'
            return 'code_issue'
        elif source == 'trufflehog':
            detector = item.get('DetectorName', '')
            if 'PrivateKey' in detector:
                return 'private_key'
            elif 'Github' in detector:
                return 'github_token'
            return 'secret'
        elif source == 'trivy':
            return 'secret'
        return 'unknown'
    
    # Process OpenGrep
    for finding in (opengrep_results.get('results', []) or []):
        path = finding.get('path', 'unknown')
        line = finding.get('start', {}).get('line', 0)
        check_id = finding.get('check_id', 'unknown')
        extra = finding.get('extra', {})
        issue_type = get_issue_type(finding, 'opengrep')
        key = f"{path}:{line}:{issue_type}"
        
        if key in seen_issues:
            existing = seen_issues[key]
            if 'opengrep' not in existing['sources']:
                existing['sources'].append('opengrep')
            continue
        
        cwe_list = []
        for c in (extra.get('metadata', {}).get('cwe', [])):
            if isinstance(c, str) and 'CWE-' in c:
                cwe_list.append(c.split(':')[0] if ':' in c else c)
        
        merged_findings.append({
            'id': str(finding_id),
            'file': path,
            'line': line,
            'type': issue_type,
            'title': check_id.split('.')[-1].replace('-', ' ').title(),
            'message': extra.get('message', ''),
            'severity': normalize_severity(extra.get('severity', 'WARNING')),
            'category': 'secrets' if issue_type in ['private_key', 'github_token', 'secret'] else 'code',
            'cwe': cwe_list,
            'sources': ['opengrep'],
            'details': {'opengrep': {'check_id': check_id}}
        })
        seen_issues[key] = merged_findings[-1]
        finding_id += 1
    
    # Process TruffleHog
    for finding in (truffle_results.get('results', []) or []):
        if 'DetectorType' not in finding:
            continue
        metadata = finding.get('SourceMetadata', {}).get('Data', {}).get('Filesystem', {})
        path = metadata.get('file', 'unknown')
        line = metadata.get('line', 0)
        detector_name = finding.get('DetectorName', '')
        issue_type = get_issue_type(finding, 'trufflehog')
        key = f"{path}:{line}:{issue_type}"
        
        if key in seen_issues:
            existing = seen_issues[key]
            if 'trufflehog' not in existing['sources']:
                existing['sources'].append('trufflehog')
            continue
        
        merged_findings.append({
            'id': str(finding_id),
            'file': path,
            'line': line,
            'type': issue_type,
            'title': detector_name,
            'message': finding.get('DetectorDescription', ''),
            'severity': 'CRITICAL' if issue_type == 'private_key' else 'HIGH',
            'category': 'secrets',
            'cwe': ['CWE-798'] if issue_type == 'private_key' else [],
            'sources': ['trufflehog'],
            'details': {'trufflehog': {'detector': detector_name}}
        })
        seen_issues[key] = merged_findings[-1]
        finding_id += 1
    
    # Process Trivy
    for finding in (trivy_results.get('results', []) or []):
        for secret in (finding.get('Secrets', []) or []):
            target = finding.get('Target', 'unknown')
            line = secret.get('StartLine', 0)
            issue_type = 'secret'
            key = f"{target}:{line}:{issue_type}"
            
            if key in seen_issues:
                existing = seen_issues[key]
                if 'trivy' not in existing['sources']:
                    existing['sources'].append('trivy')
                continue
            
            merged_findings.append({
                'id': str(finding_id),
                'file': target,
                'line': line,
                'type': issue_type,
                'title': secret.get('Title', secret.get('RuleID', '')),
                'message': f"{secret.get('Category', '')}: {secret.get('Title', '')}",
                'severity': 'HIGH',
                'category': 'secrets',
                'cwe': [],
                'sources': ['trivy'],
                'details': {'trivy': {'rule_id': secret.get('RuleID', '')}}
            })
            seen_issues[key] = merged_findings[-1]
            finding_id += 1
    
    # Summary
    severity_counts = {'CRITICAL': 0, 'MEDIUM': 0, 'LOW': 0}
    category_counts = {'secrets': 0, 'code': 0}
    
    for f in merged_findings:
        severity_counts[f['severity']] = severity_counts.get(f['severity'], 0) + 1
        category_counts[f['category']] = category_counts.get(f['category'], 0) + 1
    
    multi_source = sum(1 for f in merged_findings if len(f['sources']) > 1)
    
    merged_result = {
        'scan_id': scan_id,
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_unique': len(merged_findings),
            'multi_source_findings': multi_source,
            'by_severity': severity_counts,
            'by_category': category_counts,
            'tool_breakdown': {
                'opengrep': opengrep_results.get('findings_count', 0),
                'trufflehog': truffle_results.get('findings_count', 0),
                'trivy': trivy_results.get('findings_count', 0)
            }
        },
        'findings': merged_findings
    }
    
    logger.info(f'[Merge] ✓ Merged {len(merged_findings)} unique findings')
    logger.info(f'[Merge]   CRITICAL: {severity_counts.get("CRITICAL", 0)}')
    logger.info(f'[Merge]   MEDIUM: {severity_counts.get("MEDIUM", 0)}')
    logger.info(f'[Merge]   LOW: {severity_counts.get("LOW", 0)}')
    logger.info(f'[Merge]   Multi-source: {multi_source}')
    logger.info('=' * 80)
    
    return merged_result


def trigger_scan(repo_id, repo_name, repo_owner, repo_url, repo_branch='main'):
    """
    Main entry point - Complete scan workflow (clone -> scan -> save -> cleanup)
    
    Args:
        repo_id: Repository ID
        repo_name: Repository name
        repo_owner: Repository owner
        repo_url: Repository URL
        repo_branch: Branch to scan (default: main)
    
    Returns:
        Dict with status and scan details
    """
    scan_id = generate_scan_id()
    clone_path = None
    
    try:
        logger.info('')
        logger.info('╔' + '═' * 78 + '╗')
        logger.info('║' + ' COMPLETE SCAN WORKFLOW '.center(78) + '║')
        logger.info('╚' + '═' * 78 + '╝')
        logger.info(f'Scan ID: {scan_id}')
        logger.info(f'Repository: {repo_owner}/{repo_name} (ID: {repo_id})')
        logger.info(f'Branch: {repo_branch}')
        logger.info(f'URL: {repo_url}')
        
        # ========== STEP 1: CLONE ==========
        logger.info('')
        logger.info('╔' + '─' * 78 + '╗')
        logger.info('║ STEP 1/4: CLONING REPOSITORY'.ljust(79) + '║')
        logger.info('╚' + '─' * 78 + '╝')
        
        clone_result = clone_repository(repo_id, repo_name, repo_owner, repo_url, repo_branch)
        
        if clone_result['status'] != 'success':
            logger.error(f'[Step 1] ✗ Clone failed: {clone_result["message"]}')
            return {
                'status': 'error',
                'message': f'Clone failed: {clone_result["message"]}',
                'scan_id': scan_id,
                'repo_id': repo_id,
                'repo_name': repo_name,
                'error_details': clone_result.get('error_details', '')
            }
        
        clone_details = clone_result.get('clone_details', {})
        clone_path = clone_details.get('clone_path', None)
        logger.info(f'[Step 1] ✓ Clone successful: {clone_path}')
        
        # ========== STEP 2: RUN OPENGREP SCAN ==========
        logger.info('')
        logger.info('╔' + '─' * 78 + '╗')
        logger.info('║ STEP 2/5: RUNNING OPENGREP SCAN'.ljust(79) + '║')
        logger.info('╚' + '─' * 78 + '╝')
        
        success, opengrep_results = run_opengrep_scan(clone_path, scan_id)
        
        if not success:
            logger.error(f'[Step 2] ✗ OpenGrep failed: {opengrep_results.get("error", "Unknown error")}')
            # Continue to cleanup even if scan failed
            logger.info('[Step 2] Attempting cleanup despite scan failure...')
            cleanup_cloned_repo(repo_owner, repo_name)
            
            return {
                'status': 'error',
                'message': f'OpenGrep scan failed: {opengrep_results.get("error", "Unknown error")}',
                'scan_id': scan_id,
                'repo_id': repo_id,
                'repo_name': repo_name,
                'error_details': opengrep_results
            }
        
        logger.info(f'[Step 2] ✓ OpenGrep complete: {opengrep_results.get("findings_count", 0)} findings')
        
        # ========== STEP 3: RUN TRUFFLEHOG SCAN ==========
        logger.info('')
        logger.info('╔' + '─' * 78 + '╗')
        logger.info('║ STEP 3/7: RUNNING TRUFFLEHOG SCAN (SECRETS)'.ljust(79) + '║')
        logger.info('╚' + '─' * 78 + '╝')
        
        success, truffle_results = run_truffle_scan(clone_path, scan_id)
        
        if not success:
            logger.warning(f'[Step 3] ⚠ TruffleHog had issues: {truffle_results.get("error", "Unknown")}')
            truffle_results = {
                'status': 'failed',
                'findings_count': 0,
                'results': []
            }
        
        logger.info(f'[Step 3] ✓ TruffleHog complete: {truffle_results.get("findings_count", 0)} secrets')
        
        # ========== STEP 4: RUN TRIVY SCAN ==========
        logger.info('')
        logger.info('╔' + '─' * 78 + '╗')
        logger.info('║ STEP 4/7: RUNNING TRIVY SCAN'.ljust(79) + '║')
        logger.info('╚' + '─' * 78 + '╝')
        
        success_trivy, trivy_results = run_trivy_scan(clone_path, scan_id)
        
        if not success_trivy:
            logger.error(f'[Step 3] ✗ Trivy failed: {trivy_results.get("error", "Unknown error")}')
            # Continue anyway - Trivy failure shouldn't stop the workflow
            logger.info('[Step 3] Trivy scan failed, but continuing with results...')
            trivy_results = {
                'status': 'failed',
                'error': trivy_results.get("error", "Unknown error"),
                'findings_count': 0,
                'results': []
            }
        
        logger.info(f'[Step 3] ✓ Trivy complete: {trivy_results.get("findings_count", 0)} vulnerabilities')
        
        # ========== STEP 5: MERGE FINDINGS ==========
        logger.info('')
        logger.info('╔' + '─' * 78 + '╗')
        logger.info('║ STEP 5/7: MERGING FINDINGS'.ljust(79) + '║')
        logger.info('╚' + '─' * 78 + '╝')
        
        merged_results = merge_findings(opengrep_results, truffle_results, trivy_results, scan_id)
        logger.info(f'[Step 5] ✓ Merged: {merged_results["summary"]["total_unique"]} unique findings')
        
        # ========== STEP 6: SAVE RESULTS ==========
        logger.info('')
        logger.info('╔' + '─' * 78 + '╗')
        logger.info('║ STEP 6/7: SAVING RESULTS'.ljust(79) + '║')
        logger.info('╚' + '─' * 78 + '╝')
        
        combined_results = {
            'opengrep': opengrep_results,
            'truffle': truffle_results,
            'trivy': trivy_results,
            'merged': merged_results
        }
        
        results_dir = save_scan_results(combined_results, scan_id)
        
        if not results_dir:
            logger.error('[Step 4] ✗ Failed to save results')
            # Continue to cleanup
            cleanup_cloned_repo(repo_owner, repo_name)
            
            return {
                'status': 'error',
                'message': 'Failed to save scan results',
                'scan_id': scan_id,
                'repo_id': repo_id,
                'repo_name': repo_name
            }
        
        logger.info(f'[Step 5] ✓ Results saved: {results_dir}')
        
        # ========== STEP 6: CLEANUP ==========
        logger.info('')
        logger.info('╔' + '─' * 78 + '╗')
        logger.info('║ STEP 7/7: CLEANUP'.ljust(79) + '║')
        logger.info('╚' + '─' * 78 + '╝')
        
        cleanup_success = cleanup_cloned_repo(repo_owner, repo_name)
        
        if cleanup_success:
            logger.info(f'[Step 6] ✓ Repository cleanup successful')
        else:
            logger.warning(f'[Step 6] ⚠ Repository cleanup had issues (may retry manually)')
        
        # ========== FINAL RESULT ==========
        logger.info('')
        logger.info('╔' + '═' * 78 + '╗')
        logger.info('║' + ' SCAN COMPLETE ✅ '.center(78) + '║')
        logger.info('╚' + '═' * 78 + '╝')
        logger.info(f'Scan ID: {scan_id}')
        logger.info(f'Repository: {repo_owner}/{repo_name}')
        
        merged_summary = merged_results.get('summary', {})
        logger.info(f'--- MERGED FINDINGS ---')
        logger.info(f'Total Unique: {merged_summary.get("total_unique", 0)}')
        logger.info(f'  CRITICAL: {merged_summary.get("by_severity", {}).get("CRITICAL", 0)}')
        logger.info(f'  MEDIUM: {merged_summary.get("by_severity", {}).get("MEDIUM", 0)}')
        logger.info(f'  LOW: {merged_summary.get("by_severity", {}).get("LOW", 0)}')
        logger.info(f'Multi-source: {merged_summary.get("multi_source_findings", 0)}')
        logger.info(f'--- TOOL BREAKDOWN ---')
        logger.info(f'OpenGrep: {opengrep_results.get("findings_count", 0)}')
        logger.info(f'Trivy: {trivy_results.get("findings_count", 0)}')
        logger.info(f'Trivy vulnerabilities: {trivy_results.get("findings_count", 0)}')
        logger.info(f'Results: {results_dir}')
        logger.info('')
        
        return {
            'status': 'success',
            'message': f'Successfully completed scan for {repo_owner}/{repo_name}',
            'scan_id': scan_id,
            'repo_id': repo_id,
            'repo_name': repo_name,
            'repo_owner': repo_owner,
            'clone_path': clone_path,
            'results_dir': results_dir,
            'opengrep_findings': opengrep_results.get('findings_count', 0),
            'trivy_findings': trivy_results.get('findings_count', 0),
            'total_findings': opengrep_results.get('findings_count', 0) + trivy_results.get('findings_count', 0),
            'cleanup_success': cleanup_success
        }
    
    except Exception as e:
        logger.exception(f'Exception in trigger_scan: {e}')
        
        # Attempt cleanup on error
        if clone_path:
            try:
                logger.info('[Error] Attempting cleanup after exception...')
                cleanup_cloned_repo(repo_owner, repo_name)
            except Exception as cleanup_error:
                logger.warning(f'[Error] Cleanup also failed: {cleanup_error}')
        
        return {
            'status': 'error',
            'message': f'Scan workflow failed: {str(e)}',
            'scan_id': scan_id,
            'repo_id': repo_id,
            'repo_name': repo_name,
            'error_details': str(e)
        }
