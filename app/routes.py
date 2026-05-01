from flask import Blueprint, render_template, jsonify, request, current_app
import sys
import os

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.overview import get_overview_data
from modules.repos import get_repositories, get_repository_stats
from modules.history import get_scan_history, get_history_stats, get_scan_details
from modules.settings import (get_settings, get_integration_status, 
                             get_github_credentials, save_github_credentials)
from modules.scan_controller import trigger_scan

bp = Blueprint('main', __name__)


@bp.route('/')
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
def api_overview():
    """API endpoint for overview data"""
    return jsonify(get_overview_data())


@bp.route('/api/repos')
def api_repos():
    """API endpoint for repositories"""
    return jsonify({
        'repositories': get_repositories(),
        'stats': get_repository_stats()
    })


@bp.route('/api/history')
def api_history():
    """API endpoint for scan history"""
    return jsonify({
        'history': get_scan_history(),
        'stats': get_history_stats()
    })


@bp.route('/api/history/<scan_id>')
def api_scan_details(scan_id):
    """API endpoint for getting detailed scan information"""
    details = get_scan_details(scan_id)
    if details:
        return jsonify(details)
    return jsonify({'error': 'Scan not found'}), 404


@bp.route('/api/history/delete', methods=['POST'])
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
def api_scan_all_repos():
    """API endpoint to scan all repositories from GitHub App."""
    try:
        from modules.repos import get_repositories
        
        payload = request.get_json(silent=True) or {}
        scan_types = payload.get('scan_types', ['sats', 'sbom', 'secret'])
        
        current_app.logger.info('Scan all repos requested from %s | scan_types=%s', request.remote_addr, scan_types)
        
        # Get all repositories from GitHub App
        repos = get_repositories()
        
        if not repos or len(repos) == 0:
            return jsonify({'status': 'error', 'message': 'No repositories found'}), 404
        
        triggered_scans = []
        failed_scans = []
        
        for repo in repos:
            try:
                repo_id = repo.get('id', '')
                repo_name = repo.get('name', '')
                repo_owner = repo.get('owner', '')
                repo_url = repo.get('url', f'https://github.com/{repo_owner}/{repo_name}.git')
                repo_branch = repo.get('branch', 'main')
                
                if not repo_id or not repo_name or not repo_owner:
                    failed_scans.append({'repo': f"{repo.get('owner', 'unknown')}/{repo.get('name', 'unknown')}", 'error': 'Missing required fields'})
                    continue
                
                # Trigger scan for this repo
                result = trigger_scan(repo_id, repo_name, repo_owner, repo_url, repo_branch, scan_types)
                
                triggered_scans.append({
                    'repo_id': repo_id,
                    'repo_name': repo_name,
                    'repo_owner': repo_owner,
                    'status': result.get('status', 'unknown'),
                    'scan_id': result.get('scan_id', '')
                })
                
                current_app.logger.info('✓ Triggered scan for %s/%s', repo_owner, repo_name)
                
            except Exception as scan_err:
                current_app.logger.error('Failed to scan %s: %s', repo.get('name', 'unknown'), str(scan_err))
                failed_scans.append({'repo': f"{repo.get('owner', 'unknown')}/{repo.get('name', 'unknown')}", 'error': str(scan_err)})
        
        return jsonify({
            'status': 'success',
            'message': f'Triggered {len(triggered_scans)} scans',
            'total_repos': len(repos),
            'triggered': triggered_scans,
            'failed': failed_scans
        })
        
    except Exception as e:
        current_app.logger.exception('Error scanning all repos: %s', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/runtime')
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
def api_settings():
    """API endpoint for settings"""
    return jsonify({
        'settings': get_settings(),
        'integrations': get_integration_status()
    })


@bp.route('/api/settings/github', methods=['GET'])
def api_get_github_credentials():
    """API endpoint to retrieve GitHub credentials"""
    try:
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
def api_save_github_credentials():
    """API endpoint to save GitHub credentials"""
    try:
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
            ngrok_oauth_token=data.get('ngrok_oauth_token', '')
        )
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error saving credentials: {str(e)}'
        }), 500


@bp.route('/api/log', methods=['POST'])
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
def api_export_report():
    """Generate and download security scan report"""
    import json
    from datetime import datetime
    from flask import make_response
    
    try:
        # Get logs directory
        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(module_dir)
        logs_dir = os.path.join(project_root, 'logs', 'tool-output')
        
        if not os.path.exists(logs_dir):
            return jsonify({'error': 'No scan data found'}), 404
        
        # Read all merged.json files
        scans = []
        for scan_dir in os.listdir(logs_dir):
            scan_path = os.path.join(logs_dir, scan_dir)
            if not os.path.isdir(scan_path):
                continue
            
            merged_file = os.path.join(scan_path, 'merged.json')
            if os.path.exists(merged_file):
                try:
                    with open(merged_file, 'r') as f:
                        scan_data = json.load(f)
                        scan_data['scan_id'] = scan_dir
                        scans.append(scan_data)
                except Exception:
                    continue
        
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