"""Run QA commands with UTC command/outcome logs and redacted text artifacts.

Usage: python3 docs/qa/2026-10-02/run_logged.py GROUP LABEL -- command args...
GROUP is coordinator, backend, frontend, ux, security, or review.
"""

import datetime as dt
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent


def redact(value):
    value = re.sub(r"(?i)(authorization\s*[:=]\s*)([^\n]+)", r"\1[REDACTED]", value)
    value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b", "[REDACTED]", value)
    value = re.sub(r"(?i)((?:password|api_key|api_secret|access_token|secret_key)\s*[:=]\s*)['\"][^'\"\n]+['\"]", r"\1'[REDACTED]'", value)
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", "[REDACTED]", value)
    return value


def main():
    group, label, separator, *command = sys.argv[1:]
    if separator != "--" or not command:
        raise SystemExit("Expected GROUP LABEL -- command args...")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe_label = re.sub(r"[^A-Za-z0-9_-]", "-", label)
    artifact = ROOT / "artifacts" / f"{group}-{safe_label}-{uuid.uuid4().hex[:8]}.txt"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    log = ROOT / f"{group.upper()}-SESSION.md"
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "SHELL", "LANG", "LC_ALL", "SYSTEMROOT") if key in os.environ}
    env.update({"UV_CACHE_DIR": "/private/tmp/grann-qa-20261002/uv-cache", "PIP_CACHE_DIR": "/private/tmp/grann-qa-20261002/pip-cache", "npm_config_cache": "/private/tmp/grann-qa-20261002/npm-cache", "PW_TEST_CONNECT_WS_ENDPOINT": "ws://127.0.0.1:3950/", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT.parents[2]), "QA_OFFLINE": "1"})
    with log.open("a") as handle:
        handle.write(f"\n### {stamp} — {label}\n\nCommand (argv): `{redact(repr(command))}`\n\n")
    started = time.monotonic()
    result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    output = redact(result.stdout)
    artifact.write_text(output)
    outcome = f"Exit {result.returncode}; {time.monotonic() - started:.2f}s; [output](artifacts/{artifact.name})."
    with log.open("a") as handle:
        handle.write(outcome + "\n")
    print(output, end="")
    print(outcome)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
