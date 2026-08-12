"""Does SENTINEL_STATE_DIR actually support the review queue? Run: python -m sentinel.statecheck

The queue is SQLite on a mounted volume. Plain file writes are not enough — SQLite needs
byte-range locking, which some network filesystems (notably SMB shares) do not provide, and
WAL additionally wants a shared-memory file. This reports which of those work, so a broken
mount is diagnosed in one command instead of through a 500 and a traceback.
"""

import os
import sqlite3
import sys
from pathlib import Path

state = Path(os.environ.get("SENTINEL_STATE_DIR") or Path(__file__).parents[2] / "data")
probe = state / "statecheck.db"


def main() -> None:
    print(f"state dir       : {state}")
    print(f"  exists        : {state.is_dir()}")
    print(f"  writable      : {os.access(state, os.W_OK)}")
    try:
        (state / "statecheck.txt").write_text("ok", encoding="utf-8")
        print("  plain write   : OK")
    except OSError as e:
        print(f"  plain write   : FAILED {type(e).__name__}: {e}")
        sys.exit(1)

    probe.unlink(missing_ok=True)
    conn = sqlite3.connect(probe)
    for label, statements in (
        ("sqlite write (rollback journal)", ("CREATE TABLE t (x)", "INSERT INTO t VALUES (1)")),
        ("locking_mode=EXCLUSIVE", ("PRAGMA locking_mode=EXCLUSIVE",)),
        ("journal_mode=WAL", ("PRAGMA journal_mode=WAL",)),
        ("write under WAL", ("INSERT INTO t VALUES (2)",)),
    ):
        try:
            for s in statements:
                conn.execute(s)
            conn.commit()
            print(f"  {label:30}: OK")
        except sqlite3.Error as e:
            print(f"  {label:30}: FAILED {type(e).__name__}: {e}")

    print(f"  journal_mode  : {conn.execute('PRAGMA journal_mode').fetchone()[0]}")
    print(f"  locking_mode  : {conn.execute('PRAGMA locking_mode').fetchone()[0]}")
    conn.close()
    print(f"  files         : {sorted(p.name for p in state.glob('statecheck.db*'))}")
    for leftover in (*state.glob("statecheck.db*"), state / "statecheck.txt"):
        leftover.unlink(missing_ok=True)  # a diagnostic that litters the volume it is diagnosing is its own problem


if __name__ == "__main__":
    main()
