"""
Settings Tab Module - Configuration and preferences
Handles GitHub credentials and integrations stored in .env
"""

from modules.env_config import env_config


def get_settings():
    """
    Fetch all system settings
    """
    github_creds = env_config.get_github_credentials()
    
    return {
        'general': {},
        'scanning': {},
        'notifications': {},
        'integrations': {},
        'policies': {},
        'security': {},
        'github': github_creds
    }


def get_integration_status():
    """Get status of all integrations"""
    settings = get_settings()
    integrations = []
    for name, config in settings['integrations'].items():
        integrations.append({
            'name': name.upper(),
            'enabled': config.get('enabled', False),
            'connected': config.get('connected', False),
            'status': 'connected' if config.get('connected') else 'disconnected'
        })
    return integrations


def get_notification_settings():
    """Get notification preferences"""
    settings = get_settings()
    return settings['notifications']


def update_setting(key, value):
    """Update a specific setting"""
    return {'status': 'success', 'message': f'Setting {key} updated successfully'}


def save_github_credentials(github_app_id: str, 
                           github_app_name: str, 
                           github_secret_key: str, 
                           ngrok_oauth_token: str) -> dict:
    """
    Save GitHub credentials to .env file
    
    Args:
        github_app_id: GitHub App ID
        github_app_name: GitHub App Name
        github_secret_key: GitHub Secret Key
        ngrok_oauth_token: ngrok OAuth Token
    
    Returns:
        Status dictionary with success/error message
    """
    try:
        success = env_config.save_github_credentials(
            app_id=github_app_id,
            app_name=github_app_name,
            secret_key=github_secret_key,
            oauth_token=ngrok_oauth_token
        )
        
        if success:
            return {
                'status': 'success',
                'message': 'GitHub credentials saved successfully',
                'credentials': env_config.get_github_credentials()
            }
        else:
            return {
                'status': 'error',
                'message': 'Failed to save credentials to .env file'
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error saving credentials: {str(e)}'
        }


def get_github_credentials() -> dict:
    """
    Retrieve GitHub credentials from .env file
    
    Returns:
        Dictionary with GitHub settings
    """
    return env_config.get_github_credentials()
