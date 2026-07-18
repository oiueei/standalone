"""
Account erasure (right to be forgotten).

One function, `delete_account`, because the schema already says almost
everything: the map of what dies, what survives anonymised, and what was never
identifying in the first place is encoded in the FK `on_delete` rules, and the
Cloudinary assets follow via the `post_delete` handlers in
`cloudinary_cleanup.py`. This module exists so that map is written down in one
place and the views stay thin.

What `user.delete()` cascades away (CASCADE):
- Their collections — and with them the `collection_things` / `collection_invites`
  M2M rows. Things *inside* that belong to other members survive (only the M2M
  row dies); the collection page itself is gone.
- Their things — everywhere, including ones they added to other people's
  COMMUNITY collections and SHARE/SWAP things they received (ownership had
  transferred, so those are theirs to take down). Each thing drags its own
  FAQs, transfers, bookings and wish-links with it.
- Their bookings (both sides), RSVPs, in-app notifications, daily-activity rows
  and wish responses.

What survives, anonymised (SET_NULL):
- FAQ questions they asked on *other people's* things (`FAQ.questioner`) — the
  answer is knowledge about the thing; the name is not. Rendered as
  "former member" by the frontend.
- Their hops in *other people's* things' journeys (`ThingTransfer.from_user` /
  `to_user`) — the handoff happened; the name goes.
- `Report` rows they filed (already SET_NULL — moderation log).

What was never identifying:
- The `Event` analytics log stores 6-char code snapshots, not FKs, and is never
  exposed to users (DESIGN §9). The codes stop resolving to anyone the moment
  the row below is gone.

Cloudinary: the `post_delete` handlers destroy the profile photo and every
thumbnail/gallery/welcome-doc of the cascaded rows, on commit.
"""

import logging

from django.db import transaction

security_logger = logging.getLogger("security")


def delete_account(user):
    """Erase a user account, immediately and irreversibly.

    Returns the (now dangling) user code, for the caller's logging.
    """
    user_code = user.code
    with transaction.atomic():
        user.delete()
    security_logger.info(f"Account {user_code} deleted (user-requested erasure)")
    return user_code
