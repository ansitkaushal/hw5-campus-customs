"""Reset the working database to the original values: copy campus_customs.db over campus_customs_new.db.

Run before every full ticket run:  python -m backend.reset_db
"""

from __future__ import annotations

import shutil

from .config import DB_ORIGINAL, DB_WORKING


def reset() -> None:
    for suffix in ("-wal", "-shm"):
        DB_WORKING.with_name(DB_WORKING.name + suffix).unlink(missing_ok=True)
    shutil.copyfile(DB_ORIGINAL, DB_WORKING)


if __name__ == "__main__":
    reset()
    print(f"Reset {DB_WORKING.name} from {DB_ORIGINAL.name}")
