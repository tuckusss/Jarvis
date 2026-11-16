from unittest import TestCase
from jarvis.updates import evaluate_release, parse_version


class UpdateDiscoveryTests(TestCase):
    def test_strict_semver(self):
        self.assertEqual(parse_version("v0.7.0"), (0, 7, 0))
        self.assertIsNone(parse_version("jarvis-ci-4384-1"))

    def test_reject_draft_unsigned_dev_build(self):
        result = evaluate_release({
            "tag_name": "v0.8.0",
            "draft": True, "prerelease": False,
            "html_url": "https://github.com/tuckusss/Jarvis/releases/tag/v0.8.0"
        }, "0.7.0")
        self.assertFalse(result["update"])

    def test_discover_stable_release_without_autoinstall(self):
        result = evaluate_release({
            "tag_name": "v0.8.0",
            "draft": False, "prerelease": False,
            "html_url": "https://github.com/tuckusss/Jarvis/releases/tag/v0.8.0"
        }, "0.7.0")
        self.assertTrue(result["update"])
        self.assertTrue(result["manual_only"])

    def test_reject_third_party_release_url(self):
        result = evaluate_release({
            "tag_name": "v0.8.0",
            "draft": False, "prerelease": False,
            "html_url": "https://attacker.example/v0.8.0"
        }, "0.7.0")
        self.assertFalse(result["update"])
