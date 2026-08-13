Portraits are fetched by `scripts/fetch_avatars.py` from Wikimedia Commons, and only if
the licence is free — see CREDITS.md for who took each one. Anyone without a free portrait
falls back to a generated SVG from `scripts/avatars.py`, whose colour matches the initials
avatar in `lib/api.ts` so a failed image never changes the character's colour.

To override one by hand, drop `<handle>.png` here and point the character file at it:

    "avatar": "/avatars/elonmusk.png"

A full external URL works in the same field. Empty or missing falls back to initials.
