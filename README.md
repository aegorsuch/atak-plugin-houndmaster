
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

## Managing Orders

- Orders are shown in a compact single-line list with target, recipient, and status.
- Tap the trash icon to delete an order.
- Deletion requires confirmation before the order is removed.
- The dashboard refreshes when an order is added, deleted, or updated by an incoming status message.

## Release Targets

The project supports ATAK-CIV, ATAK-GOV, and ATAK-MIL product flavors.

## Repositories

The TAK Forge repository (`git.tak.gov`) is canonical. The GitHub repository is a secondary mirror maintained as a backup of `develop`.

Development follows feature branches merged into the canonical repository's `develop` branch, which is then pushed to the GitHub mirror.

## Rights

Unlimited Rights granted to TAK Product Center.

## Point of Contact

Alex Gorsuch on chat.tak.gov or Signal

---
