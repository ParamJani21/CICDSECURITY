from flask import Flask, request
import logging
from logging.handlers import RotatingFileHandler
import os


def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config['SECRET_KEY'] = 'your-secret-key-here'

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

    # Register scan API blueprint (controls for cloning/scanning)
    try:
        from modules.scan_api import bp as scan_bp
        app.register_blueprint(scan_bp)
    except Exception as e:
        app.logger.warning('Could not register scan_api blueprint: %s', e)

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