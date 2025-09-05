"""Tests for token storage service."""

import json
from pathlib import Path
from typing import Any

import pytest

from quickexpense.services.token_store import TokenStore


class TestTokenStore:
    """Tests for TokenStore class."""

    @pytest.fixture
    def temp_token_file(self, tmp_path):
        """Create a temporary token file path."""
        return str(tmp_path / "tokens.json")

    @pytest.fixture
    def token_store(self, temp_token_file):
        """Create a TokenStore instance with temp file."""
        return TokenStore(temp_token_file)

    @pytest.fixture
    def sample_tokens(self):
        """Sample token data."""
        return {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8640000,
            "token_type": "bearer",
            "company_id": "test_company_123",
        }

    def test_init_creates_directory(self, tmp_path):
        """Test that TokenStore creates the data directory."""
        token_path = tmp_path / "data" / "tokens.json"
        TokenStore(str(token_path))
        assert token_path.parent.exists()

    def test_load_tokens_file_not_exists(self, token_store):
        """Test loading tokens when file doesn't exist."""
        result = token_store.load_tokens()
        assert result is None

    def test_save_and_load_tokens(self, token_store, sample_tokens):
        """Test saving and loading tokens."""
        # Save tokens
        assert token_store.save_tokens(sample_tokens) is True

        # Load tokens
        loaded = token_store.load_tokens()
        assert loaded is not None
        assert loaded["access_token"] == sample_tokens["access_token"]
        assert loaded["refresh_token"] == sample_tokens["refresh_token"]
        assert loaded["company_id"] == sample_tokens["company_id"]
        assert "saved_at" in loaded  # Should add timestamp

    def test_save_tokens_adds_timestamp(self, token_store, sample_tokens):
        """Test that saving tokens adds a timestamp."""
        token_store.save_tokens(sample_tokens)
        loaded = token_store.load_tokens()
        assert "saved_at" in loaded
        # Should be ISO format with timezone
        assert loaded["saved_at"].endswith("Z") or "+" in loaded["saved_at"]

    def test_clear_tokens(self, token_store, sample_tokens):
        """Test clearing tokens."""
        # Save tokens first
        token_store.save_tokens(sample_tokens)
        assert Path(token_store.file_path).exists()

        # Clear tokens
        assert token_store.clear_tokens() is True
        assert not Path(token_store.file_path).exists()

        # Clearing non-existent file should also return True
        assert token_store.clear_tokens() is True

    def test_update_tokens(self, token_store, sample_tokens):
        """Test updating specific token fields."""
        # Save initial tokens
        token_store.save_tokens(sample_tokens)

        # Update specific fields
        assert (
            token_store.update_tokens(
                access_token="new_access_token",
                expires_in=7200,
            )
            is True
        )

        # Load and verify
        loaded = token_store.load_tokens()
        assert loaded["access_token"] == "new_access_token"
        assert loaded["expires_in"] == 7200
        # Other fields should remain unchanged
        assert loaded["refresh_token"] == sample_tokens["refresh_token"]
        assert loaded["company_id"] == sample_tokens["company_id"]

    def test_update_tokens_creates_file(self, token_store):
        """Test that update_tokens creates file if it doesn't exist."""
        assert (
            token_store.update_tokens(
                access_token="new_token",
                company_id="123",
            )
            is True
        )

        loaded = token_store.load_tokens()
        assert loaded["access_token"] == "new_token"
        assert loaded["company_id"] == "123"

    def test_load_tokens_invalid_json(self, token_store):
        """Test loading tokens with invalid JSON."""
        # Write invalid JSON
        with open(token_store.file_path, "w") as f:
            f.write("{invalid json}")

        result = token_store.load_tokens()
        assert result is None

    def test_save_tokens_pretty_print(self, token_store, sample_tokens):
        """Test that tokens are saved with pretty formatting."""
        token_store.save_tokens(sample_tokens)

        # Read the file directly
        with open(token_store.file_path) as f:
            content = f.read()

        # Should be pretty-printed with indentation
        assert "  " in content  # Has indentation
        assert content.count("\n") > len(sample_tokens)  # Multiple lines

    def test_save_tokens_sorted_keys(self, token_store, sample_tokens):
        """Test that tokens are saved with sorted keys."""
        token_store.save_tokens(sample_tokens)

        with open(token_store.file_path) as f:
            data = json.load(f)

        # Keys should be in alphabetical order
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_error_handling_save_tokens(self, token_store, sample_tokens, monkeypatch):
        """Test error handling when saving tokens fails."""

        def mock_open(*args: Any, **kwargs: Any) -> Any:
            raise PermissionError("No write permission")

        monkeypatch.setattr("builtins.open", mock_open)
        assert token_store.save_tokens(sample_tokens) is False

    def test_error_handling_load_tokens(self, token_store, monkeypatch):
        """Test error handling when loading tokens fails."""
        # Create a file first
        token_store.save_tokens({"test": "data"})

        def mock_open(*args: Any, **kwargs: Any) -> Any:
            raise PermissionError("No read permission")

        monkeypatch.setattr("builtins.open", mock_open)
        assert token_store.load_tokens() is None

    def test_error_handling_clear_tokens(self, token_store, sample_tokens, monkeypatch):
        """Test error handling when clearing tokens fails."""
        # Save tokens first
        token_store.save_tokens(sample_tokens)

        def mock_unlink(self):
            raise PermissionError("No delete permission")

        monkeypatch.setattr(Path, "unlink", mock_unlink)
        assert token_store.clear_tokens() is False
