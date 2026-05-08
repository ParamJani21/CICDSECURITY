from flask import Flask, request, jsonify, redirect, url_for, session
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import timedelta
import secrets

# Import database and session configuration
from models.database import db
from flask_session import Session as FlaskSession


def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    # Generate or load SECRET_KEY from environment
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    if not SECRET_KEY:
        # Generate a random key for development (not suitable for production)
        SECRET_KEY = secrets.token_hex(32)
        app.logger.warning('No FLASK_SECRET_KEY in environment, generated temporary key')
    
    app.config['SECRET_KEY'] = SECRET_KEY
    
    # Database configuration
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cicdsecurity.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
    app.config['SESSION_COOKIE_NAME'] = 'cicdsec_session'
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    
    # Initialize database
    db.init_app(app)
    
    # Initialize session
    FlaskSession(app)
    
    # Create database tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            
            # Add missing columns to existing tables (for database migrations)
            from sqlalchemy import text
            try:
                # Check if columns exist, if not add them
                result = db.session.execute(text("PRAGMA table_info(users)"))
                columns = [row[1] for row in result.fetchall()]
                
                if 'encrypted_github_app_id' not in columns:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN encrypted_github_app_id TEXT"))
                    app.logger.info('Added column: encrypted_github_app_id')
                if 'encrypted_github_key' not in columns:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN encrypted_github_key TEXT"))
                    app.logger.info('Added column: encrypted_github_key')
                if 'github_credentials_updated_at' not in columns:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN github_credentials_updated_at TIMESTAMP"))
                    app.logger.info('Added column: github_credentials_updated_at')
                if 'full_name' not in columns:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(255)"))
                    app.logger.info('Added column: full_name')
                if 'department' not in columns:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(255)"))
                    app.logger.info('Added column: department')
                if 'is_active' not in columns:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                    app.logger.info('Added column: is_active')
                
                db.session.commit()
            except Exception as col_e:
                app.logger.warning(f'Column migration note: {col_e}')
            
            app.logger.info('Database initialized successfully')
        except Exception as e:
            app.logger.error(f'Failed to initialize database: {e}')
    # Configure logging: console + rotating file
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'app.log')

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

    # File handler
    file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # Attach handlers to app.logger and werkzeug logger
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

    # werkzeug (Flask dev server) logs - suppress DEBUG to reduce inotify spam
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('werkzeug').addHandler(file_handler)
    logging.getLogger('werkzeug').addHandler(console_handler)
    
    # Suppress Flask's file watcher (watchdog) inotify spam
    logging.getLogger('werkzeug.serving').setLevel(logging.WARNING)
    logging.getLogger('werkzeug.security').setLevel(logging.WARNING)
    logging.getLogger('watchdog.observers').setLevel(logging.WARNING)

    # Configure root logger so all modules (control_apis, scan_api, etc) inherit handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress noisy loggers
    logging.getLogger('watchdog').setLevel(logging.WARNING)
    logging.getLogger('watchdog.observers').setLevel(logging.WARNING)
    logging.getLogger('watchdog.observers.inotify_buffer').setLevel(logging.WARNING)

    from app.routes import bp
    app.register_blueprint(bp)
    
    # Register authentication blueprint
    from app.auth_routes import auth_bp
    app.register_blueprint(auth_bp)

    # Register scan API blueprint (controls for cloning/scanning)
    try:
        from modules.scan_api import bp as scan_bp
        app.register_blueprint(scan_bp)
    except Exception as e:
        app.logger.warning('Could not register scan_api blueprint: %s', e)
    
    # Before request - check authentication (skip for auth routes and static files)
    @app.before_request
    def check_authentication():
        """Check if user is authenticated before accessing protected routes"""
        # Skip for static files, auth routes, and login page
        if (request.path.startswith('/static/') or 
            request.path.startswith('/auth/') or 
            request.path in ['/login', '/', '/auth/setup/initial-admin']):
            return
        
        # Check if user is logged in
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            else:
                return redirect(url_for('auth.login_page'))

    # Add security headers
    @app.after_request
    def set_security_headers(response):
        """Set security headers on all responses"""
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        return response

    # Log incoming requests (method, path, remote addr, params/body)
    @app.before_request
    def log_request_info():
        try:
            data = None
            try:
                data = request.get_json(silent=True)
            except Exception:
                data = None
            app.logger.info('Incoming request: %s %s from %s params=%s json=%s',
                            request.method, request.path, request.remote_addr, dict(request.args), data)
        except Exception as e:
            app.logger.exception('Error logging request info: %s', e)

    app.logger.info('App initialized, logging configured. Logs writing to %s', log_path)

    return app