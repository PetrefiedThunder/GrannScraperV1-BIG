"""Developer-experience contracts using only temporary files and blocked sockets."""

from pathlib import Path
import re
import socket
from unittest.mock import AsyncMock

from click.testing import CliRunner
import pytest
import yaml

from scraper.cli.main import cli
from scraper.config.models import ScrapeJob


@pytest.fixture(autouse=True)
def isolate_cli_home_and_network(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    def blocked(*args, **kwargs):
        raise AssertionError("QA UX tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


def test_cli_help_lists_documented_commands():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for name in ("easy", "massive", "wizard", "run", "list", "validate", "serve"):
        assert name in result.output


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="UX-007: list command shadows built-in list and cannot enumerate saved jobs")
def test_saved_jobs_are_listed(tmp_path):
    jobs = tmp_path / ".grandma-scraper" / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "qa-sample.yaml").write_text(yaml.safe_dump({"name": "QA fictional saved job", "start_url": "https://catalogue.example.invalid"}))
    result = CliRunner().invoke(cli, ["list"])
    assert result.exit_code == 0, result.output
    assert "QA fictional saved job" in result.output


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="UX-008: README uses a config pathname but scraper run only accepts a saved-job name")
def test_readme_config_path_can_be_run(monkeypatch, tmp_path):
    config = tmp_path / "config" / "my_job.yaml"
    config.parent.mkdir()
    config.write_text(yaml.safe_dump({"name": "QA README sample", "start_url": "https://catalogue.example.invalid"}))
    runner = AsyncMock()
    monkeypatch.setattr("scraper.cli.main._run_job", runner)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["run", "config/my_job.yaml"])
    assert result.exit_code == 0, result.output
    assert runner.await_count == 1, result.output


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="UX-008: README's flat browser/pagination/export keys are silently ignored")
def test_readme_job_config_preserves_documented_settings():
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()
    example = re.search(r"```yaml\n(# config/my_job.yaml.*?)```", readme, re.DOTALL)
    assert example is not None
    job = ScrapeJob.model_validate(yaml.safe_load(example.group(1)))
    assert job.browser.enabled is True
    assert job.pagination.mode == "next_button"
    assert job.pagination.max_pages == 50
    assert job.export.formats == ["csv", "json", "excel"]


def test_easy_mode_cancel_explains_outcome_without_network():
    result = CliRunner().invoke(cli, ["easy", "https://catalogue.example.invalid"], input="titles\njust one\nqa-file\nn\n")
    assert result.exit_code == 0
    assert "maybe next time" in result.output


def test_valid_saved_job_name_reaches_runner(monkeypatch, tmp_path):
    jobs = tmp_path / ".grandma-scraper" / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "qa-sample.yaml").write_text(yaml.safe_dump({"name": "QA fictional saved job", "start_url": "https://catalogue.example.invalid"}))
    runner = AsyncMock()
    monkeypatch.setattr("scraper.cli.main._run_job", runner)
    result = CliRunner().invoke(cli, ["run", "qa-sample"])
    assert result.exit_code == 0
    assert runner.await_count == 1
