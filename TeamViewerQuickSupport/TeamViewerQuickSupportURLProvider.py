#!/usr/local/autopkg/python
"""AutoPkg processor that retrieves the download URL for a TeamViewer QuickSupport custom module."""

import json
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = ["TeamViewerQuickSupportURLProvider"]

API_URL = "https://get.teamviewer.com/api/CustomDesign"


class TeamViewerQuickSupportURLProvider(Processor):
    """Retrieves the time-limited download URL for a TeamViewer QuickSupport custom module."""

    description = __doc__
    input_variables = {
        "TV_CONFIG_ID": {
            "required": True,
            "description": (
                "TeamViewer QuickSupport ConfigId. "
                "Found as `var configId` in the JavaScript of the download page "
                "(e.g. https://get.teamviewer.com/<id>)."
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

    def main(self):
        config_id = self.env["TV_CONFIG_ID"]
        version = self.env.get("TV_VERSION", "15")

        payload = json.dumps({
            "ConfigId": config_id,
            "Version": version,
            "IsCustomModule": True,
            "Subdomain": "1",
            "ConnectionId": "",
        }).encode("utf-8")

        req = urllib.request.Request(
            API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AutoPkg",
            },
        )

        try:
            with urllib.request.urlopen(req) as resp:
                download_url = json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            raise ProcessorError(f"Failed to retrieve TeamViewer download URL: {err}") from err

        self.env["url"] = download_url
        self.output(f"Download URL: {download_url}")


if __name__ == "__main__":
    PROCESSOR = TeamViewerQuickSupportURLProvider()
    PROCESSOR.execute_shell()
