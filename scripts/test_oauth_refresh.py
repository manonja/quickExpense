#!/usr/bin/env python3
"""Test OAuth token refresh behavior.

This script helps test the OAuth token refresh functionality by:
1. Checking current token status
2. Forcing a token refresh
3. Monitoring automatic refresh behavior
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quickexpense.core.config import Settings
from quickexpense.models.quickbooks_oauth import (
    QuickBooksOAuthConfig,
    QuickBooksTokenInfo,
)
from quickexpense.services.quickbooks import QuickBooksClient
from quickexpense.services.quickbooks_oauth import QuickBooksOAuthManager

# Load environment variables
load_dotenv()


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_token_info(tokens: QuickBooksTokenInfo) -> None:
    """Print token information."""
    now = datetime.now(UTC)

    print("\n" + "=" * 50)
    print(f"{Colors.BOLD}Token Information{Colors.RESET}")
    print("=" * 50)

    # Access token
    access_expires_in = tokens.access_token_expires_in
    access_expired = tokens.access_token_expired

    print(f"\n{Colors.BOLD}Access Token:{Colors.RESET}")
    print(f"  Token: {tokens.access_token[:20]}...{tokens.access_token[-10:]}")
    print(f"  Expires at: {tokens.access_token_expires_at.isoformat()}")
    print(
        f"  Expires in: {access_expires_in:.0f} seconds ({access_expires_in/60:.1f} minutes)"
    )
    print(f"  Status: {'🔴 EXPIRED' if access_expired else '🟢 VALID'}")

    # Refresh token
    refresh_expires_in = tokens.refresh_token_expires_in
    refresh_expired = tokens.refresh_token_expired

    print(f"\n{Colors.BOLD}Refresh Token:{Colors.RESET}")
    print(f"  Token: {tokens.refresh_token[:20]}...{tokens.refresh_token[-10:]}")
    print(f"  Expires at: {tokens.refresh_token_expires_at.isoformat()}")
    print(
        f"  Expires in: {refresh_expires_in:.0f} seconds ({refresh_expires_in/86400:.1f} days)"
    )
    print(f"  Status: {'🔴 EXPIRED' if refresh_expired else '🟢 VALID'}")

    # Refresh recommendation
    if tokens.should_refresh(300):  # 5 minute buffer
        print(
            f"\n{Colors.YELLOW}⚠ Token should be refreshed (within 5 minute buffer){Colors.RESET}"
        )
    else:
        print(f"\n{Colors.GREEN}✓ Token is fresh{Colors.RESET}")


async def test_oauth_refresh() -> None:
    """Test OAuth token refresh functionality."""
    print(f"\n{Colors.BOLD}OAuth Token Refresh Test{Colors.RESET}")
    print("=" * 50)

    # Load settings
    settings = Settings()

    # Create OAuth configuration
    oauth_config = QuickBooksOAuthConfig(
        client_id=settings.qb_client_id,
        client_secret=settings.qb_client_secret,
        redirect_uri=settings.qb_redirect_uri,
        environment=settings.qb_oauth_environment,
    )

    # Create initial token info (assuming current tokens from env)
    initial_tokens = QuickBooksTokenInfo(
        access_token=settings.qb_access_token,
        refresh_token=settings.qb_refresh_token,
        # Assume tokens were just obtained
        access_token_expires_at=datetime.now(UTC).replace(second=0, microsecond=0),
        refresh_token_expires_at=datetime.now(UTC).replace(second=0, microsecond=0),
    )

    # Create OAuth manager
    async with QuickBooksOAuthManager(
        config=oauth_config,
        initial_tokens=initial_tokens,
    ) as oauth_manager:
        print("\n1. Current token status:")
        print_token_info(oauth_manager.tokens)

        # Test QuickBooks connection
        print("\n2. Testing QuickBooks connection...")
        try:
            qb_client = QuickBooksClient(
                base_url=settings.qb_base_url,
                company_id=settings.qb_company_id,
                oauth_manager=oauth_manager,
            )

            result = await qb_client.test_connection()
            print_success(f"Connected to: {result.get('CompanyName', 'Unknown')}")

        except Exception as e:
            print_error(f"Connection failed: {e}")
            return

        # Force token refresh
        print("\n3. Forcing token refresh...")
        try:
            new_tokens = await oauth_manager.refresh_access_token()
            print_success("Token refresh successful!")
            print_token_info(new_tokens)

            # Save new tokens to .env
            save_tokens = (
                input("\nSave new tokens to .env? (y/N): ").lower().strip() == "y"
            )
            if save_tokens:
                env_path = Path(__file__).parent.parent / ".env"
                update_env_tokens(env_path, new_tokens)
                print_success("Tokens saved to .env")

        except Exception as e:
            print_error(f"Token refresh failed: {e}")
            return

        # Test connection with new tokens
        print("\n4. Testing connection with new tokens...")
        try:
            result = await qb_client.test_connection()
            print_success(f"Still connected to: {result.get('CompanyName', 'Unknown')}")
        except Exception as e:
            print_error(f"Connection failed with new tokens: {e}")

        await qb_client.close()


def update_env_tokens(env_path: Path, tokens: QuickBooksTokenInfo) -> None:
    """Update tokens in .env file."""
    if not env_path.exists():
        print_error(f".env file not found at {env_path}")
        return

    # Read current .env
    with open(env_path) as f:
        lines = f.readlines()

    # Update token lines
    new_lines = []
    for line in lines:
        if line.startswith("QB_ACCESS_TOKEN="):
            new_lines.append(f"QB_ACCESS_TOKEN={tokens.access_token}\n")
        elif line.startswith("QB_REFRESH_TOKEN="):
            new_lines.append(f"QB_REFRESH_TOKEN={tokens.refresh_token}\n")
        else:
            new_lines.append(line)

    # Write back
    with open(env_path, "w") as f:
        f.writelines(new_lines)


async def monitor_token_refresh() -> None:
    """Monitor automatic token refresh behavior."""
    print(f"\n{Colors.BOLD}Token Refresh Monitor{Colors.RESET}")
    print("=" * 50)
    print("This will monitor token status every 30 seconds.")
    print("Press Ctrl+C to stop.\n")

    settings = Settings()
    oauth_config = QuickBooksOAuthConfig(
        client_id=settings.qb_client_id,
        client_secret=settings.qb_client_secret,
        redirect_uri=settings.qb_redirect_uri,
    )

    initial_tokens = QuickBooksTokenInfo(
        access_token=settings.qb_access_token,
        refresh_token=settings.qb_refresh_token,
        access_token_expires_at=datetime.now(UTC).replace(second=0, microsecond=0),
        refresh_token_expires_at=datetime.now(UTC).replace(second=0, microsecond=0),
    )

    async with QuickBooksOAuthManager(
        config=oauth_config,
        initial_tokens=initial_tokens,
    ) as oauth_manager:
        refresh_count = 0
        last_token = oauth_manager.tokens.access_token

        try:
            while True:
                current_token = oauth_manager.tokens.access_token

                # Check if token changed
                if current_token != last_token:
                    refresh_count += 1
                    print(
                        f"\n{Colors.GREEN}Token refreshed! (Count: {refresh_count}){Colors.RESET}"
                    )
                    last_token = current_token

                # Show current status
                expires_in = oauth_manager.tokens.access_token_expires_in
                should_refresh = oauth_manager.tokens.should_refresh(300)

                status = (
                    f"Token expires in: {expires_in:.0f}s "
                    f"({'SHOULD REFRESH' if should_refresh else 'OK'})"
                )
                print(f"\r{status}", end="", flush=True)

                await asyncio.sleep(30)

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Monitoring stopped.{Colors.RESET}")
            print(f"Total refreshes observed: {refresh_count}")


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "monitor":
        await monitor_token_refresh()
    else:
        await test_oauth_refresh()


if __name__ == "__main__":
    asyncio.run(main())
