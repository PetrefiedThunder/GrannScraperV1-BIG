"""Exit status of `scraper validate` for job configuration files."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from scraper.cli.main import cli


def _validate(config_path: Path) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, ["validate", str(config_path)])
    return result.exit_code, result.stdout, result.stderr


def test_validate_valid_config_exits_zero(tmp_path: Path) -> None:
    """A config the models accept exits 0 and reports success."""
    config = tmp_path / "ok.yaml"
    config.write_text(
        "name: test_job\nstart_url: https://example.com\n",
        encoding="utf-8",
    )

    exit_code, stdout, _stderr = _validate(config)

    assert exit_code == 0
    assert "is valid" in stdout


@pytest.mark.parametrize(
    "body",
    [
        "name: test_job\n",
        "name: test_job\nstart_url: ftp://example.com\n",
        (
            "name: test_job\nstart_url: https://example.com\n"
            "pagination:\n  mode: next_button\n"
        ),
        "name: [\n",
        "",
        "just a string\n",
    ],
)
def test_validate_invalid_config_exits_nonzero(tmp_path: Path, body: str) -> None:
    """Schema, model, YAML, and non-mapping configs print an error and exit 1."""
    config = tmp_path / "bad.yaml"
    config.write_text(body, encoding="utf-8")

    exit_code, stdout, _stderr = _validate(config)

    assert exit_code == 1
    assert "is invalid" in stdout
    assert "Error:" in stdout


def test_validate_missing_file_exits_nonzero(tmp_path: Path) -> None:
    """A path that does not exist is a Click usage error, not success."""
    exit_code, _stdout, stderr = _validate(tmp_path / "missing.yaml")

    assert exit_code == 2
    assert "does not exist" in stderr
