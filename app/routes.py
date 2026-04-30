from flask import Blueprint, render_template, jsonify, request, current_app
import sys
import os

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.overview import get_overview_data
from modules.repos import get_repositories, get_repository_stats
from modules.history import get_scan_history, get_history_stats
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

        if not repo_id:
            return jsonify({'status': 'error', 'message': 'repo_id is required'}), 400
        
        if not repo_name or not repo_owner:
            return jsonify({'status': 'error', 'message': 'repo_name and repo_owner are required'}), 400
        
        if not repo_url:
            repo_url = f'https://github.com/{repo_owner}/{repo_name}.git'

        current_app.logger.info('Manual scan requested for repo_id=%s (%s/%s) from %s', 
                               repo_id, repo_owner, repo_name, request.remote_addr)
        
        # Trigger the actual scan using the controller
        result = trigger_scan(repo_id, repo_name, repo_owner, repo_url, repo_branch)
        
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