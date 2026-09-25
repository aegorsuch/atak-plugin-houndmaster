
# Houndmaster Plugin

Houndmaster provides a focused Bloodhound order workflow within ATAK. It lets an operator select a map item, assign a contact, send the selected item, and monitor the contact's response.

## Order Workflow

1. Open the Houndmaster dashboard from the ATAK plugin/tool menu.
2. Tap the **+** icon beside the Houndmaster title.
3. Select a target map item.
4. Select the contact that should receive the order.
5. Houndmaster sends the target to the selected contact and records the order as **Sent**.
6. The dashboard remains available so the order and its current status can be monitored.

## Statuses

The dashboard displays one of three statuses:

| Display status | Meaning |
| --- | --- |
| **Sent** | The order was created and sent to the selected contact. |
| **Active** | The contact replied with `Bloodhounding` and is working the order. The parser also accepts the observed misspelling `Bloodhonding`. |
| **Complete** | The contact replied with `In Position`, indicating the order is complete. |

Incoming chat messages are matched to an order when the message contains both the target map item's title and the contact's name. Matching status replies update the dashboard automatically.

## Managing Orders

- Orders are shown in a compact single-line list with target, recipient, and status.
- Tap the trash icon to delete an order.
- Deletion requires confirmation before the order is removed.
- The dashboard refreshes when an order is added, deleted, or updated by an incoming status message.

## Release Targets

The project supports ATAK-CIV, ATAK-GOV, and ATAK-MIL product flavors. Development follows feature branches merged into the government repository's `develop` branch; the personal GitHub repository is maintained as a backup of `develop`.

---
