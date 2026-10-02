# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
# Run: uv run db_tools.py backup SOURCE.db NEW_BACKUP.db
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path


class UnsafeDatabaseError(RuntimeError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path: Path = path
        self.reason: str = reason
        super().__init__(f'{path}: {reason}')


def verify_connection(conn: sqlite3.Connection, path: Path) -> int:
    if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise UnsafeDatabaseError(path, 'SQLite integrity check failed')
    schema: list[tuple[int, str, str, int, str | None, int]] = conn.execute('PRAGMA table_info(orders)').fetchall()
    columns = {row[1] for row in schema}
    if not {'id', 'seat', 'drink', 'status'}.issubset(columns):
        raise UnsafeDatabaseError(path, 'Not a QR orders database')
    counts: list[tuple[int]] = conn.execute('SELECT COUNT(*) FROM orders').fetchall()
    return counts[0][0]


def verify_database(path: Path) -> int:
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        return verify_connection(conn, path)


def copy_verified(source: Path, destination: Path) -> int:
    source, destination = source.resolve(), destination.resolve()
    _ = verify_database(source)
    # Exclusive reservation prevents overwriting a live DB, a backup, or a concurrently created file.
    with destination.open('xb'):
        pass
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(destination)) as copied:
                original.backup(copied)
                return verify_connection(copied, destination)
    except (sqlite3.Error, UnsafeDatabaseError, OSError):
        destination.unlink()
        raise


def main(arguments: Sequence[str]) -> int:
    if len(arguments) == 2 and arguments[0] == 'verify':
        print(f'Verified orders: {verify_database(Path(arguments[1]))}')
        return 0
    if len(arguments) == 3 and arguments[0] in {'backup', 'restore'}:
        count = copy_verified(Path(arguments[1]), Path(arguments[2]))
        print(f'{arguments[0]} verified: {count} orders -> {arguments[2]}')
        return 0
    print('Usage: db_tools.py verify SOURCE | backup SOURCE NEW_BACKUP | restore BACKUP NEW_DB', file=sys.stderr)
    return 2


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (sqlite3.Error, UnsafeDatabaseError, OSError) as error:
        print(f'Database operation refused: {error}', file=sys.stderr)
        raise SystemExit(1) from error
