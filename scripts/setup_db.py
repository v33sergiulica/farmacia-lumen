"""Repeatable database initialization from problema2_database.sql.tar.gz."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path

from create_indexes import create_indexes

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = ROOT_DIR / "problema2_database.sql.tar.gz"
DEFAULT_DB = ROOT_DIR / "data" / "farmacia.db"


def setup_database(
    archive_path: Path,
    db_path: Path,
    force: bool = False,
    skip_indexes: bool = False,
) -> None:
    """Extract SQL dump into temp directory, import via sqlite3 CLI, and index."""
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    sqlite_bin = shutil.which("sqlite3")
    if not sqlite_bin:
        raise RuntimeError("sqlite3 CLI binary not found in PATH")

    if db_path.exists() and not force:
        print(f"Database already exists at {db_path} (pass --force to rebuild).")
        if not skip_indexes:
            create_indexes(db_path)
            print("Verified analytical indexes on existing database.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with tarfile.open(archive_path, "r:gz") as tf:
            sql_members = [m for m in tf.getmembers() if m.isfile() and m.name.endswith(".sql")]
            if not sql_members:
                raise RuntimeError(f"No .sql file found inside {archive_path}")
            target_member = sql_members[0]
            tf.extract(target_member, path=tmp_path, filter="data")
            sql_file = (tmp_path / target_member.name).resolve()

        # Pass forward slashes so sqlite3 .read parses Windows paths cleanly.
        subprocess.run(
            [sqlite_bin, str(db_path), f".read {sql_file.as_posix()}"],
            check=True,
        )

    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        table_count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
    finally:
        conn.close()

    if table_count != 13:
        raise RuntimeError(f"Expected 13 tables in {db_path}, found {table_count}")

    print(f"Imported {table_count} tables into {db_path} ({db_path.stat().st_size:,} bytes).")
    if not skip_indexes:
        create_indexes(db_path)
        print("Created analytical indexes and ran ANALYZE.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize data/farmacia.db from archive.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--force", action="store_true", help="Rebuild database even if it exists")
    parser.add_argument("--skip-indexes", action="store_true", help="Skip creating analytical indexes")
    args = parser.parse_args()

    setup_database(
        archive_path=args.archive,
        db_path=args.db,
        force=args.force,
        skip_indexes=args.skip_indexes,
    )


if __name__ == "__main__":
    main()
