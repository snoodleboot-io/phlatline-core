"""Cloud upload — posts CompletedRun to Phlatline Cloud when token is configured.

Called from the CLI after a scan if PHLATLINE_CLOUD_TOKEN is set.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phlatline.sdk.models import CompletedRun

_DEFAULT_API_BASE = "https://api.phlatline.io"


def upload_run(completed: "CompletedRun", token: str | None = None) -> str | None:
    """Upload a completed run to Phlatline Cloud.

    Args:
        completed: The finished run payload.
        token: Bearer token override. Falls back to PHLATLINE_CLOUD_TOKEN env var.

    Returns:
        The run URL string if upload succeeded, None if no token is configured.
    """
    bearer = token or os.environ.get("PHLATLINE_CLOUD_TOKEN")
    if not bearer:
        return None

    import httpx  # optional dependency — only needed for cloud upload

    api_base = os.environ.get("PHLATLINE_CLOUD_API", _DEFAULT_API_BASE)
    url = f"{api_base}/v1/runs"

    payload = completed.model_dump(by_alias=True)
    resp = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json().get("run_url")
