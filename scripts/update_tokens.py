#!/usr/bin/env python3
"""Manually update QuickBooks tokens in .env file."""

import sys
from pathlib import Path


def update_tokens(access_token=None, refresh_token=None):
    """Update tokens in .env file."""
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        print("❌ .env file not found")
        return False

    # Read current .env
    with open(env_path) as f:
        lines = f.readlines()

    # Update tokens
    updated = False
    new_lines = []

    for line in lines:
        if access_token and line.startswith("QB_ACCESS_TOKEN="):
            new_lines.append(f"QB_ACCESS_TOKEN={access_token}\n")
            updated = True
        elif refresh_token and line.startswith("QB_REFRESH_TOKEN="):
            new_lines.append(f"QB_REFRESH_TOKEN={refresh_token}\n")
            updated = True
        else:
            new_lines.append(line)

    if updated:
        # Write back
        with open(env_path, "w") as f:
            f.writelines(new_lines)
        print("✅ Tokens updated in .env")
        return True
    print("❌ No tokens were updated")
    return False


if __name__ == "__main__":
    print("🔑 QuickBooks Token Update Tool")
    print("=" * 50)

    if len(sys.argv) > 1:
        # Command line usage
        access_token = sys.argv[1] if len(sys.argv) > 1 else None
        refresh_token = sys.argv[2] if len(sys.argv) > 2 else None
        update_tokens(access_token, refresh_token)
    else:
        # Interactive mode
        print("\nPaste the new tokens from the OAuth flow:")
        print("(Leave blank to skip updating that token)")

        access_token = input("\n📝 Access Token: ").strip()
        refresh_token = input("📝 Refresh Token: ").strip()

        if not access_token and not refresh_token:
            print("\n❌ No tokens provided")
            sys.exit(1)

        update_tokens(
            access_token if access_token else None,
            refresh_token if refresh_token else None,
        )

        print("\n💡 Now restart the FastAPI server to use the new tokens:")
        print("   uv run fastapi dev src/quickexpense/main.py")
