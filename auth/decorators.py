# auth/decorators.py
"""
Authentication decorators for protecting routes
"""

from functools import wraps
from flask import session, jsonify, request, render_template
from datetime import datetime
from models.database import db, User, Session

def require_login(f):
    """
    Decorator to require user to be logged in
    Returns 401 if not authenticated
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user_id in session
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
            else:
                # Redirect to login for HTML requests
                return render_template('login.html', error='Please log in first'), 401
        
        try:
            # Get user from database
            user = User.query.get(session.get('user_id'))
            
            if not user or user.account_status == 'disabled':
                session.clear()
                if request.is_json:
                    return jsonify({'error': 'User not found or disabled'}), 401
                else:
                    return render_template('login.html', error='Your account is disabled'), 401
            
            # Validate session token if it exists
            if 'session_token' in session:
                session_record = Session.query.filter_by(
                    session_token=session['session_token'],
                    user_id=user.id
                ).first()
                
                if not session_record or not session_record.is_valid():
                    session.clear()
                    if request.is_json:
                        return jsonify({'error': 'Session expired'}), 401
                    else:
                        return render_template('login.html', error='Your session has expired'), 401
                
                # Update last activity
                session_record.last_activity = datetime.utcnow()
                db.session.commit()
        
        except Exception as e:
            session.clear()
            if request.is_json:
                return jsonify({'error': 'Session validation failed'}), 401
            else:
                return render_template('login.html', error='Session validation failed'), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_admin(f):
    """
    Decorator to require admin role
    Must be used after @require_login
    Returns 403 if user is not admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check if logged in (require_login decorator should be applied first)
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            user = User.query.get(session.get('user_id'))
            
            if not user or user.role != 'admin':
                return jsonify({'error': 'Admin access required', 'code': 'FORBIDDEN'}), 403
        
        except Exception:
            return jsonify({'error': 'Authorization check failed'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_role(*allowed_roles):
    """
    Decorator to require specific roles
    Usage: @require_role('admin', 'operator')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            try:
                user = User.query.get(session.get('user_id'))
                
                if not user or user.role not in allowed_roles:
                    return jsonify({'error': f'Access denied. Required roles: {", ".join(allowed_roles)}'}), 403
            
            except Exception:
                return jsonify({'error': 'Authorization check failed'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator
