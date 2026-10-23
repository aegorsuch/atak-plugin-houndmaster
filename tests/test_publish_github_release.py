import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts.publish_github_release import (
    GitHubApi,
    PublishError,
    RELEASE_TITLE,
    ReleasePublisher,
    read_apk_metadata,
    read_owned_names,
    release_asset_name,
    update_release_body,
    update_marker,
    version_with_pipeline_iid,
)


COMMIT_SHA = "851ba8966e0fd05a2a86764f11c2c863d228d5d8"
APK_NAME = "ATAK-Plugin-Houndmaster-5.6.0-851ba896-civ-release.apk"
ASSET_NAME = "Houndmaster-5.6.0-p160.apk"


class GitHubApiTests(unittest.TestCase):
    def test_upload_passes_a_readable_label_without_changing_asset_name(self):
        api = GitHubApi("test-token")
        label = "Houndmaster 5.6.0 CIV release APK"
        with tempfile.TemporaryDirectory() as directory:
            asset = Path(directory) / "release.apk"
            asset.write_bytes(b"test artifact")
            with patch.object(
                api, "_request", return_value=(201, b'{"id":1,"name":"asset.apk"}')
            ) as request:
                api.upload_asset(
                    {
                        "upload_url": "https://uploads.example/releases/17/assets{?name,label}"
                    },
                    APK_NAME,
                    label,
                    asset,
                )

        url = request.call_args.args[1]
        self.assertEqual(
            parse_qs(urlsplit(url).query),
            {"name": [APK_NAME], "label": [label]},
        )

    def test_existing_asset_label_uses_github_metadata_patch(self):
        api = GitHubApi("test-token")
        label = "Houndmaster 5.6.0 CIV release APK"
        with patch.object(api, "request_json", return_value={}) as request:
            api.update_asset_label(17, label)

        request.assert_called_once_with(
            "PATCH",
            "/repos/aegorsuch/atak-plugin-houndmaster/releases/assets/17",
            {"label": label},
        )

    def test_reads_manifest_version_and_version_code_from_aapt(self):
        with tempfile.TemporaryDirectory() as sdk_root:
            aapt = Path(sdk_root) / "build-tools" / "35.0.0" / "aapt.exe"
            aapt.parent.mkdir(parents=True)
            aapt.touch()
            output = SimpleNamespace(
                returncode=0,
                stdout=(
                    "package: name='com.atakmap.app.civ' "
                    "versionCode='5830160' versionName='5.6.0-851ba896'\n"
                ),
            )
            with patch.dict(os.environ, {"ANDROID_SDK_ROOT": sdk_root}), patch(
                "scripts.publish_github_release.subprocess.run", return_value=output
            ) as run:
                metadata = read_apk_metadata(Path("release.apk"))

        self.assertEqual(
            metadata,
            {"version_code": "5830160", "version_name": "5.6.0-851ba896"},
        )
        self.assertEqual(run.call_args.args[0][1:3], ["dump", "badging"])


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

    def add_asset(self, name, content, label=None):
        asset = {"id": self.next_asset_id, "name": name, "label": label}
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
        if path.endswith("/git/ref/tags/takgov-pipeline") and method == "GET":
            return getattr(self, "tag_ref", None)
        if path.endswith("/git/refs/tags/takgov-pipeline") and method == "PATCH":
            self.writes.append(("move-tag", payload))
            self.tag_ref = {"object": {"sha": payload["sha"]}}
            return self.tag_ref
        if path.endswith("/git/refs") and method == "POST":
            self.writes.append(("create-tag", payload))
            self.tag_ref = {"object": {"sha": payload["sha"]}}
            return self.tag_ref
        raise AssertionError(f"Unexpected API request: {method} {path}")

    def upload_asset(self, release, name, label, asset_path):
        self.writes.append(("upload", name, label))
        self.events.append("upload")
        content = asset_path.read_bytes()
        if self.corrupt_upload:
            content += b"corrupt"
        return self.add_asset(name, content, label)

    def download_asset(self, asset_id):
        self.writes.append(("verify", asset_id))
        return self.assets[asset_id][1]

    def delete_asset(self, asset_id):
        self.writes.append(("delete-asset", asset_id))
        del self.assets[asset_id]

    def update_asset_label(self, asset_id, label):
        self.writes.append(("update-label", asset_id, label))
        self.assets[asset_id][0]["label"] = label


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
            "CI_PIPELINE_ID": "1799402",
            "CI_PIPELINE_IID": "160",
            "CI_PIPELINE_URL": "https://git.tak.gov/aegorsuch/atak-plugin-houndmaster/-/pipelines/1799402",
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
            apk_metadata_reader=lambda _: {
                "version_name": "5.6.0-851ba896",
                "version_code": "5830160",
            },
        )

    def test_creates_stable_release_and_only_uploads_signed_apk(self):
        api = FakeGitHubApi()

        self.assertEqual(self.publisher(api).run(), ASSET_NAME)

        self.assertTrue(any(entry[0] == "upload" for entry in api.writes))
        asset = list(api.assets.values())[0][0]
        self.assertEqual(asset["name"], ASSET_NAME)
        self.assertEqual(
            asset["label"], ASSET_NAME
        )
        self.assertEqual(api.release["name"], f"{RELEASE_TITLE} (5.6.0-p160)")
        self.assertIn(
            "Automatically published stable Houndmaster main-channel",
            api.release["body"],
        )
        self.assertIn(
            "APK version: **5.6.0-851ba896** (versionCode **5830160**)",
            api.release["body"],
        )
        self.assertIn(
            "GitLab pipeline **1799402** (project pipeline **160**)",
            api.release["body"],
        )
        self.assertIn(self.env["CI_PIPELINE_URL"], api.release["body"])
        self.assertIn(f"Source commit: `{COMMIT_SHA}` on TAK.gov `main`", api.release["body"])
        generated_body = api.release["body"].split(
            "<!-- houndmaster-release-metadata:start -->\n", 1
        )[1].split("\n<!-- houndmaster-release-metadata:end -->", 1)[0]
        self.assertEqual(
            generated_body,
            "\n".join(
                [
                    "Automatically published stable Houndmaster main-channel CIV plugin build.",
                    "",
                    "- APK version: **5.6.0-851ba896** (versionCode **5830160**)",
                    "- Build: GitLab pipeline **1799402** (project pipeline **160**)",
                    f"- Pipeline: {self.env['CI_PIPELINE_URL']}",
                    f"- Source commit: `{COMMIT_SHA}` on TAK.gov `main`",
                    f"- SHA256: `{hashlib.sha256(self.apk_bytes).hexdigest()}`",
                    "",
                    "Install the APK above. GitHub's \"Source code\" archives come from the fixed release anchor tag, not from this build; the source commit above is authoritative and may not yet be mirrored to GitHub.",
                ]
            ),
        )
        self.assertNotIn("- Download:", api.release["body"])
        self.assertIn("<!-- houndmaster-release-metadata:start -->", api.release["body"])
        self.assertIn("<!-- houndmaster-release-metadata:end -->", api.release["body"])
        self.assertIn("<!-- houndmaster-ci-assets:", api.release["body"])
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
        self.assertTrue(
            any(asset["name"] == "notes.txt" for asset, _ in api.assets.values())
        )
        self.assertTrue(
            any(asset["name"] == ASSET_NAME for asset, _ in api.assets.values())
        )
        new_asset = next(
            asset for asset, _ in api.assets.values() if asset["name"] == ASSET_NAME
        )
        self.assertEqual(new_asset["label"], ASSET_NAME)
        self.assertIn("Existing release notes", api.release["body"])
        verification_index = next(
            index for index, entry in enumerate(api.writes) if entry[0] == "verify"
        )
        deletion_index = next(
            index
            for index, entry in enumerate(api.writes)
            if entry == ("delete-asset", old_asset_id)
        )
        self.assertLess(verification_index, deletion_index)
        self.assertEqual(read_owned_names(api.release["body"]), [ASSET_NAME])

    def test_updates_label_for_verified_existing_apk_without_reuploading(self):
        api = FakeGitHubApi(
            body=update_marker("Manual note", [ASSET_NAME]),
            assets={ASSET_NAME: self.apk_bytes},
        )
        asset_id = next(iter(api.assets))

        self.publisher(api).run()

        self.assertEqual(
            api.assets[asset_id][0]["label"], ASSET_NAME
        )
        self.assertFalse(any(entry[0] == "upload" for entry in api.writes))
        self.assertFalse(any(entry[0] == "delete-asset" for entry in api.writes))
        verification_index = next(
            index for index, entry in enumerate(api.writes) if entry[0] == "verify"
        )
        label_index = next(
            index for index, entry in enumerate(api.writes) if entry[0] == "update-label"
        )
        self.assertLess(verification_index, label_index)

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

    def test_updates_generated_metadata_without_repeating_it_or_losing_notes(self):
        metadata = "Automatically published stable build.\n\n- SHA256: `abc123`"
        body = update_release_body("Manually maintained notes", metadata, [])

        updated = update_release_body(body, "Updated metadata", [APK_NAME])

        self.assertIn("Manually maintained notes", updated)
        self.assertIn("Updated metadata", updated)
        self.assertNotIn("abc123", updated)
        self.assertEqual(updated.count("houndmaster-release-metadata:start"), 1)
        self.assertEqual(updated.count("houndmaster-ci-assets:"), 1)

    def test_pipeline_iid_is_used_once_for_version_and_filename(self):
        self.assertEqual(version_with_pipeline_iid("5.6.0", "160"), "5.6.0-p160")
        self.assertEqual(version_with_pipeline_iid("5.6.0-p160", "160"), "5.6.0-p160")
        self.assertEqual(release_asset_name("5.6.0-p160"), ASSET_NAME)

        with self.assertRaisesRegex(PublishError, "does not match"):
            version_with_pipeline_iid("5.6.0-p159", "160")

    def test_refuses_apk_version_mismatch_before_release_changes(self):
        api = FakeGitHubApi()
        publisher = ReleasePublisher(
            self.env,
            api=api,
            head_reader=lambda _: COMMIT_SHA,
            apk_verifier=lambda _: None,
            apk_metadata_reader=lambda _: {
                "version_name": "5.6.0-00000000",
                "version_code": "5830160",
            },
        )

        with self.assertRaisesRegex(PublishError, "does not match"):
            publisher.run()

        self.assertIsNone(api.release)
        self.assertFalse(api.writes)

    def test_rejects_noncanonical_pipeline_url(self):
        env = dict(self.env, CI_PIPELINE_URL="https://example.com/elsewhere")
        api = FakeGitHubApi()
        publisher = ReleasePublisher(
            env,
            api=api,
            head_reader=lambda _: COMMIT_SHA,
            apk_verifier=lambda _: None,
            apk_metadata_reader=lambda _: {
                "version_name": "5.6.0-851ba896",
                "version_code": "5830160",
            },
        )

        with self.assertRaisesRegex(PublishError, "canonical Forge pipeline"):
            publisher.run()

        self.assertIsNone(api.release)
        self.assertFalse(api.writes)

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
            apk_metadata_reader=lambda _: {
                "version_name": "5.6.0-851ba896",
                "version_code": "5830160",
            },
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
