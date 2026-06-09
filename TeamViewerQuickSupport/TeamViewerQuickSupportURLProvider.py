#!/usr/local/autopkg/python
"""AutoPkg processor that retrieves the download URL for a TeamViewer QuickSupport custom module."""

import json
import re
import subprocess
import tempfile
import os

from autopkglib import Processor, ProcessorError

__all__ = ["TeamViewerQuickSupportURLProvider"]

BASE_URL = "https://get.teamviewer.com"
API_URL = f"{BASE_URL}/api/CustomDesign"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class TeamViewerQuickSupportURLProvider(Processor):
    """Retrieves the time-limited download URL for a TeamViewer QuickSupport custom module.

    Performs a two-step request: first GETs the download page to obtain Cloudflare
    session cookies and the live configId, then POSTs to the TeamViewer API.
    """

    description = __doc__
    input_variables = {
        "TV_SUBDOMAIN": {
            "required": True,
            "description": (
                "The path component of the TeamViewer QuickSupport download URL, "
                "e.g. 'umbag' for https://get.teamviewer.com/umbag."
            ),
        },
        "TV_VERSION": {
            "required": False,
            "default": "15",
            "description": "TeamViewer major version number.",
        },
    }
    output_variables = {
        "url": {
            "description": "Download URL for the TeamViewer QuickSupport zip.",
        },
    }

    def _curl(self, args):
        """Run curl and return stdout. Raises ProcessorError on failure."""
        cmd = ["/usr/bin/curl", "-sL", "-A", USER_AGENT] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ProcessorError(f"curl failed (exit {result.returncode}): {result.stderr}")
        return result.stdout

    def main(self):
        subdomain = self.env["TV_SUBDOMAIN"]
        version = self.env.get("TV_VERSION", "15")
        page_url = f"{BASE_URL}/{subdomain}"

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as jar:
            cookie_jar = jar.name

        try:
            # Step 1: GET the download page to capture Cloudflare cookies and live configId.
            page_html = self._curl(["-c", cookie_jar, page_url])

            match = re.search(r'var\s+configId\s*=\s*["\']([^"\']+)["\']', page_html)
            if not match:
                raise ProcessorError(
                    f"Could not find configId in page source for {page_url}. "
                    "The page structure may have changed."
                )
            config_id = match.group(1)
            self.output(f"Extracted configId: {config_id}")

            # Step 2: POST to the API with the session cookies.
            payload = json.dumps({
                "ConfigId": config_id,
                "Version": version,
                "IsCustomModule": True,
                "Subdomain": "1",
                "ConnectionId": "",
            })

            response = self._curl([
                "-b", cookie_jar,
                "-X", "POST",
                "-H", "Content-Type: application/json; charset=utf-8",
                "-H", f"Referer: {page_url}",
                "-d", payload,
                API_URL,
            ])

            if not response.strip():
                raise ProcessorError(
                    "TeamViewer API returned an empty response. "
                    "The session cookie or configId may be invalid."
                )

            download_url = json.loads(response)
        except ProcessorError:
            raise
        except Exception as err:
            raise ProcessorError(f"Failed to retrieve TeamViewer download URL: {err}") from err
        finally:
            os.unlink(cookie_jar)

        self.env["url"] = download_url
        self.output(f"Download URL: {download_url}")


if __name__ == "__main__":
    PROCESSOR = TeamViewerQuickSupportURLProvider()
    PROCESSOR.execute_shell()
