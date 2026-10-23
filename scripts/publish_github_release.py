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
RELEASE_TITLE = "TAK.gov Forge CI/CD Pipeline Release"
OWNERSHIP_MARKER = "<!-- houndmaster-ci-assets: "
METADATA_START = "<!-- houndmaster-release-metadata:start -->"
METADATA_END = "<!-- houndmaster-release-metadata:end -->"
APK_PATTERN = re.compile(
    r"^ATAK-Plugin-Houndmaster-[0-9][A-Za-z0-9.+_-]*-[0-9a-f]{8}-civ-release\.apk$"
)
OWNED_ASSET_PATTERN = re.compile(
    r"^(?:ATAK-Plugin-Houndmaster-[0-9][A-Za-z0-9.+_-]*-[0-9a-f]{8}-civ-release|"
    r"Houndmaster-[0-9][A-Za-z0-9.+_-]*-p[0-9]+)\.apk$"
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

    def upload_asset(self, release, name, label, asset_path):
        upload_url = release["upload_url"].split("{", 1)[0]
        url = upload_url + "?" + urllib.parse.urlencode({"name": name, "label": label})
        status, body = self._request(
            "POST", url, data=asset_path.read_bytes()
        )
        if status < 200 or status >= 300:
            raise PublishError("GitHub asset upload returned HTTP " + str(status))
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PublishError("GitHub returned invalid upload metadata")

    def update_asset_label(self, asset_id, label):
        return self.request_json(
            "PATCH",
            f"/repos/{GITHUB_REPOSITORY}/releases/assets/{asset_id}",
            {"label": label},
        )

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


def latest_main_sha(repository_url):
    result = subprocess.run(
        ["git", "ls-remote", repository_url, "refs/heads/main"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PublishError("Could not verify the canonical main branch head")
    fields = result.stdout.strip().split()
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise PublishError("Could not read the canonical main branch head")
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


def read_apk_metadata(apk_path):
    sdk_root = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if not sdk_root:
        raise PublishError("Android SDK path is unavailable for APK metadata inspection")
    build_tools = Path(sdk_root) / "build-tools"
    candidates = [
        path / tool_name
        for path in build_tools.iterdir()
        if path.is_dir()
        for tool_name in ("aapt", "aapt.exe")
        if (path / tool_name).is_file()
    ] if build_tools.is_dir() else []
    if not candidates:
        raise PublishError("Android aapt is unavailable for APK metadata inspection")
    aapt = max(
        candidates,
        key=lambda path: tuple(
            int(part) for part in re.findall(r"\d+", path.parent.name)
        ),
    )
    result = subprocess.run(
        [str(aapt), "dump", "badging", str(apk_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PublishError("Could not inspect release APK version metadata")
    match = re.search(
        r"(?m)^package: name='[^']+' versionCode='([^']+)' versionName='([^']*)'",
        result.stdout,
    )
    if not match or not match.group(2):
        raise PublishError("The release APK has invalid version metadata")
    if not match.group(1).isdigit():
        raise PublishError("The release APK versionCode is invalid")
    return {"version_code": match.group(1), "version_name": match.group(2)}


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
        not isinstance(name, str) or not OWNED_ASSET_PATTERN.fullmatch(name)
        for name in names
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


def update_release_body(body, metadata, names):
    body = body or ""
    metadata_pattern = re.compile(
        re.escape(METADATA_START) + r".*?" + re.escape(METADATA_END),
        re.DOTALL,
    )
    if body.count(METADATA_START) != body.count(METADATA_END):
        raise PublishError("The rolling release metadata markers are invalid")
    if body.count(METADATA_START) > 1:
        raise PublishError("The rolling release contains duplicate metadata markers")
    if body.count(METADATA_START) and not metadata_pattern.search(body):
        raise PublishError("The rolling release metadata markers are invalid")
    block = METADATA_START + "\n" + metadata + "\n" + METADATA_END
    if metadata_pattern.search(body):
        body = metadata_pattern.sub(lambda _: block, body, count=1)
    else:
        body = body.rstrip() + ("\n\n" if body.strip() else "") + block
    return update_marker(body, names)


def artifact_version(apk_path):
    suffix = apk_path.name.split("ATAK-Plugin-Houndmaster-", 1)[1]
    return "-".join(suffix.split("-")[:-3])


def version_with_pipeline_iid(version, pipeline_iid):
    if not pipeline_iid or not pipeline_iid.isdigit():
        raise PublishError("The project pipeline IID is required for release naming")
    embedded_iid = re.search(r"-p([0-9]+)$", version)
    if embedded_iid:
        if embedded_iid.group(1) != pipeline_iid:
            raise PublishError("The APK version pipeline IID does not match this pipeline")
        return version
    return f"{version}-p{pipeline_iid}"


def release_asset_name(version):
    return f"Houndmaster-{version}.apk"


def release_asset_label(version):
    return f"Houndmaster {version} CIV release APK"


def release_metadata(env, asset_name, asset_label, version, version_code, sha256):
    pipeline_id = env.get("CI_PIPELINE_ID", "")
    pipeline_iid = env.get("CI_PIPELINE_IID", "")
    if pipeline_id and not pipeline_id.isdigit():
        raise PublishError("The global pipeline ID is invalid")
    if pipeline_iid and not pipeline_iid.isdigit():
        raise PublishError("The project pipeline IID is invalid")

    pipeline_url = env.get("CI_PIPELINE_URL", "")
    if pipeline_id:
        expected_url = (
            f"https://{env['CI_SERVER_HOST']}/{env['CI_PROJECT_PATH']}"
            f"/-/pipelines/{pipeline_id}"
        )
        if pipeline_url and pipeline_url != expected_url:
            raise PublishError("The pipeline URL is not the canonical Forge pipeline")
        pipeline_url = pipeline_url or expected_url
    elif pipeline_url:
        parsed = urllib.parse.urlsplit(pipeline_url)
        prefix = f"/{env['CI_PROJECT_PATH']}/-/pipelines/"
        pipeline_match = re.fullmatch(re.escape(prefix) + r"([0-9]+)", parsed.path)
        if (
            parsed.scheme != "https"
            or parsed.hostname != env["CI_SERVER_HOST"]
            or parsed.query
            or parsed.fragment
            or not pipeline_match
        ):
            raise PublishError("The pipeline URL is not the canonical Forge pipeline")
        pipeline_id = pipeline_match.group(1)

    apk_url = (
        f"https://github.com/{GITHUB_REPOSITORY}/releases/download/"
        f"{urllib.parse.quote(RELEASE_TAG, safe='')}/"
        f"{urllib.parse.quote(asset_name, safe='')}"
    )
    build = "GitLab pipeline"
    if pipeline_id:
        build += f" **{pipeline_id}**"
    if pipeline_iid:
        build += f" (project pipeline **{pipeline_iid}**)"
    lines = [
        f"Automatically published stable Houndmaster {env['CI_COMMIT_BRANCH']}-channel CIV plugin build.",
        "",
        f"- APK version: **{version}** (versionCode **{version_code}**)",
    ]
    if pipeline_id or pipeline_iid:
        lines.append(f"- Build: {build}")
    if pipeline_url:
        lines.append(f"- Pipeline: {pipeline_url}")
    lines.extend(
        [
            f"- Source commit: `{env['CI_COMMIT_SHA'].lower()}` on TAK.gov `{env['CI_COMMIT_BRANCH']}`",
            f"- SHA256: `{sha256}`",
            f"- Download: [{asset_label}]({apk_url})",
        ]
    )
    return "\n".join(lines)


class ReleasePublisher:
    def __init__(
        self,
        env,
        api=None,
        head_reader=latest_main_sha,
        apk_verifier=verify_signed_apk,
        apk_metadata_reader=read_apk_metadata,
    ):
        self.env = env
        self.api = api or GitHubApi(env["GITHUB_RELEASE_TOKEN"])
        self.head_reader = head_reader
        self.apk_verifier = apk_verifier
        self.apk_metadata_reader = apk_metadata_reader

    def assert_current_head(self, commit_sha):
        if self.head_reader(self.env["CI_REPOSITORY_URL"]) != commit_sha:
            raise PublishError("This pipeline is no longer the canonical main head")
        mirror = self.api.request_json(
            "GET", f"/repos/{GITHUB_REPOSITORY}/commits/main"
        )
        if mirror.get("sha", "").lower() != commit_sha:
            raise PublishError("The GitHub main mirror does not match this pipeline")

    def run(self):
        required = (
            "CI_SERVER_HOST",
            "CI_PROJECT_PATH",
            "CI_COMMIT_BRANCH",
            "CI_PIPELINE_SOURCE",
            "CI_COMMIT_SHA",
            "CI_REPOSITORY_URL",
            "CI_PIPELINE_IID",
            "GITHUB_RELEASE_TOKEN",
        )
        missing = [name for name in required if not self.env.get(name)]
        if missing:
            raise PublishError("Required CI configuration is missing: " + ", ".join(missing))
        if (
            self.env["CI_SERVER_HOST"] != "git.tak.gov"
            or self.env["CI_PROJECT_PATH"] != GITHUB_REPOSITORY
            or self.env["CI_COMMIT_BRANCH"] != "main"
            or self.env["CI_PIPELINE_SOURCE"] != "push"
        ):
            raise PublishError("Only canonical main push pipelines may publish")

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
        apk_metadata = self.apk_metadata_reader(apk_path)
        apk_version = artifact_version(apk_path)
        if apk_metadata["version_name"] != f"{apk_version}-{commit_sha[:8]}":
            raise PublishError("The APK version does not match its filename and commit")
        display_version = version_with_pipeline_iid(
            apk_version, self.env["CI_PIPELINE_IID"]
        )
        asset_name = release_asset_name(display_version)
        asset_label = release_asset_label(display_version)
        title = f"{RELEASE_TITLE} ({display_version})"
        local_digest = hashlib.sha256(apk_path.read_bytes()).hexdigest()
        metadata = release_metadata(
            self.env,
            asset_name,
            asset_label,
            apk_metadata["version_name"],
            apk_metadata["version_code"],
            local_digest,
        )

        release_path = f"/repos/{GITHUB_REPOSITORY}/releases/tags/{RELEASE_TAG}"
        release = self.api.request_json("GET", release_path, allow_not_found=True)
        if release is None:
            release = self.api.request_json(
                "POST",
                f"/repos/{GITHUB_REPOSITORY}/releases",
                {
                    "tag_name": RELEASE_TAG,
                    "name": title,
                    "body": update_marker("", []),
                    "draft": True,
                    "prerelease": False,
                    "target_commitish": commit_sha,
                },
            )
        owned_names = read_owned_names(release.get("body", ""))
        assets = self.api.list_assets(release["id"])
        assets_by_name = {asset["name"]: asset for asset in assets}
        existing = assets_by_name.get(asset_name)
        if existing is not None and asset_name not in owned_names:
            raise PublishError("A non-publisher release asset uses the APK filename")
        planned_names = list(dict.fromkeys(owned_names + [asset_name]))
        if existing is not None:
            remote_digest = hashlib.sha256(
                self.api.download_asset(existing["id"])
            ).hexdigest()
            if remote_digest != local_digest:
                raise PublishError(
                    "An asset for this commit already exists with different bytes"
                )
        else:
            new_asset = self.api.upload_asset(
                release, asset_name, asset_label, apk_path
            )
            if new_asset.get("name") != asset_name or "id" not in new_asset:
                raise PublishError("GitHub returned invalid release-asset metadata")
            remote_digest = hashlib.sha256(
                self.api.download_asset(new_asset["id"])
            ).hexdigest()
            if remote_digest != local_digest:
                self.api.delete_asset(new_asset["id"])
                raise PublishError("The uploaded APK did not match the pipeline artifact")

        self.assert_current_head(commit_sha)
        release = self.api.request_json(
            "PATCH",
            f"/repos/{GITHUB_REPOSITORY}/releases/{release['id']}",
            {
                "name": title,
                "body": update_release_body(
                    release.get("body", ""),
                    metadata,
                    planned_names,
                ),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
            },
        )
        if existing is not None:
            self.api.update_asset_label(
                existing["id"], asset_label
            )
        self.update_rolling_tag(commit_sha)
        for asset in assets:
            if asset["name"] in owned_names and asset["name"] != asset_name:
                self.api.delete_asset(asset["id"])

        self.api.request_json(
            "PATCH",
            f"/repos/{GITHUB_REPOSITORY}/releases/{release['id']}",
            {
                "name": title,
                "body": update_release_body(
                    release.get("body", ""), metadata,
                    [asset_name],
                ),
                "draft": False,
                "prerelease": False,
                "target_commitish": commit_sha,
            },
        )
        return asset_name

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
                f"/repos/{GITHUB_REPOSITORY}/git/refs/tags/{RELEASE_TAG}",
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
