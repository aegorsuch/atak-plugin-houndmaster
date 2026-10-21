import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.publish_github_release import (
    PublishError,
    RELEASE_TITLE,
    ReleasePublisher,
    update_marker,
)


COMMIT_SHA = "851ba8966e0fd05a2a86764f11c2c863d228d5d8"
APK_NAME = "ATAK-Plugin-Houndmaster-5.6.0-851ba896-civ-release.apk"


class FakeGitHubApi:
    def __init__(self, branch_sha=COMMIT_SHA, body=None, assets=None, corrupt_upload=False):
        self.branch_sha = branch_sha
        self.release = None
        self.assets = {}
        self.next_asset_id = 1
        self.corrupt_upload = corrupt_upload
        self.writes = []
        self.events = []
        if body is not None:
            self.release = {
                "id": 17,
                "upload_url": "https://uploads.github.com/repos/aegorsuch/atak-plugin-houndmaster/releases/17/assets{?name,label}",
                "name": "old title",
                "body": body,
                "draft": False,
                "prerelease": True,
            }
        for name, content in (assets or {}).items():
            self.add_asset(name, content)

    def add_asset(self, name, content):
        asset = {"id": self.next_asset_id, "name": name}
        self.next_asset_id += 1
        self.assets[asset["id"]] = (asset, content)
        return asset

    def list_assets(self, release_id):
        self.writes.append(("list-assets", release_id))
        return [asset for asset, _ in self.assets.values()]

    def request_json(self, method, path, payload=None, allow_not_found=False):
        if path.endswith("/commits/main"):
            return {"sha": self.branch_sha}
        if path.endswith("/releases/tags/takgov-pipeline"):
            return self.release
        if path.endswith("/releases") and method == "POST":
            self.writes.append(("create-release", payload))
            self.release = dict(payload, id=17, upload_url="https://uploads.example/releases/17/assets{?name,label}")
            return self.release
        if path.endswith("/releases/17/assets?per_page=100&page=1"):
            return [asset for asset, _ in self.assets.values()]
        if path.endswith("/releases/17") and method == "PATCH":
            self.writes.append(("update-release", payload))
            self.release.update(payload)
            return self.release
        if path.endswith("/git/ref/tags/takgov-pipeline"):
            if method == "GET":
                return getattr(self, "tag_ref", None)
            self.writes.append(("move-tag", payload))
            self.tag_ref = {"object": {"sha": payload["sha"]}}
            return self.tag_ref
        if path.endswith("/git/refs") and method == "POST":
            self.writes.append(("create-tag", payload))
            self.tag_ref = {"object": {"sha": payload["sha"]}}
            return self.tag_ref
        raise AssertionError(f"Unexpected API request: {method} {path}")

    def upload_asset(self, release, name, asset_path):
        self.writes.append(("upload", name))
        self.events.append("upload")
        content = asset_path.read_bytes()
        if self.corrupt_upload:
            content += b"corrupt"
        return self.add_asset(name, content)

    def download_asset(self, asset_id):
        self.writes.append(("verify", asset_id))
        return self.assets[asset_id][1]

    def delete_asset(self, asset_id):
        self.writes.append(("delete-asset", asset_id))
        del self.assets[asset_id]


class ReleasePublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_cwd = Path.cwd()
        os.chdir(self.temp_dir.name)
        self.apk_path = Path(APK_NAME)
        self.apk_bytes = b"signed apk test content"
        self.apk_path.write_bytes(self.apk_bytes)
        self.env = {
            "CI_SERVER_HOST": "git.tak.gov",
            "CI_PROJECT_PATH": "aegorsuch/atak-plugin-houndmaster",
            "CI_COMMIT_BRANCH": "main",
            "CI_PIPELINE_SOURCE": "push",
            "CI_COMMIT_SHA": COMMIT_SHA,
            "CI_REPOSITORY_URL": "https://git.tak.gov/aegorsuch/atak-plugin-houndmaster.git",
            "GITHUB_RELEASE_TOKEN": "not-a-real-token",
        }

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.temp_dir.cleanup()

    def publisher(self, api):
        return ReleasePublisher(
            self.env,
            api=api,
            head_reader=lambda _: COMMIT_SHA,
            apk_verifier=lambda _: api.events.append("signature"),
        )

    def test_creates_stable_release_and_only_uploads_signed_apk(self):
        api = FakeGitHubApi()

        self.assertEqual(self.publisher(api).run(), APK_NAME)

        self.assertTrue(any(entry[0] == "upload" for entry in api.writes))
        self.assertEqual(list(api.assets.values())[0][0]["name"], APK_NAME)
        self.assertEqual(api.release["name"], RELEASE_TITLE)
        self.assertFalse(api.release["draft"])
        self.assertFalse(api.release["prerelease"])
        self.assertEqual(api.tag_ref["object"]["sha"], COMMIT_SHA)
        self.assertLess(api.events.index("signature"), api.events.index("upload"))

    def test_replaces_only_publisher_owned_apks_after_upload_verification(self):
        old_name = "ATAK-Plugin-Houndmaster-5.6.0-ff41a741-civ-release.apk"
        body = update_marker("Existing release notes", [old_name])
        api = FakeGitHubApi(body=body, assets={old_name: b"old apk", "notes.txt": b"keep"})
        old_asset_id = next(
            asset["id"] for asset, _ in api.assets.values() if asset["name"] == old_name
        )

        self.publisher(api).run()

        self.assertNotIn(old_asset_id, api.assets)
        self.assertTrue(any(asset["name"] == "notes.txt" for asset, _ in api.assets.values()))
        self.assertTrue(any(asset["name"] == APK_NAME for asset, _ in api.assets.values()))
        verification_index = next(
            index for index, entry in enumerate(api.writes) if entry[0] == "verify"
        )
        deletion_index = next(
            index
            for index, entry in enumerate(api.writes)
            if entry == ("delete-asset", old_asset_id)
        )
        self.assertLess(verification_index, deletion_index)
        self.assertEqual(
            json.loads(api.release["body"].split("houndmaster-ci-assets: ", 1)[1][:-4]),
            [APK_NAME],
        )

    def test_keeps_old_assets_when_uploaded_bytes_fail_verification(self):
        old_name = "ATAK-Plugin-Houndmaster-5.6.0-ff41a741-civ-release.apk"
        api = FakeGitHubApi(
            body=update_marker("", [old_name]),
            assets={old_name: b"old apk"},
            corrupt_upload=True,
        )
        old_asset_id = next(
            asset["id"] for asset, _ in api.assets.values() if asset["name"] == old_name
        )

        with self.assertRaisesRegex(PublishError, "did not match"):
            self.publisher(api).run()

        self.assertIn(old_asset_id, api.assets)
        self.assertEqual(api.release["name"], "old title")
        self.assertTrue(api.release["prerelease"])

    def test_refuses_to_overwrite_an_unmarked_existing_release(self):
        api = FakeGitHubApi(body="Release created by someone else")

        with self.assertRaisesRegex(PublishError, "not marked as publisher-owned"):
            self.publisher(api).run()

        self.assertFalse(any(entry[0] == "upload" for entry in api.writes))

    def test_refuses_to_publish_when_github_mirror_is_stale(self):
        api = FakeGitHubApi(branch_sha="0" * 40)

        with self.assertRaisesRegex(PublishError, "mirror does not match"):
            self.publisher(api).run()

        self.assertIsNone(api.release)
        self.assertFalse(api.writes)

    def test_refuses_to_move_the_release_when_the_branch_advances_during_upload(self):
        old_name = "ATAK-Plugin-Houndmaster-5.6.0-ff41a741-civ-release.apk"
        api = FakeGitHubApi(
            body=update_marker("", [old_name]),
            assets={old_name: b"old apk"},
        )
        head_values = iter((COMMIT_SHA, "0" * 40))
        publisher = ReleasePublisher(
            self.env,
            api=api,
            head_reader=lambda _: next(head_values),
            apk_verifier=lambda _: api.events.append("signature"),
        )
        old_asset_id = next(
            asset["id"] for asset, _ in api.assets.values() if asset["name"] == old_name
        )

        with self.assertRaisesRegex(PublishError, "no longer the canonical main head"):
            publisher.run()

        self.assertIn(old_asset_id, api.assets)
        self.assertFalse(any(entry[0] == "move-tag" for entry in api.writes))

    def test_refuses_to_publish_an_unsigned_apk(self):
        api = FakeGitHubApi()

        def reject_unsigned(_):
            raise PublishError("signature is invalid")

        publisher = ReleasePublisher(
            self.env,
            api=api,
            head_reader=lambda _: COMMIT_SHA,
            apk_verifier=reject_unsigned,
        )
        with self.assertRaisesRegex(PublishError, "signature is invalid"):
            publisher.run()

        self.assertIsNone(api.release)
        self.assertFalse(api.writes)


if __name__ == "__main__":
    unittest.main()
