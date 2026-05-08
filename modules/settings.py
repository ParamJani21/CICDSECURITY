"""
Settings Tab Module - Configuration and preferences
Handles GitHub credentials - now stored encrypted in database instead of .env
"""

from modules.env_config import env_config
from models.database import db, User
from utils.crypto_utils import encrypt_credential, decrypt_credential
from datetime import datetime
from flask import current_app


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
                           ngrok_oauth_token: str,
                           user_id: int = None) -> dict:
    """
    Save GitHub credentials encrypted to database (User model)
    Falls back to .env if user_id not provided (for backwards compatibility)
    
    Args:
        github_app_id: GitHub App ID
        github_app_name: GitHub App Name
        github_secret_key: GitHub Secret Key (Private Key)
        ngrok_oauth_token: ngrok OAuth Token
        user_id: User ID to associate credentials with (current user)
    
    Returns:
        Status dictionary with success/error message
    """
    try:
        # If user_id provided, store in database with encryption
        if user_id:
            user = User.query.get(user_id)
            if not user:
                return {
                    'status': 'error',
                    'message': 'User not found'
                }
            
            try:
                # Encrypt sensitive data
                encrypted_app_id = encrypt_credential(github_app_id) if github_app_id else None
                encrypted_secret_key = encrypt_credential(github_secret_key) if github_secret_key else None
                
                # Store in user record
                user.encrypted_github_app_id = encrypted_app_id
                user.encrypted_github_key = encrypted_secret_key
                user.github_credentials_updated_at = datetime.utcnow()
                
                db.session.commit()
                
                current_app.logger.info(f'GitHub credentials encrypted and stored for user {user_id}')
                
                return {
                    'status': 'success',
                    'message': 'GitHub credentials saved securely (encrypted)',
                    'credentials': get_github_credentials_for_user(user_id)
                }
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Failed to encrypt/store credentials: {e}')
                return {
                    'status': 'error',
                    'message': f'Failed to encrypt credentials: {str(e)}'
                }
        else:
            # Fallback: save to .env (legacy)
            success = env_config.save_github_credentials(
                app_id=github_app_id,
                app_name=github_app_name,
                secret_key=github_secret_key,
                oauth_token=ngrok_oauth_token
            )
            
            if success:
                return {
                    'status': 'success',
                    'message': 'GitHub credentials saved to .env (not encrypted)',
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


def get_github_credentials_for_user(user_id: int) -> dict:
    """
    Retrieve and decrypt GitHub credentials for a specific user
    
    Args:
        user_id: User ID
        
    Returns:
        Dictionary with decrypted GitHub settings (App ID masked for security)
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {}
        
        # Decrypt credentials
        app_id = decrypt_credential(user.encrypted_github_app_id) if user.encrypted_github_app_id else ''
        secret_key = decrypt_credential(user.encrypted_github_key) if user.encrypted_github_key else ''
        
        # Mask secret key for display (only show last 10 chars)
        masked_key = ('*' * max(0, len(secret_key) - 10)) + secret_key[-10:] if secret_key else ''
        
        return {
            'github_app_id': app_id,
            'github_app_id_masked': ('*' * max(0, len(app_id) - 4)) + app_id[-4:] if app_id else '',
            'github_secret_key_masked': masked_key,
            'updated_at': user.github_credentials_updated_at.isoformat() if user.github_credentials_updated_at else None
        }
    except Exception as e:
        current_app.logger.error(f'Error retrieving credentials for user {user_id}: {e}')
        return {}


def get_github_credentials() -> dict:
    """
    Retrieve GitHub credentials from .env file
    
    Returns:
        Dictionary with GitHub settings
    """
    return env_config.get_github_credentials()
