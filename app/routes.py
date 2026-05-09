from flask import Blueprint, render_template, jsonify, request, current_app, session, redirect, url_for
import sys
import os
import hmac
import hashlib
import json

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import db
from modules.overview import get_overview_data
from modules.repos import get_repositories, get_repository_stats, get_repository_branches
from modules.history import get_scan_history, get_history_stats, get_scan_details
from modules.settings import (get_settings, get_integration_status, 
                             get_github_credentials, save_github_credentials, 
                             get_github_credentials_for_user)
from modules.scan_controller import trigger_scan
from auth.decorators import require_login, require_admin
from auth.utils import get_current_user

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Main route - redirect to login if not authenticated, otherwise show dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return redirect(url_for('main.dashboard'))


@bp.route('/dashboard')
@require_login
def dashboard():
    """Render main dashboard page"""
    overview_data = get_overview_data()
    repos_stats = get_repository_stats()
    history_stats = get_history_stats()
    
    context = {
        'overview': overview_data,
        'repos_stats': repos_stats,
        'history_stats': history_stats
    }
    return render_template('dashboard.html', **context)


# API endpoints for tab data
@bp.route('/api/overview')
@require_login
def api_overview():
    """API endpoint for overview data"""
    return jsonify(get_overview_data())


@bp.route('/api/repos')
@require_login
def api_repos():
    """API endpoint for repositories"""
    return jsonify({
        'repositories': get_repositories(),
        'stats': get_repository_stats()
    })


@bp.route('/api/branches/<path:owner>/<path:repo_name>')
@require_login
def api_branches(owner, repo_name):
    """API endpoint to fetch available branches for a repository"""
    try:
        branches = get_repository_branches(owner, repo_name)
        return jsonify({
            'branches': branches,
            'status': 'success'
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching branches for {owner}/{repo_name}: {e}")
        return jsonify({
            'branches': [],
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/api/history')
@require_login
def api_history():
    """API endpoint for scan history"""
    return jsonify({
        'history': get_scan_history(),
        'stats': get_history_stats()
    })


@bp.route('/api/history/<scan_id>')
@require_login
def api_scan_details(scan_id):
    """API endpoint for getting detailed scan information"""
    details = get_scan_details(scan_id)
    if details:
        # If files exist but are incomplete, return 202 (Accepted) to indicate retry
        if details.get('errors') and not details.get('files'):
            return jsonify({
                'status': 'processing',
                'message': 'Scan results still being written. Please retry in a moment.',
                'errors': details.get('errors', [])
            }), 202
        # Return partial data if some files are incomplete
        if details.get('errors') and details.get('files'):
            response = jsonify(details)
            response.status_code = 206  # 206 Partial Content
            return response
        return jsonify(details), 200
    return jsonify({'error': 'Scan not found', 'status': 'not_found'}), 404


@bp.route('/api/history/filter')
@require_login
def api_history_filter():
    """API endpoint for filtering scan history findings by severity, tool, category, and search"""
    severity = request.args.get('severity', '')
    tool = request.args.get('tool', '')
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    
    # Parse comma-separated values into lists
    severity_list = [s.strip().upper() for s in severity.split(',') if s.strip()]
    tool_list = [t.strip().lower() for t in tool.split(',') if t.strip()]
    category_list = [c.strip().lower() for c in category.split(',') if c.strip()]
    
    # If no filters, return all history
    if not severity_list and not tool_list and not category_list and not search:
        history = get_scan_history()
        return jsonify({'history': history})
    
    # Get history and filter
    history = get_scan_history()
    filtered = []
    
    for scan in history:
        # Filter findings in each scan
        findings = scan.get('findings', [])
        if not findings:
            findings = []
        
        filtered_findings = [
            f for f in findings
            if (not severity_list or f.get('severity', '').upper() in severity_list)
            and (not tool_list or any(t in f.get('sources', []).lower() if f.get('sources') else [] for t in tool_list))
            and (not category_list or f.get('category', '').lower() in category_list)
            and (not search or search.lower() in (f.get('file', '') or '').lower() or search.lower() in (f.get('message', '') or '').lower() or search.lower() in (f.get('title', '') or '').lower())
        ]
        
        if filtered_findings:  # Only return scans with matching findings
            scan_copy = scan.copy()
            scan_copy['findings'] = filtered_findings
            filtered.append(scan_copy)
    
    return jsonify({'history': filtered})


@bp.route('/api/history/delete', methods=['POST'])
@require_login
def api_delete_history():
    """API endpoint for deleting scans"""
    import os
    import shutil
    
    data = request.get_json()
    scan_ids = data.get('scan_ids', [])
    
    if not scan_ids:
        return jsonify({'success': False, 'message': 'No scan IDs provided'}), 400
    
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'tool-output')
    deleted_count = 0
    errors = []
    
    for scan_id in scan_ids:
        scan_path = os.path.join(logs_dir, scan_id)
        if os.path.exists(scan_path) and os.path.isdir(scan_path):
            try:
                shutil.rmtree(scan_path)
                deleted_count += 1
            except Exception as e:
                errors.append(f"Failed to delete {scan_id}: {str(e)}")
    
    if deleted_count > 0:
        return jsonify({
            'success': True, 
            'deleted': deleted_count,
            'message': f'Deleted {deleted_count} scan(s)'
        })
    else:
        return jsonify({
            'success': False, 
            'message': 'No scans were deleted. ' + '; '.join(errors) if errors else 'Scans not found'
        }), 400


@bp.route('/api/repos/scan', methods=['POST'])
@require_login
def api_trigger_repo_scan():
    """API endpoint for manual scan triggers."""
    try:
        payload = request.get_json(silent=True) or {}
        repo_id = payload.get('repo_id')
        repo_name = payload.get('repo_name')
        repo_owner = payload.get('repo_owner')
        repo_url = payload.get('repo_url')
        repo_branch = payload.get('repo_branch', 'main')
        scan_types = payload.get('scan_types', ['sats', 'sbom', 'secret'])

        if not repo_id:
            return jsonify({'status': 'error', 'message': 'repo_id is required'}), 400
        
        if not repo_name or not repo_owner:
            return jsonify({'status': 'error', 'message': 'repo_name and repo_owner are required'}), 400
        
        if not repo_url:
            repo_url = f'https://github.com/{repo_owner}/{repo_name}.git'

        current_app.logger.info('Manual scan requested for repo_id=%s (%s/%s) from %s | scan_types=%s', 
                               repo_id, repo_owner, repo_name, request.remote_addr, scan_types)
        
        # Trigger the actual scan using the controller
        result = trigger_scan(repo_id, repo_name, repo_owner, repo_url, repo_branch, scan_types)
        
        current_app.logger.info('[RESULT] Status: %s | Message: %s | Keys: %s', 
                               result.get('status'), result.get('message'), list(result.keys()))
        
        if result['status'] == 'success':
            current_app.logger.info('✓ Scan successful: %s', result['message'])
            return jsonify(result), 200
        else:
            current_app.logger.error('✗ Scan failed: %s', result['message'])
            return jsonify(result), 500
    except Exception as e:
        current_app.logger.exception('Error handling manual scan request: %s', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/repos/scan-all', methods=['POST'])
@require_login
def api_scan_all_repos():
    """API endpoint to scan all repositories from GitHub App."""
    try:
        from modules.repos import get_repositories
        
        payload = request.get_json(silent=True) or {}
        scan_types = payload.get('scan_types', ['sats', 'sbom', 'secret'])
        
        current_app.logger.info('Scan all repos requested from %s | scan_types=%s', request.remote_addr, scan_types)
        
        # Check if repos with branch info are provided in the request
        repos_from_request = payload.get('repos', None)
        
        if repos_from_request:
            # Use repos and branches from frontend
            repos_to_scan = repos_from_request
            current_app.logger.info('Using %d repos with branch info from request', len(repos_to_scan))
        else:
            # Get all repositories from GitHub App (fallback)
            all_repos = get_repositories()
            
            if not all_repos or len(all_repos) == 0:
                return jsonify({'status': 'error', 'message': 'No repositories found'}), 404
            
            # Convert to the format expected by scan
            repos_to_scan = [
                {
                    'repo_id': repo.get('id', ''),
                    'repo_name': repo.get('name', ''),
                    'repo_owner': repo.get('owner', ''),
                    'repo_url': repo.get('url', f'https://github.com/{repo.get("owner", "")}/{repo.get("name", "")}.git'),
                    'repo_branch': repo.get('branch', 'main')
                }
                for repo in all_repos
            ]
        
        triggered_scans = []
        failed_scans = []
        
        for repo_info in repos_to_scan:
            try:
                repo_id = repo_info.get('repo_id', '')
                repo_name = repo_info.get('repo_name', '')
                repo_owner = repo_info.get('repo_owner', '')
                repo_url = repo_info.get('repo_url', f'https://github.com/{repo_owner}/{repo_name}.git')
                repo_branch = repo_info.get('repo_branch', 'main')
                
                if not repo_id or not repo_name or not repo_owner:
                    failed_scans.append({'repo': f"{repo_owner}/{repo_name}", 'error': 'Missing required fields'})
                    continue
                
                # Trigger scan for this repo with its selected branch
                result = trigger_scan(repo_id, repo_name, repo_owner, repo_url, repo_branch, scan_types)
                
                triggered_scans.append({
                    'repo_id': repo_id,
                    'repo_name': repo_name,
                    'repo_owner': repo_owner,
                    'repo_branch': repo_branch,
                    'status': result.get('status', 'unknown'),
                    'scan_id': result.get('scan_id', '')
                })
                
                current_app.logger.info('✓ Triggered scan for %s/%s (branch: %s)', repo_owner, repo_name, repo_branch)
                
            except Exception as scan_err:
                current_app.logger.error('Failed to scan %s: %s', repo_info.get('repo_name', 'unknown'), str(scan_err))
                failed_scans.append({'repo': f"{repo_info.get('repo_owner', 'unknown')}/{repo_info.get('repo_name', 'unknown')}", 'error': str(scan_err)})
        
        return jsonify({
            'status': 'success',
            'message': f'Triggered {len(triggered_scans)} scans',
            'total_repos': len(repos_to_scan),
            'triggered': triggered_scans,
            'failed': failed_scans
        })
        
    except Exception as e:
        current_app.logger.exception('Error scanning all repos: %s', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/runtime')
@require_login
def api_runtime():
    """Return runtime information to help diagnose environment (python executable, cwd, PATH)."""
    try:
        import sys
        import os
        info = {
            'python_executable': sys.executable,
            'cwd': os.getcwd(),
            'path': os.environ.get('PATH', '')[:2000]
        }
        current_app.logger.info('Runtime info requested: %s', info)
        return jsonify({'status': 'success', 'runtime': info})
    except Exception as exc:
        current_app.logger.exception('Error collecting runtime info: %s', exc)
        return jsonify({'status': 'error', 'message': str(exc)}), 500


@bp.route('/api/settings')
@require_login
def api_settings():
    """API endpoint for settings"""
    return jsonify({
        'settings': get_settings(),
        'integrations': get_integration_status()
    })


@bp.route('/api/settings/github', methods=['GET'])
@require_login
def api_get_github_credentials():
    """API endpoint to retrieve GitHub credentials (decrypted for authenticated user)"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not authenticated'
            }), 401
        
        # Try database first (encrypted credentials)
        credentials = get_github_credentials_for_user(user.id)
        
        # Fallback to .env if not in database
        if not credentials or not credentials.get('github_app_id'):
            credentials = get_github_credentials()
        
        return jsonify({
            'status': 'success',
            'credentials': credentials
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/api/settings/github', methods=['POST'])
@require_login
def api_save_github_credentials():
    """API endpoint to save GitHub credentials (encrypted in database)"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not authenticated'
            }), 401
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        result = save_github_credentials(
            github_app_id=data.get('github_app_id', ''),
            github_app_name=data.get('github_app_name', ''),
            github_secret_key=data.get('github_secret_key', ''),
            ngrok_oauth_token=data.get('ngrok_oauth_token', ''),
            github_webhook_secret=data.get('github_webhook_secret', ''),
            user_id=user.id  # Pass current user ID for encryption
        )
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error saving credentials: {str(e)}'
        }), 500


@bp.route('/api/log', methods=['POST'])
@require_login
def api_client_log():
    """Accept client-side logs (UI events) and write them to server logs."""
    try:
        payload = request.get_json(silent=True) or {}
        event = payload.get('event') or 'client_event'
        details = payload.get('details') or {}
        level = payload.get('level', 'info').lower()

        # Normalize details size
        import json as _json
        try:
            details_str = _json.dumps(details) if not isinstance(details, str) else details
        except Exception:
            details_str = str(details)

        msg = f"ClientLog - {event} - {details_str} - remote={request.remote_addr}"

        if level == 'debug':
            current_app.logger.debug(msg)
        elif level == 'warning' or level == 'warn':
            current_app.logger.warning(msg)
        elif level == 'error':
            current_app.logger.error(msg)
        else:
            current_app.logger.info(msg)

        return jsonify({'status': 'ok'})
    except Exception as e:
        current_app.logger.exception('Error handling client log: %s', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/export-report')
@require_login
def api_export_report():
    """Generate and download security scan report"""
    import json
    from datetime import datetime
    from flask import make_response
    
    try:
        # Get filter params (000 to 111 - date, severity, tool)
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        severity_filter = request.args.get('severity', '').split(',') if request.args.get('severity') else []
        tool_filter = request.args.get('tool', '').split(',') if request.args.get('tool') else []
        
        # Get logs directory
        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(module_dir)
        logs_dir = os.path.join(project_root, 'logs', 'tool-output')
        
        if not os.path.exists(logs_dir):
            return jsonify({'error': 'No scan data found'}), 404
        
        # Read scans based on filters
        scans = []
        for scan_dir in os.listdir(logs_dir):
            scan_path = os.path.join(logs_dir, scan_dir)
            if not os.path.isdir(scan_path):
                continue
            
            # If tool filter, filter merged.json by sources; else use all merged findings
            if tool_filter:
                merged_file = os.path.join(scan_path, 'merged.json')
                if os.path.exists(merged_file):
                    try:
                        with open(merged_file, 'r') as f:
                            m = json.load(f)
                            scan_data = {'scan_id': scan_dir, 'findings': [], 'summary': {'total_unique': 0, 'by_severity': {}}}
                            scan_data['repo_name'] = m.get('repo_name', '')
                            scan_data['repo_owner'] = m.get('repo_owner', '')
                            scan_data['repo_branch'] = m.get('repo_branch', 'main')
                            scan_data['timestamp'] = m.get('timestamp', scan_dir)
                            # Filter findings by tool/source
                            for f in m.get('findings', []):
                                sources = f.get('sources', [])
                                # Check if any of the tool_filter is in sources
                                # Normalize: truffle -> trufflehog, etc.
                                for t in tool_filter:
                                    if t == 'truffle' and 'trufflehog' in sources:
                                        scan_data['findings'].append(f)
                                        break
                                    elif t in sources:
                                        scan_data['findings'].append(f)
                                        break
                            by_sev = {}
                            for f in scan_data['findings']:
                                sev = f.get('severity', 'LOW').upper()
                                by_sev[sev] = by_sev.get(sev, 0) + 1
                            scan_data['summary']['by_severity'] = by_sev
                            scan_data['summary']['total_unique'] = len(scan_data['findings'])
                            if scan_data['findings']:
                                scans.append(scan_data)
                    except Exception:
                        continue
            else:
                merged_file = os.path.join(scan_path, 'merged.json')
                if os.path.exists(merged_file):
                    try:
                        with open(merged_file, 'r') as f:
                            scan_data = json.load(f)
                            scan_data['scan_id'] = scan_dir
                            scans.append(scan_data)
                    except Exception:
                        continue
        
        # Apply date filter (bit 0)
        if date_from or date_to:
            filtered_scans = []
            for scan in scans:
                ts = scan.get('timestamp', '')
                if not ts:
                    continue
                # Parse timestamp - could be ISO format or directory name
                try:
                    if 'T' in ts:
                        scan_date = ts.split('T')[0]
                    else:
                        scan_date = ts[:10] if len(ts) >= 10 else ''
                except:
                    scan_date = ''
                
                if date_from and scan_date < date_from:
                    continue
                if date_to and scan_date > date_to:
                    continue
                filtered_scans.append(scan)
            scans = filtered_scans
        
        # Apply severity filter
        if severity_filter:
            for scan in scans:
                scan['findings'] = [f for f in scan.get('findings', []) if f.get('severity', 'LOW').upper() in severity_filter]
                by_sev = {}
                for f in scan['findings']:
                    sev = f.get('severity', 'LOW').upper()
                    by_sev[sev] = by_sev.get(sev, 0) + 1
                scan['summary']['by_severity'] = by_sev
                scan['summary']['total_unique'] = len(scan['findings'])
        
        # Remove scans with no findings after filtering
        scans = [s for s in scans if s.get('summary', {}).get('total_unique', 0) > 0]
        
        # Sort scans: findings first, then clean scans
        scans_with_findings = [s for s in scans if s.get('summary', {}).get('total_unique', 0) > 0]
        scans_clean = [s for s in scans if s.get('summary', {}).get('total_unique', 0) == 0]
        
        # Sort by timestamp descending
        scans_with_findings.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        scans_clean.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        sorted_scans = scans_with_findings + scans_clean
        
        # Calculate totals
        total_repos = len(scans)
        total_findings = sum(s.get('summary', {}).get('total_unique', 0) for s in scans)
        
        severity_totals = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for scan in scans:
            by_severity = scan.get('summary', {}).get('by_severity', {})
            for sev in severity_totals:
                severity_totals[sev] += by_severity.get(sev, 0)
        
        # Generate scan sections HTML
        scan_sections_html = ''
        severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        
        for scan in sorted_scans:
            findings = scan.get('findings', [])
            total = scan.get('summary', {}).get('total_unique', 0)
            timestamp = scan.get('timestamp', scan.get('scan_id', ''))
            repo_name = scan.get('repo_name', 'Unknown')
            repo_owner = scan.get('repo_owner', 'Unknown')
            repo_branch = scan.get('repo_branch', 'main')
            
            # Format timestamp
            if 'T' in str(timestamp):
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = str(timestamp)
            else:
                formatted_time = str(timestamp)
            
            repo_name = scan.get('repo_name')
            repo_owner = scan.get('repo_owner')
            repo_branch = scan.get('repo_branch', 'main')
            
            if repo_name and repo_owner:
                repo_full = f"{repo_owner}/{repo_name}"
                branch_display = repo_branch
            else:
                repo_full = scan.get('scan_id', 'Unknown Repository')
                branch_display = 'N/A'
            
            scan_sections_html += f'''
            <div class="scan-section">
                <div class="scan-header">
                    <div class="scan-header-left">
                        <h3>📁 Scan: {scan.get('scan_id', 'N/A')}</h3>
                        <div class="scan-repo-info">
                            <span>📦 <strong>{repo_full}</strong></span>
                            <span>🌿 {branch_display}</span>
                        </div>
                    </div>
                    <div class="scan-meta">
                        <span>⏰ {formatted_time}</span>
                        <span>📊 {total} Findings</span>
                    </div>
                </div>
'''
            
            if total == 0:
                scan_sections_html += '''
                <div class="no-findings">
                    <div class="icon">✅</div>
                    <p>No security issues found in this scan</p>
                </div>
'''
            else:
                # Sort findings by severity
                severity_rank = {sev: i for i, sev in enumerate(severity_order)}
                sorted_findings = sorted(findings, key=lambda x: severity_rank.get(x.get('severity', 'LOW'), 3))
                
                scan_sections_html += '''
                <table class="findings-table">
                    <thead>
                        <tr>
                            <th style="width: 10%;">Severity</th>
                            <th style="width: 25%;">File / Location</th>
                            <th style="width: 25%;">Finding</th>
                            <th style="width: 40%;">Description</th>
                        </tr>
                    </thead>
                    <tbody>
'''
                for finding in sorted_findings:
                    sev = finding.get('severity', 'LOW').upper()
                    severity_class = sev.lower()
                    file_path = finding.get('file', 'unknown')
                    line = finding.get('line', 0)
                    title = finding.get('title', 'Unknown')
                    ftype = finding.get('category', 'secrets')
                    message = finding.get('message', '')
                    
                    scan_sections_html += f'''
                        <tr>
                            <td><span class="severity-badge {severity_class}">{sev}</span></td>
                            <td>{file_path}:{line}</td>
                            <td>
                                {title}
                                <div class="finding-type">{ftype}</div>
                            </td>
                            <td>{message}</td>
                        </tr>
'''
                
                scan_sections_html += '''
                    </tbody>
                </table>
'''
            
            scan_sections_html += '''
            </div>
'''
        
        # Generate the full HTML
        from datetime import datetime
        generated_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Scan Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0d0d0d;
            color: #e0e0e0;
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #1a1a1a;
            border-radius: 12px;
            box-shadow: 0 4px 30px rgba(0,0,0,0.5);
            overflow: hidden;
            border: 1px solid #2a2a2a;
        }}
        
        .header {{
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #0d1117 100%);
            color: #ffffff;
            padding: 40px;
            text-align: center;
            border-bottom: 2px solid #30363d;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }}
        
        .header .subtitle {{
            color: #8b949e;
            font-size: 1rem;
        }}
        
        .header .meta {{
            margin-top: 20px;
            display: flex;
            justify-content: center;
            gap: 40px;
            font-size: 0.9rem;
            color: #c9d1d9;
        }}
        
        .summary-section {{
            background: #161b22;
            padding: 30px 40px;
            border-bottom: 1px solid #30363d;
        }}
        
        .summary-section h2 {{
            color: #f0f6fc;
            margin-bottom: 20px;
            font-size: 1.4rem;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
        }}
        
        .stat-card {{
            background: #21262d;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #30363d;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}
        
        .stat-card .number {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        
        .stat-card .label {{
            color: #8b949e;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .stat-card.critical .number {{ color: #f85149; }}
        .stat-card.high .number {{ color: #f0883e; }}
        .stat-card.medium .number {{ color: #d29922; }}
        .stat-card.low .number {{ color: #3fb950; }}
        
        .scan-section {{
            background: #161b22;
            padding: 30px 40px;
            border-bottom: 1px solid #30363d;
        }}
        
        .scan-section:last-of-type {{
            border-bottom: none;
        }}
        
        .scan-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 2px solid #30363d;
        }}
        
        .scan-header-left {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        
        .scan-header h3 {{
            color: #f0f6fc;
            font-size: 1.3rem;
            margin: 0;
        }}
        
        .scan-repo-info {{
            display: flex;
            gap: 15px;
            font-size: 0.85rem;
            color: #8b949e;
        }}
        
        .scan-repo-info span {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        
        .scan-meta {{
            display: flex;
            gap: 20px;
            color: #8b949e;
            font-size: 0.9rem;
        }}
        
        .severity-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .severity-badge.critical {{
            background: rgba(248, 81, 73, 0.15);
            color: #f85149;
            border: 1px solid #f85149;
        }}
        
        .severity-badge.high {{
            background: rgba(240, 136, 62, 0.15);
            color: #f0883e;
            border: 1px solid #f0883e;
        }}
        
        .severity-badge.medium {{
            background: rgba(210, 153, 34, 0.15);
            color: #d29922;
            border: 1px solid #d29922;
        }}
        
        .severity-badge.low {{
            background: rgba(63, 185, 80, 0.15);
            color: #3fb950;
            border: 1px solid #3fb950;
        }}
        
        .findings-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        .findings-table th {{
            background: #21262d;
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            color: #c9d1d9;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #30363d;
        }}
        
        .findings-table td {{
            padding: 15px;
            border-bottom: 1px solid #30363d;
            vertical-align: top;
            color: #c9d1d9;
        }}
        
        .findings-table tr:hover {{
            background: #1f2428;
        }}
        
        .finding-type {{
            font-size: 0.8rem;
            color: #8b949e;
            margin-top: 3px;
        }}
        
        .no-findings {{
            text-align: center;
            padding: 40px;
            color: #3fb950;
            font-weight: 500;
        }}
        
        .no-findings .icon {{
            font-size: 2rem;
            margin-bottom: 10px;
        }}
        
        .footer {{
            background: #0d1117;
            color: #8b949e;
            padding: 20px 40px;
            text-align: center;
            font-size: 0.85rem;
            border-top: 1px solid #30363d;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ Security Scan Report</h1>
            <p class="subtitle">Comprehensive security findings across all repositories</p>
            <div class="meta">
                <span>📅 Generated: {generated_time}</span>
                <span>📦 Repos Scanned: {total_repos}</span>
                <span>🔍 Total Findings: {total_findings}</span>
            </div>
        </div>

        <div class="summary-section">
            <h2>📊 Executive Summary</h2>
            <div class="stats-grid">
                <div class="stat-card critical">
                    <div class="number">{severity_totals['CRITICAL']}</div>
                    <div class="label">Critical</div>
                </div>
                <div class="stat-card high">
                    <div class="number">{severity_totals['HIGH']}</div>
                    <div class="label">High</div>
                </div>
                <div class="stat-card medium">
                    <div class="number">{severity_totals['MEDIUM']}</div>
                    <div class="label">Medium</div>
                </div>
                <div class="stat-card low">
                    <div class="number">{severity_totals['LOW']}</div>
                    <div class="label">Low</div>
                </div>
            </div>
        </div>

        {scan_sections_html}

        <div class="footer">
            <p>Report generated by <strong>CICDSECURITY</strong> Scanner</p>
            <p>Tools: OpenGrep | TruffleHog | Trivy (SBOM)</p>
        </div>
    </div>
</body>
</html>'''
        
        # Create response with HTML content
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = f'attachment; filename=security-report-{datetime.now().strftime("%Y%m%d-%H%M%S")}.html'
        
        return response
        
    except Exception as e:
        current_app.logger.exception('Error generating report: %s', e)
        return jsonify({'error': str(e)}), 500


# ============ USER MANAGEMENT ENDPOINTS ============

@bp.route('/api/me')
@require_login
def api_get_current_user():
    """Get current user info"""
    user = get_current_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    
    return jsonify({
        'status': 'success',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'full_name': user.full_name,
            'department': user.department
        }
    })


@bp.route('/api/users', methods=['GET'])
@require_login
@require_admin
def api_get_users():
    """Get all users (admin only)"""
    from models.database import User
    
    users = User.query.order_by(User.created_at.desc()).all()
    
    return jsonify({
        'status': 'success',
        'users': [{
             'id': u.id,
             'username': u.username,
             'email': u.email,
             'role': u.role,
             'full_name': u.full_name,
             'department': u.department,
             'created_at': u.created_at.isoformat() if u.created_at else None,
             'last_login': u.last_login.isoformat() if u.last_login else None
        } for u in users]
    })


@bp.route('/api/users', methods=['POST'])
@require_login
@require_admin
def api_create_user():
    """Create a new user (admin only)"""
    from models.database import User
    from validators.input_validators import validate_username, validate_email, validate_password_strength
    
    data = request.get_json()
    
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'operator')
    full_name = data.get('full_name', '').strip()
    department = data.get('department', '').strip()
    
    # Validation
    if not username:
        return jsonify({'status': 'error', 'message': 'Username is required'}), 400
    
    valid, msg = validate_username(username)
    if not valid:
        return jsonify({'status': 'error', 'message': msg}), 400
    
    if not password:
        return jsonify({'status': 'error', 'message': 'Password is required'}), 400
    
    valid, msg = validate_password_strength(password, username)
    if not valid:
        return jsonify({'status': 'error', 'message': msg}), 400
    
    # Check if username exists
    if User.query.filter_by(username=username).first():
        return jsonify({'status': 'error', 'message': 'Username already exists'}), 400
    
    # Check if email exists
    if email and User.query.filter_by(email=email).first():
        return jsonify({'status': 'error', 'message': 'Email already exists'}), 400
    
    # Validate role
    if role not in ['admin', 'operator']:
        role = 'operator'
    
    try:
        # Create user
        new_user = User(
            username=username,
            email=email if email else None,
            password_hash=User.hash_password(password),
            role=role,
            full_name=full_name if full_name else None,
            department=department if department else None,
            is_first_login=True
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        current_app.logger.info(f'User {username} created by admin')
        
        return jsonify({
            'status': 'success',
            'message': f'User {username} created successfully',
            'user': {
                'id': new_user.id,
                'username': new_user.username,
                'role': new_user.role
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/users/<int:user_id>', methods=['PUT'])
@require_login
@require_admin
def api_update_user(user_id):
    """Update user (admin only)"""
    from models.database import User
    
    data = request.get_json()
    
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    
    # Update fields
    if 'email' in data and data['email']:
        if User.query.filter(User.email == data['email'], User.id != user_id).first():
            return jsonify({'status': 'error', 'message': 'Email already in use'}), 400
        user.email = data['email']
    
    if 'role' in data and data['role'] in ['admin', 'viewer', 'operator']:
        user.role = data['role']
    
    if 'full_name' in data:
        user.full_name = data['full_name'] if data['full_name'] else None
    
    if 'department' in data:
        user.department = data['department'] if data['department'] else None
    
    try:
        db.session.commit()
        current_app.logger.info(f'User {user.username} updated by admin')
        
        return jsonify({
            'status': 'success',
            'message': 'User updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_login
@require_admin
def api_delete_user(user_id):
    """Delete a user (admin only)"""
    from models.database import User
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    
    # Prevent deleting yourself
    current_user = get_current_user()
    if current_user and current_user.id == user_id:
        return jsonify({'status': 'error', 'message': 'Cannot delete your own account'}), 400
    
    try:
        db.session.delete(user)
        db.session.commit()
        current_app.logger.info(f'User {user.username} deleted by admin')
        
        return jsonify({
            'status': 'success',
            'message': f'User {user.username} has been deleted'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============ GITHUB WEBHOOK LISTENER ============

@bp.route('/github/webhook', methods=['POST'])
def github_webhook():
    """
    GitHub Webhook endpoint - receives webhook events from GitHub App
    Verifies signature and processes events
    
    Returns:
        JSON response with status
    """
    from modules.env_config import env_config
    
    try:
        # Get the webhook secret from .env
        webhook_secret = env_config.get_github_credentials().get('github_webhook_secret', '')
        
        if not webhook_secret:
            current_app.logger.warning('GitHub webhook received but GITHUB_WEBHOOK_SECRET not configured')
            return jsonify({'status': 'error', 'message': 'Webhook secret not configured'}), 400
        
        # Verify webhook signature
        signature_header = request.headers.get('X-Hub-Signature-256', '')
        
        if not signature_header:
            current_app.logger.warning('GitHub webhook received without signature header')
            return jsonify({'status': 'error', 'message': 'No signature provided'}), 400
        
        # Get raw body for signature verification
        body = request.get_data()
        
        # Compute HMAC-SHA256
        computed_signature = 'sha256=' + hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Verify signature
        if not hmac.compare_digest(signature_header, computed_signature):
            current_app.logger.warning(f'GitHub webhook signature verification failed')
            return jsonify({'status': 'error', 'message': 'Signature verification failed'}), 403
        
        # Parse JSON payload
        payload = request.get_json()
        
        if not payload:
            return jsonify({'status': 'error', 'message': 'No JSON payload'}), 400
        
        # Get event type from headers
        event_type = request.headers.get('X-GitHub-Event', 'unknown')
        
        # Log the webhook event
        current_app.logger.info(f'GitHub webhook received: {event_type}')
        current_app.logger.debug(f'Webhook payload: {json.dumps(payload, indent=2)}')
        
        # Handle different event types
        if event_type == 'pull_request':
            return handle_pr_webhook(payload)
        elif event_type == 'push':
            return handle_push_webhook(payload)
        elif event_type == 'issues':
            return handle_issues_webhook(payload)
        elif event_type == 'ping':
            return jsonify({'status': 'success', 'message': 'Webhook configured successfully'}), 200
        else:
            current_app.logger.debug(f'Unhandled webhook event type: {event_type}')
            return jsonify({'status': 'success', 'message': f'Event type {event_type} received but not processed'}), 200
    
    except Exception as e:
        current_app.logger.error(f'Error processing GitHub webhook: {str(e)}')
        return jsonify({'status': 'error', 'message': f'Error processing webhook: {str(e)}'}), 500


def handle_pr_webhook(payload):
    """
    Handle pull_request events from GitHub webhook
    Automatically triggers security scans on PR open and synchronize events
    
    Args:
        payload: GitHub webhook payload
    
    Returns:
        JSON response with status
    """
    try:
        from modules.pr_scan_handler import trigger_pr_scan
        from modules.repos import get_repositories
        
        action = payload.get('action', '')
        pr = payload.get('pull_request', {})
        repo = payload.get('repository', {})
        
        pr_number = pr.get('number', 'unknown')
        pr_title = pr.get('title', '')
        pr_head_sha = pr.get('head', {}).get('sha', '')
        repo_name = repo.get('name', 'unknown')
        repo_owner = repo.get('owner', {}).get('login', 'unknown')
        repo_id = repo.get('id', '')
        repo_url = repo.get('clone_url', f'https://github.com/{repo_owner}/{repo_name}.git')
        
        current_app.logger.info(f'Pull Request {action}: {repo_owner}/{repo_name}#{pr_number} - {pr_title}')
        
        # Handle different PR actions
        if action == 'opened':
            current_app.logger.info(f'PR #{pr_number} opened in {repo_owner}/{repo_name}, triggering scan...')
            
            # Trigger security scan
            scan_result = trigger_pr_scan(
                repo_id=repo_id,
                repo_name=repo_name,
                repo_owner=repo_owner,
                repo_url=repo_url,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_head_sha=pr_head_sha,
                scan_types=['sats', 'sbom', 'secret']  # Default scan types
            )
            
            current_app.logger.info(f'PR scan triggered: {scan_result.get("scan_id")}')
            
            return jsonify({
                'status': 'success',
                'message': f'PR #{pr_number} opened, scan triggered',
                'pr_number': pr_number,
                'repo': f'{repo_owner}/{repo_name}',
                'scan_id': scan_result.get('scan_id'),
                'scan_status': 'pending'
            }), 200
        
        elif action == 'synchronize':
            current_app.logger.info(f'PR #{pr_number} synchronized (new commits), triggering re-scan...')
            
            # Trigger new scan for updated PR
            scan_result = trigger_pr_scan(
                repo_id=repo_id,
                repo_name=repo_name,
                repo_owner=repo_owner,
                repo_url=repo_url,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_head_sha=pr_head_sha,
                scan_types=['sats', 'sbom', 'secret']
            )
            
            current_app.logger.info(f'PR re-scan triggered: {scan_result.get("scan_id")}')
            
            return jsonify({
                'status': 'success',
                'message': f'PR #{pr_number} synchronized, re-scan triggered',
                'pr_number': pr_number,
                'repo': f'{repo_owner}/{repo_name}',
                'scan_id': scan_result.get('scan_id'),
                'scan_status': 'pending'
            }), 200
        
        elif action == 'closed':
            current_app.logger.info(f'PR #{pr_number} closed')
            # Could archive/cleanup PR scan results here if needed
            
            return jsonify({
                'status': 'success',
                'message': f'PR #{pr_number} closed',
                'pr_number': pr_number,
                'repo': f'{repo_owner}/{repo_name}'
            }), 200
        
        else:
            # Other PR actions (edited, assigned, labeled, etc.) - no action needed
            return jsonify({
                'status': 'success',
                'message': f'PR event {action} received but not processed',
                'pr_number': pr_number,
                'repo': f'{repo_owner}/{repo_name}'
            }), 200
    
    except Exception as e:
        current_app.logger.error(f'Error handling PR webhook: {str(e)}')
        import traceback
        current_app.logger.exception(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500


def handle_push_webhook(payload):
    """
    Handle push events from GitHub webhook
    
    Args:
        payload: GitHub webhook payload
    
    Returns:
        JSON response with status
    """
    try:
        repo = payload.get('repository', {})
        ref = payload.get('ref', '')
        branch = ref.replace('refs/heads/', '')
        
        repo_name = repo.get('name', 'unknown')
        repo_owner = repo.get('owner', {}).get('login', 'unknown')
        
        current_app.logger.info(f'Push to {repo_owner}/{repo_name}:{branch}')
        
        return jsonify({
            'status': 'success',
            'message': f'Push event processed',
            'repo': f'{repo_owner}/{repo_name}',
            'branch': branch
        }), 200
    
    except Exception as e:
        current_app.logger.error(f'Error handling push webhook: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


def handle_issues_webhook(payload):
    """
    Handle issues events from GitHub webhook
    
    Args:
        payload: GitHub webhook payload
    
    Returns:
        JSON response with status
    """
    try:
        action = payload.get('action', '')
        issue = payload.get('issue', {})
        repo = payload.get('repository', {})
        
        issue_number = issue.get('number', 'unknown')
        issue_title = issue.get('title', '')
        repo_name = repo.get('name', 'unknown')
        repo_owner = repo.get('owner', {}).get('login', 'unknown')
        
        current_app.logger.info(f'Issue {action}: {repo_owner}/{repo_name}#{issue_number} - {issue_title}')
        
        return jsonify({
            'status': 'success',
            'message': f'Issue event {action} processed',
            'issue_number': issue_number,
            'repo': f'{repo_owner}/{repo_name}'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f'Error handling issues webhook: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500
