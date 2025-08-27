#!/usr/bin/env python3
"""Simple QuickBooks OAuth 2.0 Setup
Gets you a bearer token for API testing in 3 steps
"""

import base64
import http.server
import json
import secrets
import socketserver
import sys
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

# 🔧 CONFIGURATION - UPDATE THESE WITH YOUR VALUES FROM QUICKBOOKS DEVELOPER DASHBOARD
CLIENT_ID = "AB6w8Z4dFYQqSHsICexm0t0SfQfaeYyKxA2DgbFoVrC8cDVput"
CLIENT_SECRET = "9f0HwGLBCOCvSqkrzPp89nkohUclAjFo130pHbPu"
REDIRECT_URI = "http://localhost:8000/api/quickbooks/callback"
PORT = 8000

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

        html = f"""
        <html>
        <head><title>OAuth Success!</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
            <h2>🎉 Success! You're connected to QuickBooks</h2>

            <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <strong>✅ .env file has been created with your tokens!</strong>
            </div>

            <h3>🔑 Your Bearer Token (for testing):</h3>
            <div style="background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 5px; font-family: monospace; word-break: break-all;">
                {access_token}
            </div>

            <h3>📊 Token Info:</h3>
            <ul>
                <li><strong>Company ID:</strong> {company_id}</li>
                <li><strong>Expires in:</strong> {expires_in} seconds (~1 hour)</li>
                <li><strong>Refresh token:</strong> Available (for automatic renewal)</li>
            </ul>

            <h3>🧪 Test Your Setup:</h3>
            <p>Your FastAPI app should now work! Try:</p>
            <code style="background: #f8f9fa; padding: 10px; display: block; border-radius: 5px;">
                curl http://localhost:8000/test-connection
            </code>

            <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin-top: 20px;">
                <strong>💡 Next Steps:</strong>
                <ol>
                    <li>Start your FastAPI app: <code>python main.py</code></li>
                    <li>Test the connection endpoint</li>
                    <li>Try creating expenses with the receipt flow</li>
                </ol>
            </div>

            <p><em>You can close this window now!</em></p>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

        # Print to console for easy copying
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! Your tokens:")
        print("=" * 60)
        print(f"BEARER TOKEN: {access_token}")
        print(f"COMPANY_ID: {company_id}")
        print(f"EXPIRES_IN: {expires_in} seconds")
        print("=" * 60)
        print("✅ .env file created - your FastAPI app is ready!")
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
        """Create .env file with all necessary variables"""
        env_content = f"""# QuickBooks API Configuration (Generated by OAuth setup)
# Sandbox Environment - Replace URLs for production

# Base Configuration
QB_BASE_URL=https://sandbox-quickbooks.api.intuit.com
QB_CLIENT_ID={CLIENT_ID}
QB_CLIENT_SECRET={CLIENT_SECRET}
QB_REDIRECT_URI={REDIRECT_URI}

# Company & Tokens (from OAuth flow)
QB_COMPANY_ID={company_id}
QB_ACCESS_TOKEN={tokens.get('access_token', '')}
QB_REFRESH_TOKEN={tokens.get('refresh_token', '')}

# Token expires in {tokens.get('expires_in', 'unknown')} seconds from now
# Refresh token expires in {tokens.get('x_refresh_token_expires_in', 'unknown')} seconds from now
"""

        try:
            with open(".env", "w") as f:
                f.write(env_content)
            print("✅ .env file created successfully!")
        except Exception as e:
            print(f"⚠️ Could not create .env file: {e}")

    def log_message(self, format, *args):
        # Suppress default HTTP request logging
        pass


def main():
    print("🚀 Simple QuickBooks OAuth Setup")
    print("=" * 50)
    print(f"🌐 Server: http://localhost:{PORT}")
    print(f"🔗 Callback: {REDIRECT_URI}")
    print("=" * 50)

    # Validate configuration
    if CLIENT_ID == "YOUR_CLIENT_ID_HERE" or CLIENT_SECRET == "YOUR_CLIENT_SECRET_HERE":
        print("\n❌ SETUP REQUIRED:")
        print("   1. Go to: https://developer.intuit.com/app/developer/dashboard")
        print("   2. Create/select your app")
        print("   3. Copy Client ID and Client Secret")
        print("   4. Update CLIENT_ID and CLIENT_SECRET in this file")
        print(f"   5. Add redirect URI: {REDIRECT_URI}")
        sys.exit(1)

    print("\n📋 Instructions:")
    print("1. Browser will open automatically")
    print("2. Click 'Connect to QuickBooks'")
    print("3. Select a sandbox company")
    print("4. Get your bearer token!")
    print("\n🔄 Starting server...\n")

    try:
        with socketserver.TCPServer(("", PORT), SimpleOAuthHandler) as httpd:
            # Auto-open browser
            webbrowser.open(f"http://localhost:{PORT}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped!")
        print("Check your .env file - your tokens should be ready!")


if __name__ == "__main__":
    main()
