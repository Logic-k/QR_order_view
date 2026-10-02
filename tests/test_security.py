"""Real Flask/SQLite boundary regressions with test-only data and credentials."""
import base64
import importlib.util
import re
import sqlite3
import sys
from pathlib import Path
from html.parser import HTMLParser

import pytest
from flask.testing import FlaskClient


@pytest.fixture
def private_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    # Given an isolated SQLite path before any application import.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('QR_DATABASE_PATH', str(tmp_path / 'app.db'))
    monkeypatch.setenv('QR_ADMIN_USER', 'test-staff')
    monkeypatch.setenv('QR_ADMIN_PASSWORD', 'test-only-never-production')
    source = Path(__file__).resolve().parents[1] / 'app.py'
    spec = importlib.util.spec_from_file_location('qr_security_app', source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, 'qr_security_app', module)
    spec.loader.exec_module(module)
    module.app.config['TESTING'] = True
    return module.app.test_client()


def credentials() -> dict[str, str]:
    return {'Authorization': 'Basic ' + base64.b64encode(
        b'test-staff:test-only-never-production'
    ).decode('ascii')}


def staff_headers(client: FlaskClient) -> dict[str, str]:
    page = client.get('/admin', headers=credentials()).get_data(as_text=True)
    token = re.search(r'name="csrf-token" content="([^"]+)"', page)
    assert token is not None, 'Authenticated admin must publish a CSRF token'
    return {**credentials(), 'X-CSRF-Token': token.group(1)}


@pytest.mark.parametrize('endpoint,method', [
    ('/admin', 'get'), ('/master-order', 'post'),
    ('/delete-order', 'post'), ('/delete-all-orders', 'post'),
])
def test_admin_denied_when_auth_missing(private_client: FlaskClient, endpoint: str, method: str) -> None:
    # Given no credentials; When a protected route is used; Then it challenges.
    response = private_client.open(endpoint, method=method, json={})
    assert response.status_code == 401
    assert response.headers['WWW-Authenticate'].startswith('Basic ')


def test_admin_closed_when_password_unconfigured(private_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given missing deployment credentials; When admin requested; Then no data leaks.
    monkeypatch.delenv('QR_ADMIN_PASSWORD')
    assert private_client.get('/admin', headers=credentials()).status_code == 503


def test_admin_denied_when_password_wrong(private_client: FlaskClient) -> None:
    # Given invalid credentials; When admin requested; Then it challenges.
    wrong = base64.b64encode(b'test-staff:wrong').decode('ascii')
    assert private_client.get('/admin', headers={'Authorization': 'Basic ' + wrong}).status_code == 401


def test_admin_not_cached_when_authenticated(private_client: FlaskClient) -> None:
    # Given credentials; When admin rendered; Then sensitive responses are not cached.
    response = private_client.get('/admin', headers=credentials())
    assert response.status_code == 200
    assert 'no-store' in response.headers['Cache-Control']


@pytest.mark.parametrize('endpoint', ['/master-order', '/delete-order', '/delete-all-orders'])
def test_mutation_denied_when_csrf_missing(private_client: FlaskClient, endpoint: str) -> None:
    # Given authenticated staff without token; When mutation requested; Then denied.
    assert private_client.post(endpoint, json={}, headers=credentials()).status_code == 403


def test_mutation_denied_when_csrf_wrong(private_client: FlaskClient) -> None:
    # Given a forged token; When clearing orders; Then denied.
    assert private_client.post('/delete-all-orders', headers={**credentials(), 'X-CSRF-Token': 'forged'}).status_code == 403


@pytest.mark.parametrize('seat', ['', ' ', '\n', '\x00', '9' * 33, '9' * 500])
def test_customer_rejected_when_seat_invalid(private_client: FlaskClient, seat: str) -> None:
    # Given a blank, control-character or overlong seat; When ordering; Then rejected.
    assert private_client.post('/order', query_string={'seat': seat}, json={'drink': '아메리카노(HOT)'}).status_code == 400


@pytest.mark.parametrize('body', ['[]', 'null', '{', '"text"'])
def test_customer_rejected_when_json_invalid(private_client: FlaskClient, body: str) -> None:
    # Given malformed/non-object JSON; When ordering; Then a clear 400 response.
    response = private_client.post('/order?seat=1', data=body, content_type='application/json')
    assert response.status_code == 400
    assert response.is_json


@pytest.mark.parametrize('drink', [None, '', 'unknown', 14, ['아메리카노(HOT)']])
def test_customer_rejected_when_drink_invalid(private_client: FlaskClient, drink) -> None:
    # Given a value outside the exact 14-menu contract; When posted; Then rejected.
    assert private_client.post('/order?seat=1', json={'drink': drink}).status_code == 400


@pytest.mark.parametrize('order_id', [0, -1, True, '1 OR 1=1', '1.5', None])
def test_delete_rejected_when_id_invalid(private_client: FlaskClient, order_id) -> None:
    # Given an invalid identifier; When deletion requested; Then clear error.
    assert private_client.post('/delete-order', json={'id': order_id}, headers=staff_headers(private_client)).status_code == 400


def test_db_persists_when_working_directory_changes(private_client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given the configured DB and another CWD; When ordering; Then same DB receives it.
    other = tmp_path / 'other'
    other.mkdir()
    monkeypatch.chdir(other)
    assert private_client.post('/order?seat=3', json={'drink': '아메리카노(HOT)'}).status_code == 200
    with sqlite3.connect(tmp_path / 'app.db') as conn:
        assert conn.execute('SELECT seat FROM orders').fetchall() == [('3',)]
    assert not (other / 'app.db').exists()


def test_order_unconfirmed_when_storage_unavailable(private_client: FlaskClient, tmp_path: Path) -> None:
    # Given SQLite replaced by a directory; When writing; Then no false success.
    (tmp_path / 'app.db').unlink()
    (tmp_path / 'app.db').mkdir()
    response = private_client.post('/order?seat=1', json={'drink': '아메리카노(HOT)'})
    assert response.status_code == 503
    assert 'error' in response.get_json()


def test_legacy_order_visible_when_seat_outside_current_map(private_client: FlaskClient, tmp_path: Path) -> None:
    # Given a historical non-map seat; When admin rendered; Then preserved order is visible.
    with sqlite3.connect(tmp_path / 'app.db') as conn:
        conn.execute("INSERT INTO orders(seat,drink) VALUES('A-7', '기존 음료')")
    page = private_client.get('/admin', headers=credentials()).get_data(as_text=True)
    assert '기존 자리 기록: A-7' in page and '기존 음료' in page


def test_csrf_rotated_when_password_changes(private_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given the old token and changed password; When used with new auth; Then token is rejected.
    old = staff_headers(private_client)['X-CSRF-Token']
    monkeypatch.setenv('QR_ADMIN_PASSWORD', 'rotated-test-only-password')
    auth = base64.b64encode(b'test-staff:rotated-test-only-password').decode('ascii')
    assert private_client.post('/delete-all-orders', headers={'Authorization': 'Basic ' + auth, 'X-CSRF-Token': old}).status_code == 403


def test_unicode_credentials_when_authorized(private_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given UTF-8 staff credentials; When admin accessed; Then authorized without a 500.
    monkeypatch.setenv('QR_ADMIN_USER', '직원')
    monkeypatch.setenv('QR_ADMIN_PASSWORD', '테스트전용비밀번호')
    auth = base64.b64encode('직원:테스트전용비밀번호'.encode('utf-8')).decode('ascii')
    assert private_client.get('/admin', headers={'Authorization': 'Basic ' + auth}).status_code == 200


def test_customer_rejected_when_json_too_deep(private_client: FlaskClient) -> None:
    response = private_client.post('/order?seat=1', data='[' * 1500 + '0' + ']' * 1500, content_type='application/json')
    assert response.status_code == 400


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def test_historical_drink_shown_exactly_when_not_current_menu(private_client: FlaskClient, tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / 'app.db') as conn:
        conn.execute("INSERT INTO orders(seat,drink) VALUES('2', '아메리카노(Decaf)')")
    parser = VisibleText()
    parser.feed(private_client.get('/admin', headers=credentials()).get_data(as_text=True))
    assert '아메리카노(Decaf)' in ''.join(parser.text)
