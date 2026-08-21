#!/usr/bin/env python3
"""Regression checks for third-party names that contain the old brand substring."""

from html.parser import HTMLParser
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parent.parent


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._current = [dict(attrs).get("href"), []]

    def handle_data(self, data):
        if self._current is not None:
            self._current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._current is not None:
            href, text = self._current
            self.anchors.append((href, "".join(text).strip()))
            self._current = None


class ExternalLinkBrandSafetyTests(unittest.TestCase):
    def test_third_party_live_wallpaper_brands_are_not_rebranded(self):
        parser = AnchorParser()
        parser.feed((ROOT / "template.html").read_text())
        links = dict(parser.anchors)

        expected = {
            "https://livewallp.com/": "LiveWallp ↗",
            "https://livewallpapers4free.com/": "LiveWallpapers4Free ↗",
            "https://mylivewallpapers.com/": "MyLiveWallpapers ↗",
        }
        for url, label in expected.items():
            self.assertEqual(links.get(url), label, f"third-party link was renamed: {url}")

    def test_deploy_runs_external_link_regression_check(self):
        deploy_script = (ROOT / "deploy.sh").read_text()
        self.assertIn(
            "python3 tools/test_external_links.py",
            deploy_script,
            "site deployment must run the third-party brand regression check",
        )


if __name__ == "__main__":
    unittest.main()
