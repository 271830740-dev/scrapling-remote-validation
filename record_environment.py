"""Record non-secret GitHub runner provenance, never the full environment."""
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

keys = ["GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion"]
record = {key: os.environ.get(key) for key in keys}
record.update(recorded_at_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(), system=platform.system(), real_hotel_quote_records=0)
if record["GITHUB_ACTIONS"] != "true" or record["RUNNER_ENVIRONMENT"] != "github-hosted":
    raise RuntimeError("Expected a GitHub-hosted Actions runner")
Path("evidence/environment.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
