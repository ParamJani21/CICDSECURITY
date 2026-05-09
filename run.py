#!/usr/bin/env python3
"""
CICDSECURITY Application Runner
Starts ngrok tunnel with .env token and Flask development server
"""

import os
import sys
import signal
import time
import subprocess
import json
import requests
from pathlib import Path

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.env_config import env_config
from app import create_app

# Global variables for cleanup
ngrok_process = None
ngrok_tunnel_url = None


def load_env():
    """Load environment variables from .env file"""
    env_vars = env_config.read_env()
    return env_vars


def get_ngrok_token():
    """Get ngrok token from .env"""
    env_vars = load_env()
    token = env_vars.get('NGROK_OAUTH_TOKEN', '')
    
    if not token:
        print("⚠️  WARNING: NGROK_OAUTH_TOKEN not found in .env")
        print("   Skipping ngrok tunnel. Set NGROK_OAUTH_TOKEN to enable automatic tunneling.")
        return None
    
    return token


def authenticate_ngrok(token):
    """Authenticate ngrok with the provided token"""
    try:
        print(f"🔐 Authenticating ngrok with token...")
        result = subprocess.run(
            ['ngrok', 'config', 'add-authtoken', token],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ ngrok authentication successful")
            return True
        else:
            print(f"❌ ngrok authentication failed: {result.stderr}")
            return False
    
    except FileNotFoundError:
        print("❌ ERROR: ngrok command not found. Install ngrok from https://ngrok.com")
        return False
    except Exception as e:
        print(f"❌ ERROR: Failed to authenticate ngrok: {str(e)}")
        return False


def start_ngrok_tunnel(port=5000):
    """
    Start ngrok tunnel on specified port
    
    Args:
        port: Flask server port (default: 5000)
    
    Returns:
        Tuple: (ngrok_process, public_url) or (None, None) if failed
    """
    global ngrok_process, ngrok_tunnel_url
    
    try:
        print(f"🚀 Starting ngrok tunnel on port {port}...")
        
        # Start ngrok tunnel
        ngrok_process = subprocess.Popen(
            ['ngrok', 'http', str(port), '--log=stdout'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("   Waiting for tunnel to initialize...")
        time.sleep(3)  # Give ngrok time to start
        
        # Try to get tunnel URL from ngrok API
        try:
            response = requests.get('http://localhost:4040/api/tunnels', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('tunnels'):
                    for tunnel in data['tunnels']:
                        if tunnel.get('proto') == 'https':
                            ngrok_tunnel_url = tunnel.get('public_url')
                            print(f"✅ ngrok tunnel started successfully!")
                            print(f"\n{'='*70}")
                            print(f"🌐 Public URL: {ngrok_tunnel_url}")
                            print(f"{'='*70}\n")
                            return ngrok_process, ngrok_tunnel_url
        except Exception as e:
            print(f"⚠️  Could not get tunnel URL from ngrok API: {str(e)}")
            print("   But ngrok tunnel may still be running. Check logs.")
        
        # If we got here, ngrok started but we couldn't get the URL
        print("✅ ngrok tunnel process started")
        print("   Check ngrok logs for public URL")
        return ngrok_process, None
    
    except FileNotFoundError:
        print("❌ ERROR: ngrok command not found. Install ngrok from https://ngrok.com")
        return None, None
    except Exception as e:
        print(f"❌ ERROR: Failed to start ngrok tunnel: {str(e)}")
        return None, None


def check_ngrok_status():
    """Check if ngrok tunnel is still running"""
    global ngrok_process
    
    if ngrok_process is None:
        return False
    
    return ngrok_process.poll() is None


def cleanup_ngrok():
    """Stop ngrok tunnel"""
    global ngrok_process
    
    if ngrok_process:
        print("\n🛑 Stopping ngrok tunnel...")
        try:
            ngrok_process.terminate()
            try:
                ngrok_process.wait(timeout=3)
                print("✅ ngrok tunnel stopped")
            except subprocess.TimeoutExpired:
                ngrok_process.kill()
                print("✅ ngrok tunnel killed")
        except Exception as e:
            print(f"⚠️  Error stopping ngrok: {str(e)}")
        finally:
            ngrok_process = None


def signal_handler(signum, frame):
    """Handle Ctrl+C and other signals"""
    print("\n\n🛑 Received interrupt signal...")
    cleanup_ngrok()
    print("👋 Goodbye!")
    sys.exit(0)


def print_startup_info():
    """Print startup information"""
    print("\n" + "="*70)
    print(" CICDSECURITY - GitHub Security Scanning Dashboard")
    print("="*70)
    print(f"📝 Environment: Development")
    print(f"🔧 Flask Debug: Enabled")
    print(f"🌐 Local URL: http://localhost:5000")
    print("="*70 + "\n")


def main():
    """Main entry point"""
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print_startup_info()
    
    # Check for ngrok token and start tunnel if available
    ngrok_token = get_ngrok_token()
    
    if ngrok_token:
        print("🔌 ngrok Configuration:")
        print(f"   Token found: {ngrok_token[:10]}...{ngrok_token[-5:]}")
        
        # Authenticate ngrok
        if authenticate_ngrok(ngrok_token):
            # Start tunnel
            process, url = start_ngrok_tunnel(port=5000)
            if process:
                print("💡 GitHub Webhook URL:")
                if url:
                    webhook_url = f"{url}/github/webhook"
                    print(f"   {webhook_url}")
                else:
                    print("   (Check ngrok logs for public URL)")
            else:
                print("⚠️  ngrok tunnel failed to start. Continuing with local Flask server.")
    else:
        print("⏭️  Skipping ngrok tunnel. Using local Flask server only.")
    
    print("\n📖 Documentation:")
    print("   - Webhook Setup: See WEBHOOK_QUICK_START.md")
    print("   - Full Guide: See WEBHOOK_IMPLEMENTATION.md")
    print("\n" + "="*70)
    print("🎯 Starting Flask application...")
    print("="*70 + "\n")
    
    try:
        # Create and run Flask app
        app = create_app()
        
        # Run Flask development server
        # debug=True but use_reloader=False to avoid inotify issues
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False
        )
    
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted...")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        cleanup_ngrok()
        print("👋 Application stopped")
        sys.exit(0)


if __name__ == '__main__':
    main()
