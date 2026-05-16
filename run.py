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
import webbrowser
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


def save_env_var(key, value):
    """Save environment variable to .env file - uses same logic as env_config"""
    current_vars = env_config.read_env()
    current_vars[key] = value
    env_config.write_env(current_vars)


def check_ngrok_installed():
    """Check if ngrok is installed"""
    try:
        result = subprocess.run(['which', 'ngrok'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def install_ngrok():
    """Auto-install ngrok"""
    print("[*] Installing ngrok...")
    try:
        subprocess.run('wget -q -O /tmp/ngrok.tgz https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz && tar -xzf /tmp/ngrok.tgz -C /usr/local/bin && rm /tmp/ngrok.tgz',
                      shell=True, check=True, timeout=30)
        return True
    except:
        try:
            subprocess.run('wget -q -O /usr/local/bin/ngrok https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64 && chmod +x /usr/local/bin/ngrok',
                          shell=True, timeout=30)
            return check_ngrok_installed()
        except:
            return False


def ask_ngrok_setup():
    """Interactive ngrok setup wizard"""
    env_vars = load_env()
    existing_token = env_vars.get('NGROK_OAUTH_TOKEN', '')
    existing_subdomain = env_vars.get('NGROK_SUBDOMAIN', '')

    # Case 1: Token and subdomain both exist - return immediately
    if existing_token and existing_subdomain:
        return existing_token, existing_subdomain

    # Case 2: Token exists but no subdomain - ask for subdomain
    if existing_token and not existing_subdomain:
        print("\n[!] Subdomain not set")
        print("""
[?] GET DOMAIN:
    1. Go to: https://dashboard.ngrok.com/cloud-edge/domains
    2. Under "Universal Gateway" > "Domains"
    3. Copy your reserved domain (e.g., my-app.ngrok-free.app)
    4. Enter below (only the prefix)
""")
        webbrowser.open('https://dashboard.ngrok.com/cloud-edge/domains')
        while True:
            print("[?] Subdomain (e.g., my-app): ", end="")
            subdomain = input().strip()
            if subdomain:
                break
            print("[!] Subdomain required")
        save_env_var('NGROK_SUBDOMAIN', subdomain)
        print(f"[✓] Saved (domain: {subdomain}.ngrok-free.app)\n")
        return existing_token, subdomain

    # Case 3: No token - run full wizard
    print("\n[!] NGROK_OAUTH_TOKEN not found")

    # Install ngrok if needed
    if not check_ngrok_installed():
        if not install_ngrok():
            print("[!] Install failed")
            return None, None
        print("[✓] ngrok installed")

    if not check_ngrok_installed():
        print("[!] ngrok not found")
        return None, None

    # Get token
    print("""
[?] GET NGROK TOKEN:
    1. Go to: https://dashboard.ngrok.com/get-started/your-authtoken
    2. Login/Signup to ngrok
    3. Copy your authtoken
    4. Paste it below
""")
    try:
        webbrowser.open('https://dashboard.ngrok.com/get-started/your-authtoken')
    except:
        pass
    print("[?] Paste token: ", end="")
    token = input().strip()

    if not token:
        print("[!] No token, skipping ngrok")
        return None, None

    # Get subdomain (mandatory)
    print("""
[?] GET DOMAIN:
    1. Go to: https://dashboard.ngrok.com/cloud-edge/domains
    2. Under "Universal Gateway" > "Domains"
    3. Copy your reserved domain (e.g., my-app.ngrok-free.app)
    4. Enter below (only the prefix, e.g., my-app)
""")
    try:
        webbrowser.open('https://dashboard.ngrok.com/cloud-edge/domains')
    except:
        pass
    while True:
        print("[?] Subdomain (e.g., my-app): ", end="")
        subdomain = input().strip()
        if subdomain:
            break
        print("[!] Subdomain required for permanent webhook URL")

    # Save both
    save_env_var('NGROK_OAUTH_TOKEN', token)
    save_env_var('NGROK_SUBDOMAIN', subdomain)
    print(f"[✓] Saved (domain: {subdomain}.ngrok-free.app)\n")

    return token, subdomain


def authenticate_ngrok(token):
    """Authenticate ngrok with the provided token"""
    try:
        print("🔐 Authenticating ngrok with token...")
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
        print("❌ ERROR: ngrok command not found")
        return False
    except Exception as e:
        print(f"❌ ERROR: Failed to authenticate ngrok: {str(e)}")
        return False


def start_ngrok_tunnel(port=5000, subdomain=None):
    """Start ngrok tunnel on specified port"""
    global ngrok_process, ngrok_tunnel_url

    # Use provided subdomain or fallback to .env
    if not subdomain:
        env_vars = load_env()
        subdomain = env_vars.get('NGROK_SUBDOMAIN', '')

    try:
        print(f"🚀 Starting ngrok tunnel on port {port}...")

        if subdomain:
            print(f"   Using subdomain: {subdomain}")
            ngrok_process = subprocess.Popen(
                ['ngrok', 'http', f'--url={subdomain}.ngrok-free.dev', str(port), '--log=stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        else:
            print("   Using random subdomain")
            ngrok_process = subprocess.Popen(
                ['ngrok', 'http', str(port), '--log=stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

        print("   Waiting for tunnel to initialize...")
        time.sleep(3)

        # Get tunnel URL from ngrok API
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
            print(f"⚠️  Could not get tunnel URL: {str(e)}")

        print("✅ ngrok tunnel process started")
        return ngrok_process, None

    except FileNotFoundError:
        print("❌ ERROR: ngrok command not found")
        return None, None
    except Exception as e:
        print(f"❌ ERROR: Failed to start ngrok tunnel: {str(e)}")
        return None, None


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


def kill_port_5000():
    """Kill any process using port 5000"""
    try:
        subprocess.run('lsof -ti:5000 | xargs -r kill -9', shell=True, timeout=5)
    except:
        pass


def main():
    """Main entry point"""

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print_startup_info()

    # Kill any existing process on port 5000
    print("[*] Checking port 5000...")
    kill_port_5000()

    # ngrok setup
    ngrok_token, ngrok_subdomain = ask_ngrok_setup()

    if ngrok_token:
        if authenticate_ngrok(ngrok_token):
            process, url = start_ngrok_tunnel(port=5000, subdomain=ngrok_subdomain)
            if url:
                webhook_url = f"{url}/github/webhook"
                print(f"[*] Webhook: {webhook_url}")

                # Check if GitHub credentials already exist
                env_vars = load_env()
                if env_vars.get('GITHUB_APP_ID') and env_vars.get('GITHUB_SECRET_KEY') and env_vars.get('GITHUB_WEBHOOK_SECRET'):
                    print("[✓] GitHub App already configured\n")
                else:
                    # Setup GitHub App
                    print("""
[?] SETUP GITHUB APP:
    1. Creating GitHub App with pre-filled details
    2. Then configure permissions and webhook
""")
                    try:
                        webbrowser.open(f'https://github.com/settings/apps/new?name=CICDSECURITY&description=Security+Scanning+Dashboard&url={url}&hook_active=true&hook_url={webhook_url}')
                    except:
                        pass
                    print("[*] GitHub App creation page opened")
                    print("""
    REQUIRED Repository PERMISSIONS:
    - Checks: Read & Write
    - Commit statuses: Read & Write
    - Contents: Read
    - Pull requests: Read & Write

    Subscribe to events :
    - Subscribe to: Pull requests

    After creating:
    1. Download private key (.pem)
    2. Note the App ID
    3. Install on your org/repos
""")
                    print("[?] Press Enter when GitHub App is created...")
                    input()

                    # Ask for GitHub App credentials
                    print("\n[?] Enter GitHub App ID: ", end="")
                    app_id = input().strip()

                    # Read private key from file path
                    while True:
                        print("[?] Path to private key (.pem file): ", end="")
                        pem_path = input().strip()
                        if pem_path and os.path.exists(pem_path):
                            with open(pem_path, 'r') as f:
                                private_key = f.read().strip()
                            break
                        elif pem_path:
                            print("[!] File not found, try again")
                        else:
                            print("[!] Enter path to .pem file")

                    print("[?] Enter webhook secret (same as in GitHub): ", end="")
                    webhook_secret = input().strip()

                    if app_id and private_key and webhook_secret:
                        save_env_var('GITHUB_APP_ID', app_id)
                        save_env_var('GITHUB_APP_NAME', 'CICDSECURITY')
                        # Pass raw newlines - write_env will escape and quote
                        save_env_var('GITHUB_SECRET_KEY', private_key)
                        save_env_var('GITHUB_WEBHOOK_SECRET', webhook_secret)
                        print("[✓] GitHub App credentials saved\n")

    print("="*70)
    print("Starting Flask (http://localhost:5000)... Ctrl+C to stop")
    print("="*70 + "\n")

    try:
        app = create_app()
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
        cleanup_ngrok()
        print("👋 Application stopped")
        sys.exit(0)


if __name__ == '__main__':
    main()