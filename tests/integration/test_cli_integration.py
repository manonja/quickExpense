"""Integration test for CLI functionality."""

# ruff: noqa: S607

from __future__ import annotations

import subprocess
from pathlib import Path


def test_cli_help() -> None:
    """Test that CLI help works."""
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "quickexpense", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "QuickExpense CLI" in result.stdout
    assert "upload" in result.stdout


def test_cli_version() -> None:
    """Test that CLI version works."""
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "quickexpense", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "quickexpense 0.1.0" in result.stdout


def test_upload_help() -> None:
    """Test that upload command help works."""
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "quickexpense", "upload", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Process a single receipt" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--output" in result.stdout


def test_upload_nonexistent_file() -> None:
    """Test upload with non-existent file."""
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "quickexpense", "upload", "nonexistent.jpg"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2  # File validation error
    assert "File not found" in result.stderr


def test_upload_invalid_format() -> None:
    """Test upload with invalid file format."""
    # Create a test file with unsupported format
    test_file = Path("test.pdf")
    test_file.write_text("test")

    try:
        result = subprocess.run(  # noqa: S603
            ["uv", "run", "quickexpense", "upload", "test.pdf"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2  # File validation error
        assert "Unsupported file format" in result.stderr
    finally:
        test_file.unlink()


if __name__ == "__main__":
    print("Running CLI integration tests...")  # noqa: T201
    test_cli_help()
    print("✓ CLI help works")  # noqa: T201

    test_cli_version()
    print("✓ CLI version works")  # noqa: T201

    test_upload_help()
    print("✓ Upload command help works")  # noqa: T201

    test_upload_nonexistent_file()
    print("✓ Non-existent file handling works")  # noqa: T201

    test_upload_invalid_format()
    print("✓ Invalid format handling works")  # noqa: T201

    print("\nAll CLI integration tests passed!")  # noqa: T201
