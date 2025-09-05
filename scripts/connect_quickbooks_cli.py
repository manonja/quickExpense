#!/usr/bin/env python3
"""QuickBooks OAuth 2.0 CLI Setup Tool.

Connects QuickBooks accounts and obtains OAuth tokens for API access.
Uses environment variables for security - no hardcoded credentials.
"""

import base64
import http.server
import json
import os
import secrets
import socketserver
import sys
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

# 🔧 CONFIGURATION - Load from environment variables for security
CLIENT_ID = os.getenv("QB_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv(
    "QB_REDIRECT_URI", "http://localhost:8000/api/quickbooks/callback"
)
PORT = int(os.getenv("QB_OAUTH_PORT", "8000"))

# QuickBooks OAuth 2.0 endpoints
AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


class SimpleOAuthHandler(http.server.BaseHTTPRequestHandler):
    # Store state for CSRF protection
    oauth_state = None

    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/":
            self.show_start_page()
        elif parsed_url.path == "/api/quickbooks/callback":
            self.handle_callback(parsed_url.query)
        else:
            self.send_response(404)
            self.end_headers()

    def show_start_page(self):
        """Show the authorization start page"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        # Generate and store state for CSRF protection
        SimpleOAuthHandler.oauth_state = secrets.token_urlsafe(32)

        # Build authorization URL with proper encoding
        params = {
            "client_id": CLIENT_ID,
            "scope": "com.intuit.quickbooks.accounting",
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "access_type": "offline",
            "state": SimpleOAuthHandler.oauth_state,
        }
        auth_url = f"{AUTH_URL}?{urlencode(params)}"

        html = f"""
        <html>
        <head><title>QuickBooks OAuth Setup</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h2>🚀 QuickBooks OAuth Setup</h2>
            <p><strong>Step 1:</strong> Click the button below to connect to QuickBooks</p>
            <p><a href="{auth_url}" style="background: #0077C5; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Connect to QuickBooks</a></p>

            <hr style="margin: 30px 0;">

            <h3>📋 Current Settings:</h3>
            <ul>
                <li><strong>Client ID:</strong> {CLIENT_ID}</li>
                <li><strong>Redirect URI:</strong> {REDIRECT_URI}</li>
                <li><strong>Environment:</strong> Sandbox</li>
            </ul>

            <div style="background: #f0f0f0; padding: 15px; border-radius: 5px; margin-top: 20px;">
                <strong>⚠️ Make sure:</strong>
                <ul>
                    <li>You've updated CLIENT_ID and CLIENT_SECRET in this script</li>
                    <li>Your QuickBooks app has redirect URI: <code>{REDIRECT_URI}</code></li>
                    <li>You're using a sandbox company for testing</li>
                </ul>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def handle_callback(self, query_string):
        """Handle the OAuth callback"""
        query_params = parse_qs(query_string)

        if "error" in query_params:
            self.show_error_page(query_params["error"][0])
            return

        if "code" not in query_params:
            self.show_error_page("Missing authorization code")
            return

        # Verify state parameter for CSRF protection
        received_state = query_params.get("state", [None])[0]
        if received_state != SimpleOAuthHandler.oauth_state:
            self.show_error_page("Invalid state parameter - possible CSRF attack")
            return

        auth_code = query_params["code"][0]
        company_id = query_params.get("realmId", [None])[0]

        print(f"✅ Got authorization code: {auth_code[:20]}...")
        print(f"✅ Company ID: {company_id}")

        try:
            tokens = self.exchange_code_for_tokens(auth_code)
            self.show_success_page(tokens, company_id)
            self.create_env_file(tokens, company_id)
        except Exception as e:
            print(f"❌ Token exchange failed: {e}")
            self.show_error_page(f"Token exchange failed: {e}")

    def exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access token"""
        # Create Basic Auth header (Client ID:Client Secret encoded in base64)
        credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        # Prepare form data
        post_data = urlencode(
            {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": REDIRECT_URI,
            }
        )

        # Make token request
        request = Request(TOKEN_URL)
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        request.add_header("Authorization", f"Basic {b64_credentials}")
        request.data = post_data.encode()

        with urlopen(request) as response:
            return json.loads(response.read().decode())

    def show_success_page(self, tokens, company_id):
        """Show success page with tokens"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")
        expires_in = tokens.get("expires_in", "unknown")
        refresh_expires_in = tokens.get("x_refresh_token_expires_in", "unknown")

        html = f"""
        <html>
        <head><title>OAuth Success!</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
            <h2>🎉 Success! You're connected to QuickBooks</h2>

            <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <strong>✅ .env file has been created/updated with your tokens!</strong>
            </div>

            <h3>📊 Token Information:</h3>
            <ul>
                <li><strong>Company ID:</strong> {company_id}</li>
                <li><strong>Access Token Expires in:</strong> {expires_in} seconds (~{int(expires_in) // 3600} hour)</li>
                <li><strong>Refresh Token Expires in:</strong> {refresh_expires_in} seconds (~{int(refresh_expires_in) // 86400} days)</li>
            </ul>

            <h3>🧪 Test Your Setup:</h3>
            <p>Your QuickExpense app should now work with automatic token refresh!</p>
            <code style="background: #f8f9fa; padding: 10px; display: block; border-radius: 5px;">
                # Start the app
                uv run fastapi dev src/quickexpense/main.py

                # Test connection
                curl http://localhost:8000/api/v1/test-connection
            </code>

            <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin-top: 20px;">
                <strong>💡 Important Notes:</strong>
                <ul>
                    <li>The app will automatically refresh your access token before it expires</li>
                    <li>Refresh tokens rotate - each use generates a new one</li>
                    <li>Make sure to use the app at least once every 100 days to keep tokens active</li>
                </ul>
            </div>

            <p><em>You can close this window now!</em></p>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

        # Print to console for easy copying
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! QuickBooks OAuth tokens obtained")
        print("=" * 60)
        print(f"Company ID: {company_id}")
        print(f"Access token expires in: {expires_in} seconds")
        print(f"Refresh token expires in: {refresh_expires_in} seconds")
        print("=" * 60)
        print("✅ .env file updated - your app now has:")
        print("  - Automatic token refresh before expiry")
        print("  - Retry logic for failed requests")
        print("  - Background token management")
        print("=" * 60)

    def show_error_page(self, error_msg):
        """Show error page"""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        html = f"""
        <html>
        <head><title>OAuth Error</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h2>❌ OAuth Error</h2>
            <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px;">
                <strong>Error:</strong> {error_msg}
            </div>
            <p><a href="/" style="color: #007bff;">← Try Again</a></p>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def create_env_file(self, tokens, company_id):
        """Create or update .env file with OAuth tokens"""
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )

        # Read existing .env if it exists
        existing_env = {}
        if os.path.exists(env_path):
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            existing_env[key] = value
            except Exception as e:
                print(f"⚠️ Warning: Could not read existing .env: {e}")

        # Update with new tokens
        existing_env.update(
            {
                "QB_BASE_URL": existing_env.get(
                    "QB_BASE_URL", "https://sandbox-quickbooks.api.intuit.com"
                ),
                "QB_CLIENT_ID": CLIENT_ID,
                "QB_CLIENT_SECRET": CLIENT_SECRET,
                "QB_REDIRECT_URI": REDIRECT_URI,
                "QB_COMPANY_ID": company_id,
                "QB_ACCESS_TOKEN": tokens.get("access_token", ""),
                "QB_REFRESH_TOKEN": tokens.get("refresh_token", ""),
            }
        )

        # Preserve Gemini settings if they exist
        env_content = """# QuickBooks API Configuration
# Generated/Updated by connect_quickbooks_cli.py

# QuickBooks OAuth Configuration
"""

        # Write QuickBooks settings
        for key in [
            "QB_BASE_URL",
            "QB_CLIENT_ID",
            "QB_CLIENT_SECRET",
            "QB_REDIRECT_URI",
            "QB_COMPANY_ID",
            "QB_ACCESS_TOKEN",
            "QB_REFRESH_TOKEN",
        ]:
            if key in existing_env:
                env_content += f"{key}={existing_env[key]}\n"

        # Add token expiry info
        env_content += f"""\n# Token Information
# Access token expires in: {tokens.get('expires_in', 'unknown')} seconds from generation
# Refresh token expires in: {tokens.get('x_refresh_token_expires_in', 'unknown')} seconds from generation
# Generated at: {json.dumps(tokens).get('timestamp', 'now')}
"""

        # Preserve other settings (like Gemini)
        other_settings = [
            (k, v) for k, v in existing_env.items() if not k.startswith("QB_")
        ]
        if other_settings:
            env_content += "\n# Other Configuration\n"
            for key, value in other_settings:
                env_content += f"{key}={value}\n"

        try:
            with open(env_path, "w") as f:
                f.write(env_content)
            print(f"✅ .env file updated at: {env_path}")
        except Exception as e:
            print(f"❌ Could not update .env file: {e}")
            print("\nPlease manually add these to your .env file:")
            print(f"QB_COMPANY_ID={company_id}")
            print(f"QB_ACCESS_TOKEN={tokens.get('access_token', '')}")
            print(f"QB_REFRESH_TOKEN={tokens.get('refresh_token', '')}")

    def log_message(self, format, *args):
        # Suppress default HTTP request logging
        pass


def main():
    """Main entry point for QuickBooks OAuth CLI setup."""
    print("🚀 QuickBooks OAuth Connection Tool")
    print("=" * 50)
    print(f"🌐 Server: http://localhost:{PORT}")
    print(f"🔗 Callback: {REDIRECT_URI}")
    print("=" * 50)

    # Validate configuration
    if not CLIENT_ID or not CLIENT_SECRET:
        print("\n❌ CONFIGURATION REQUIRED:")
        print("\nPlease set the following environment variables:")
        print("  QB_CLIENT_ID     - Your QuickBooks OAuth Client ID")
        print("  QB_CLIENT_SECRET - Your QuickBooks OAuth Client Secret")
        print("\nOptional:")
        print(
            "  QB_REDIRECT_URI  - OAuth redirect URI (default: http://localhost:8000/api/quickbooks/callback)"
        )
        print("  QB_OAUTH_PORT    - Local server port (default: 8000)")
        print("\nExample:")
        print("  export QB_CLIENT_ID='your_client_id_here'")
        print("  export QB_CLIENT_SECRET='your_client_secret_here'")
        print(f"  python {sys.argv[0]}")
        print("\nGet your credentials from:")
        print("  https://developer.intuit.com/app/developer/dashboard")
        sys.exit(1)

    print("\n📋 Instructions:")
    print("1. Browser will open automatically")
    print("2. Click 'Connect to QuickBooks'")
    print("3. Log in and select a company (sandbox for testing)")
    print("4. Authorize the application")
    print("5. Tokens will be saved to .env automatically")
    print("\n🔄 Starting OAuth server...\n")

    try:
        with socketserver.TCPServer(("", PORT), SimpleOAuthHandler) as httpd:
            # Auto-open browser
            webbrowser.open(f"http://localhost:{PORT}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 OAuth server stopped")
        print("\nIf successful, your .env file has been updated with:")
        print("  - QB_ACCESS_TOKEN (expires in ~1 hour)")
        print("  - QB_REFRESH_TOKEN (expires in ~100 days)")
        print("  - QB_COMPANY_ID")
        print("\nThe QuickExpense app will automatically manage token refresh!")


if __name__ == "__main__":
    main()
