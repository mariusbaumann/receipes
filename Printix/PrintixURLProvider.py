#!/usr/local/autopkg/python
"""AutoPkg processor that retrieves the Printix Mac client download URL for a given tenant."""

import json
import subprocess

from autopkglib import Processor, ProcessorError

__all__ = ["PrintixURLProvider"]

TENANT_API = "https://api.printix.net/v1/tenants/{hostname}"


class PrintixURLProvider(Processor):
    """Looks up the Printix tenant by subdomain, then returns the Mac client DMG URL and version.

    Calls api.printix.net/v1/tenants/{PRINTIX_TENANT}.printix.net to resolve the tenant UUID,
    then queries the px:software HAL link to find the MAC CLIENT DMG download path.
    """

    description = __doc__
    input_variables = {
        "PRINTIX_TENANT": {
            "required": True,
            "description": (
                "Printix tenant subdomain — the hostname prefix of the download page. "
                "E.g. 'acme' for https://acme.printix.net/download/. "
                "This is customer-specific and must be set in a recipe override."
            ),
        },
    }
    output_variables = {
        "url": {
            "description": "Download URL for the Printix Mac client DMG.",
        },
        "version": {
            "description": "Version string of the available Printix Mac client.",
        },
    }

    def _curl_json(self, url):
        """Fetch a URL as JSON using the system curl."""
        cmd = [
            "/usr/bin/curl", "-sL",
            "-H", "Accept: application/json",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ProcessorError(f"curl failed (exit {result.returncode}): {result.stderr}")
        if not result.stdout.strip():
            raise ProcessorError(f"Empty response from {url}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as err:
            raise ProcessorError(f"Failed to parse JSON from {url}: {err}") from err

    def main(self):
        tenant = self.env.get("PRINTIX_TENANT", "").strip()
        if not tenant:
            raise ProcessorError(
                "PRINTIX_TENANT is not set. "
                "Add it to a recipe override with your Printix tenant subdomain "
                "(e.g. 'acme' for https://acme.printix.net)."
            )

        hostname = f"{tenant}.printix.net"

        # Step 1: Resolve tenant UUID and px:software link.
        tenant_data = self._curl_json(TENANT_API.format(hostname=hostname))
        software_href = (
            tenant_data.get("_links", {})
            .get("px:software", {})
            .get("href")
        )
        if not software_href:
            raise ProcessorError(
                f"px:software link not found in tenant response for {hostname}. "
                "Check that PRINTIX_TENANT is correct."
            )

        # Step 2: Fetch software list and find the MAC CLIENT entry.
        software_data = self._curl_json(software_href)
        resources = software_data.get("_embedded", {}).get("px:softwareResources", [])

        mac_client = next(
            (r for r in resources if r.get("os") == "MAC" and r.get("appl") == "CLIENT"),
            None,
        )
        if not mac_client:
            raise ProcessorError(
                f"No Mac client entry found in software resources for tenant {hostname}."
            )

        version = mac_client.get("version")
        files = mac_client.get("files", [])
        if not files:
            raise ProcessorError(
                f"Mac client version {version} has no downloadable files listed."
            )

        download_url = files[0]["path"]

        self.env["url"] = download_url
        self.env["version"] = version
        self.output(f"Printix Mac client version: {version}")
        self.output(f"Download URL: {download_url}")


if __name__ == "__main__":
    PROCESSOR = PrintixURLProvider()
    PROCESSOR.execute_shell()
