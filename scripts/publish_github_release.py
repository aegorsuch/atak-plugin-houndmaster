#!/usr/bin/env python3

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


GITHUB_REPOSITORY = "aegorsuch/atak-plugin-houndmaster"
RELEASE_TAG = "takgov-pipeline"
RELEASE_TITLE = "TAK.gov CI/CD Pipeline Release"
OWNERSHIP_MARKER = "<!-- houndmaster-ci-assets: "
APK_PATTERN = re.compile(
    r"^ATAK-Plugin-Houndmaster-[0-9][A-Za-z0-9.+_-]*-[0-9a-f]{8}-civ-release\.apk$"
)


class PublishError(Exception):
    pass


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        redirected = super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )
        if redirected is not None:
            old_host = urllib.parse.urlsplit(request.full_url).hostname
            new_host = urllib.parse.urlsplit(new_url).hostname
            if old_host != new_host:
                redirected.remove_header("Authorization")
        return redirected


class GitHubApi:
    def __init__(self, token):
        self.token = token
        self.api_url = "https://api.github.com"
        self.opener = urllib.request.build_opener(SafeRedirectHandler())

    def _request(self, method, url, payload=None, data=None, accept=None):
        headers = {
            "Accept": accept or "application/vnd.github+json",
            "Authorization": "Bearer " + self.token,
            "User-Agent": "houndmaster-gitlab-release-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif data is not None:
            headers["Content-Type"] = "application/vnd.android.package-archive"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=120) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()
        except urllib.error.URLError as error:
            raise PublishError("GitHub request failed: " + error.reason.__class__.__name__)

    def request_json(self, method, path, payload=None, allow_not_found=False):
        status, body = self._request(method, self.api_url + path, payload=payload)
        if allow_not_found and status == 404:
            return None
        if status < 200 or status >= 300:
            raise PublishError("GitHub API returned HTTP " + str(status))
        try:
            return json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PublishError("GitHub API returned invalid JSON")

    def list_assets(self, release_id):
        assets = []
        page = 1
        while True:
            batch = self.request_json(
                "GET",
                f"/repos/{GITHUB_REPOSITORY}/releases/{release_id}/assets"
                f"?per_page=100&page={page}",
            )
            if not isinstance(batch, list):
                raise PublishError("GitHub returned an invalid release-asset list")
            assets.extend(batch)
            if len(batch) < 100:
                return assets
            page += 1

    def upload_asset(self, release, name, asset_path):
        upload_url = release["upload_url"].split("{", 1)[0]
        url = upload_url + "?" + urllib.parse.urlencode({"name": name})
        status, body = self._request(
            "POST", url, data=asset_path.read_bytes()
        )
        if status < 200 or status >= 300:
            raise PublishError("GitHub asset upload returned HTTP " + str(status))
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PublishError("GitHub returned invalid upload metadata")

    def download_asset(self, asset_id):
        status, body = self._request(
            "GET",
            f"{self.api_url}/repos/{GITHUB_REPOSITORY}/releases/assets/{asset_id}",
            accept="application/octet-stream",
        )
        if status < 200 or status >= 300:
            raise PublishError("GitHub asset verification returned HTTP " + str(status))
        return body

    def delete_asset(self, asset_id):
        status, _ = self._request(
            "DELETE", f"{self.api_url}/repos/{GITHUB_REPOSITORY}/releases/assets/{asset_id}"
        )
        if status != 204:
            raise PublishError("GitHub asset deletion returned HTTP " + str(status))


def latest_develop_sha(repository_url):
    result = subprocess.run(
        ["git", "ls-remote", repository_url, "refs/heads/develop"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PublishError("Could not verify the canonical develop branch head")
    fields = result.stdout.strip().split()
    if len(fields) != 2 or fields[1] != "refs/heads/develop":
        raise PublishError("Could not read the canonical develop branch head")
    return fields[0].lower()


def verify_signed_apk(apk_path):
    sdk_root = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if not sdk_root:
        raise PublishError("Android SDK path is unavailable for APK signature verification")
    build_tools = Path(sdk_root) / "build-tools"
    candidates = [
        path / "apksigner"
        for path in build_tools.iterdir()
        if path.is_dir() and (path / "apksigner").is_file()
    ] if build_tools.is_dir() else []
    if not candidates:
        raise PublishError("Android apksigner is unavailable for APK signature verification")
    apksigner = max(
        candidates,
        key=lambda path: tuple(
            int(part) for part in re.findall(r"\d+", path.parent.name)
        ),
    )
    result = subprocess.run(
        [str(apksigner), "verify", "--print-certs", str(apk_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0 or not re.search(
        r"Signer #\d+ certificate SHA-256 digest:", output
    ):
        raise PublishError("The release APK failed Android signature verification")


def read_owned_names(body):
    matches = re.findall(
        r"(?m)^<!-- houndmaster-ci-assets: (.+) -->$", body or ""
    )
    if len(matches) != 1:
        raise PublishError("The rolling release is not marked as publisher-owned")
    try:
        names = json.loads(matches[0])
    except json.JSONDecodeError:
        raise PublishError("The rolling release ownership marker is invalid")
    if not isinstance(names, list) or any(
        not isinstance(name, str) or not APK_PATTERN.fullmatch(name) for name in names
    ):
        raise PublishError("The rolling release ownership marker is invalid")
    return list(dict.fromkeys(names))


def update_marker(body, names):
    marker = OWNERSHIP_MARKER + json.dumps(names, separators=(",", ":")) + " -->"
    pattern = re.compile(r"(?m)^<!-- houndmaster-ci-assets: .+ -->$")
    if pattern.search(body or ""):
        return pattern.sub(lambda _: marker, body, count=1)
    if body:
        return body.rstrip() + "\n\n" + marker
    return marker


class ReleasePublisher:
    def __init__(
        self,
        env,
        api=None,
        head_reader=latest_develop_sha,
        apk_verifier=verify_signed_apk,
    ):
        self.env = env
        self.api = api or GitHubApi(env["GITHUB_RELEASE_TOKEN"])
        self.head_reader = head_reader
        self.apk_verifier = apk_verifier

    def assert_current_head(self, commit_sha):
        if self.head_reader(self.env["CI_REPOSITORY_URL"]) != commit_sha:
            raise PublishError("This pipeline is no longer the canonical develop head")
        mirror = self.api.request_json(
            "GET", f"/repos/{GITHUB_REPOSITORY}/commits/develop"
        )
        if mirror.get("sha", "").lower() != commit_sha:
            raise PublishError("The GitHub develop mirror does not match this pipeline")

    def run(self):
        required = (
            "CI_SERVER_HOST",
            "CI_PROJECT_PATH",
            "CI_COMMIT_BRANCH",
            "CI_PIPELINE_SOURCE",
            "CI_COMMIT_SHA",
            "CI_REPOSITORY_URL",
            "GITHUB_RELEASE_TOKEN",
        )
        missing = [name for name in required if not self.env.get(name)]
        if missing:
            raise PublishError("Required CI configuration is missing: " + ", ".join(missing))
        if (
            self.env["CI_SERVER_HOST"] != "git.tak.gov"
            or self.env["CI_PROJECT_PATH"] != GITHUB_REPOSITORY
            or self.env["CI_COMMIT_BRANCH"] != "develop"
            or self.env["CI_PIPELINE_SOURCE"] != "push"
        ):
            raise PublishError("Only canonical develop push pipelines may publish")

        commit_sha = self.env["CI_COMMIT_SHA"].lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise PublishError("The pipeline commit SHA is invalid")
        self.assert_current_head(commit_sha)

        apk_candidates = [
            path
            for path in Path.cwd().glob("ATAK-Plugin-Houndmaster-*-civ-release.apk")
            if path.is_file() and not path.is_symlink()
        ]
        if len(apk_candidates) != 1:
            raise PublishError("Expected exactly one distributable CIV release APK")
        apk_path = apk_candidates[0]
        if (
            not APK_PATTERN.fullmatch(apk_path.name)
            or not apk_path.stat().st_size
            or apk_path.name.split("-")[-3].lower() != commit_sha[:8]
        ):
            raise PublishError("The pipeline APK name or commit does not match")
        self.apk_verifier(apk_path)

        release_path = f"/repos/{GITHUB_REPOSITORY}/releases/tags/{RELEASE_TAG}"
        release = self.api.request_json("GET", release_path, allow_not_found=True)
        if release is None:
            release = self.api.request_json(
                "POST",
                f"/repos/{GITHUB_REPOSITORY}/releases",
                {
                    "tag_name": RELEASE_TAG,
                    "name": RELEASE_TITLE,
                    "body": update_marker("", []),
                    "draft": True,
                    "prerelease": False,
                    "target_commitish": commit_sha,
                },
            )
        owned_names = read_owned_names(release.get("body", ""))
        assets = self.api.list_assets(release["id"])
        assets_by_name = {asset["name"]: asset for asset in assets}
        existing = assets_by_name.get(apk_path.name)
        if existing is not None and apk_path.name not in owned_names:
            raise PublishError("A non-publisher release asset uses the APK filename")

        planned_names = list(dict.fromkeys(owned_names + [apk_path.name]))
        release = self.api.request_json(
            "PATCH",
            f"/repos/{GITHUB_REPOSITORY}/releases/{release['id']}",
            {
                "name": release.get("name") or RELEASE_TITLE,
                "body": update_marker(release.get("body", ""), planned_names),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
            },
        )

        local_digest = hashlib.sha256(apk_path.read_bytes()).hexdigest()
        if existing is not None:
            remote_digest = hashlib.sha256(
                self.api.download_asset(existing["id"])
            ).hexdigest()
            if remote_digest != local_digest:
                raise PublishError(
                    "An asset for this commit already exists with different bytes"
                )
        else:
            new_asset = self.api.upload_asset(release, apk_path.name, apk_path)
            if new_asset.get("name") != apk_path.name or "id" not in new_asset:
                raise PublishError("GitHub returned invalid release-asset metadata")
            remote_digest = hashlib.sha256(
                self.api.download_asset(new_asset["id"])
            ).hexdigest()
            if remote_digest != local_digest:
                self.api.delete_asset(new_asset["id"])
                raise PublishError("The uploaded APK did not match the pipeline artifact")

        self.assert_current_head(commit_sha)
        self.update_rolling_tag(commit_sha)
        for asset in assets:
            if asset["name"] in owned_names and asset["name"] != apk_path.name:
                self.api.delete_asset(asset["id"])

        self.api.request_json(
            "PATCH",
            f"/repos/{GITHUB_REPOSITORY}/releases/{release['id']}",
            {
                "name": RELEASE_TITLE,
                "body": update_marker(release.get("body", ""), [apk_path.name]),
                "draft": False,
                "prerelease": False,
                "target_commitish": commit_sha,
            },
        )
        return apk_path.name

    def update_rolling_tag(self, commit_sha):
        ref_path = f"/repos/{GITHUB_REPOSITORY}/git/ref/tags/{RELEASE_TAG}"
        ref = self.api.request_json("GET", ref_path, allow_not_found=True)
        if ref is None:
            self.api.request_json(
                "POST",
                f"/repos/{GITHUB_REPOSITORY}/git/refs",
                {"ref": "refs/tags/" + RELEASE_TAG, "sha": commit_sha},
            )
        elif ref.get("object", {}).get("sha", "").lower() != commit_sha:
            self.api.request_json(
                "PATCH",
                ref_path,
                {"sha": commit_sha, "force": True},
            )


def main():
    try:
        asset_name = ReleasePublisher(os.environ).run()
    except PublishError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    print("Published verified signed APK: " + asset_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
