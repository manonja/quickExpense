"""Token storage service for QuickBooks OAuth tokens."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TokenStore:
    """Simple JSON file-based token storage for single-user prototype."""

    def __init__(self, file_path: str = "data/tokens.json") -> None:
        """Initialize token store.

        Args:
            file_path: Path to tokens JSON file
        """
        self.file_path = Path(file_path)
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load_tokens(self) -> dict[str, Any] | None:
        """Load tokens from JSON file.

        Returns:
            Token data or None if file doesn't exist
        """
        if not self.file_path.exists():
            logger.info("Token file does not exist: %s", self.file_path)
            return None

        try:
            with self.file_path.open(encoding="utf-8") as f:
                tokens: dict[str, Any] = json.load(f)
                logger.info("Loaded tokens from %s", self.file_path)
                return tokens
        except json.JSONDecodeError as e:
            logger.error("Failed to parse token file: %s", e)
            return None
        except Exception as e:
            logger.error("Failed to load tokens: %s", e)
            return None

    def save_tokens(self, tokens: dict[str, Any]) -> bool:
        """Save tokens to JSON file.

        Args:
            tokens: Token data to save

        Returns:
            True if saved successfully
        """
        try:
            # Add timestamp if not present
            if "saved_at" not in tokens:
                tokens["saved_at"] = datetime.now(UTC).isoformat()

            # Pretty print for easier debugging
            with self.file_path.open("w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=2, sort_keys=True)

            logger.info("Saved tokens to %s", self.file_path)
            return True
        except Exception as e:
            logger.error("Failed to save tokens: %s", e)
            return False

    def clear_tokens(self) -> bool:
        """Delete the token file.

        Returns:
            True if deleted successfully or file didn't exist
        """
        try:
            if self.file_path.exists():
                self.file_path.unlink()
                logger.info("Deleted token file: %s", self.file_path)
            return True
        except Exception as e:
            logger.error("Failed to delete token file: %s", e)
            return False

    def update_tokens(self, **kwargs: Any) -> bool:
        """Update specific token fields.

        Args:
            **kwargs: Fields to update

        Returns:
            True if updated successfully
        """
        # Load existing tokens
        tokens = self.load_tokens() or {}

        # Update fields
        tokens.update(kwargs)

        # Save back
        return self.save_tokens(tokens)
