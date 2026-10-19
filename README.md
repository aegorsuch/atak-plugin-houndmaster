
# Houndmaster Plugin

Houndmaster provides a focused Bloodhound order workflow within ATAK. It lets an operator select a map item, assign a contact, send the selected item, and monitor the contact's response.

## Order Workflow

1. Open the Houndmaster dashboard from the ATAK plugin/tool menu.
2. Tap the **+** icon beside the Houndmaster title.
3. Select a target map item.
4. Select the contact that should receive the order.
5. Houndmaster sends the target to the selected contact, sends them a chat message such as `ODIN-ATAK sent you S-F. RGR to start, nPos to close`, and records the order as **Sent**.
6. The dashboard remains available so the order and its current status can be monitored.

## Statuses

The dashboard displays one of three statuses:

| Display status | Meaning |
| --- | --- |
| **Sent** | The order was created and sent to the selected contact. |
| **Active** | The contact replied with `RGR`, `Roger`, or `Bloodhounding` and is working the order. The parser also accepts the observed misspelling `Bloodhonding`. |
| **Complete** | The contact replied with `nPos` or `In Position`, indicating the order is complete. |

Replies are case-insensitive, and `RGR`, `Roger`, and `nPos` must appear as standalone words.

Incoming status messages are matched first by the assigned contact's UID and the target's UID when those IDs are present in the message. For existing replies that identify the target by title, Houndmaster uses the assigned sender identity and updates only an unambiguous match. A reply that names no target, such as a bare `RGR`, updates the sender's order only when that contact has exactly one open order; otherwise it is ignored. If a tracked map item's title changes, its saved UID lets Houndmaster use the current title.

Statuses only move forward: a late `Roger` cannot reopen a completed order.

## Managing Orders

- Orders are shown in a compact single-line list with target, recipient, and status.
- Tap the trash icon to delete an order.
- Deletion requires confirmation before the order is removed.
- The dashboard refreshes when an order is added, deleted, or updated by an incoming status message.
- The target and contact lists can be searched by title or callsign and update when eligible map items appear or disappear.

## Release Targets

The project supports ATAK-CIV, ATAK-GOV, and ATAK-MIL product flavors.

## Versioning

The plugin version is `<ATAK SDK version>-<commit hash>`, for example `5.6.0-1c34d70`. APKs are named `ATAK-Plugin-Houndmaster-<ATAK SDK version>-<commit hash>-<flavor>-<build type>.apk`, for example `ATAK-Plugin-Houndmaster-5.6.0-1c34d70-civ-release.apk`.

## Repositories

The TAK Forge repository (`git.tak.gov`) is canonical. The GitHub repository is a secondary mirror maintained as a backup of `develop`.

Development follows feature branches merged into the canonical repository's `develop` branch, which is then pushed to the GitHub mirror.

## TAK Forge CI/CD

`.gitlab-ci.yml` uses the shared `devsecops/gitlab-ci-common` build-and-sign
template, matching Physio Dashboard and WearTAK Companion. Pushes to `develop`
run `release_build_and_sign` with JDK 17 for the `civ` variant. Other branches do
not run this build job. Houndmaster continues to target ATAK 5.6.0.

The shared launcher handles authenticated TAK dependency access, building,
signing, and build/report artifacts. It requires access to the shared template,
TAK runners, artifact repositories, and signing service. Keep credentials and
signing keys in Forge CI services/configuration, not in Git.

The build supports `takrepo.url`, `takrepo.user`, and `takrepo.password` Gradle/local
properties and the launcher's underscore-form `takrepo_url`, `takrepo_user`, and
`takrepo_password` properties. Dotted properties take precedence. The launcher
can provide a root-level, untracked `signing.properties` with `storeFile`,
`storePassword`, `keyAlias`, and `keyPassword`; a relative `storeFile` is resolved
from `app`. Without that file, the existing local signing defaults are preserved.

The shared template exposes manual `release_internal` and `distribute_resources`
jobs on protected branches. Building does not automatically publish or distribute
the plugin. Production publication uses the shared template's protected
maintenance-branch and plugin-metadata requirements; a successful develop build
is not production approval.

The `publish_github_pipeline_release` job publishes only the signed CIV release
APK from a successful protected `develop` push to the GitHub mirror's
`takgov-pipeline` rolling release, titled **TAK.gov CI/CD Pipeline Release**.
It runs only when canonical Forge `develop` and the GitHub `develop` mirror both
match the pipeline commit. The job verifies the APK signature and uploaded
bytes; it does not publish the AAB, debug APK, source archive, or CI reports.
Numbered releases, the `dev` prerelease, and unrelated assets are left alone.

Enable publication by adding a protected, masked `GITHUB_RELEASE_TOKEN` CI/CD
variable to the TAK Forge project. Use a fine-grained GitHub token scoped only
to `aegorsuch/atak-plugin-houndmaster` with **Contents: read and write**
permission. Do not copy a developer's local GitHub CLI token into CI or commit
credentials. The publisher records its own APK asset names in the rolling
release description and only replaces assets it previously recorded. It moves
only the dedicated `takgov-pipeline` rolling tag; numbered and other tags are
not modified.

This pipeline runs on canonical TAK Forge only; mirroring source to GitHub
remains a separate operation.

## Rights

Unlimited Rights granted to TAK Product Center.

## Point of Contact

Alex Gorsuch on chat.tak.gov or Signal

---
