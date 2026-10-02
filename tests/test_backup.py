import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / 'db_tools.py'


def make_orders(path: Path) -> None:
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY, seat TEXT, drink TEXT, status TEXT)")
        conn.execute("INSERT INTO orders VALUES(1, '2', '아메리카노(HOT)', '대기 중')")


def test_backup_restored_when_original_removed(tmp_path: Path) -> None:
    # Given synthetic orders and a verified backup; When restored; Then records match.
    source, backup, restored = (tmp_path / name for name in ('source.db', 'backup.db', 'restored.db'))
    make_orders(source)
    result = subprocess.run([sys.executable, str(TOOL), 'backup', str(source), str(backup)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    source.unlink()
    result = subprocess.run([sys.executable, str(TOOL), 'restore', str(backup), str(restored)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with closing(sqlite3.connect(restored)) as conn:
        assert conn.execute('SELECT * FROM orders').fetchall() == [(1, '2', '아메리카노(HOT)', '대기 중')]
    assert backup.exists()


def test_backup_denied_when_destination_exists(tmp_path: Path) -> None:
    # Given two existing DB files; When overwrite requested; Then target is untouched.
    source, target = tmp_path / 'source.db', tmp_path / 'target.db'
    make_orders(source)
    target.write_bytes(b'preserve this file')
    result = subprocess.run([sys.executable, str(TOOL), 'backup', str(source), str(target)], capture_output=True)
    assert result.returncode != 0
    assert target.read_bytes() == b'preserve this file'


def test_backup_denied_when_source_missing(tmp_path: Path) -> None:
    # Given no source file; When backup requested; Then no empty DB is created.
    source, target = tmp_path / 'missing.db', tmp_path / 'target.db'
    result = subprocess.run([sys.executable, str(TOOL), 'backup', str(source), str(target)], capture_output=True)
    assert result.returncode != 0
    assert not source.exists() and not target.exists()


def test_restore_denied_when_backup_corrupted(tmp_path: Path) -> None:
    # Given invalid SQLite bytes; When restored; Then no usable target is claimed.
    backup, target = tmp_path / 'broken.db', tmp_path / 'target.db'
    backup.write_bytes(b'broken sqlite')
    result = subprocess.run([sys.executable, str(TOOL), 'restore', str(backup), str(target)], capture_output=True)
    assert result.returncode != 0
    assert not target.exists()


def test_verify_denied_when_schema_unrelated(tmp_path: Path) -> None:
    # Given SQLite without orders; When checked; Then it is rejected as QR backup.
    source = tmp_path / 'other.db'
    with closing(sqlite3.connect(source)) as conn, conn:
        conn.execute('CREATE TABLE other(value TEXT)')
    result = subprocess.run([sys.executable, str(TOOL), 'verify', str(source)], capture_output=True)
    assert result.returncode != 0
