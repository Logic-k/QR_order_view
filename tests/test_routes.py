"""Synthetic Flask regression checks; every import uses a fresh temporary DB."""
import importlib.util
import os
import sqlite3
import sys
import base64
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask.testing import FlaskClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    # Given a private working directory, never the application data directory.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('QR_DATABASE_PATH', str(tmp_path / 'app.db'))
    monkeypatch.setenv('QR_ADMIN_USER', 'test-staff')
    monkeypatch.setenv('QR_ADMIN_PASSWORD', 'test-only-never-production')
    source = Path(os.environ.get('QR_TEST_ROOT', str(Path(__file__).resolve().parents[1]))) / 'app.py'
    spec = importlib.util.spec_from_file_location('qr_test_app', source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, 'qr_test_app', module)
    spec.loader.exec_module(module)
    module.app.config['TESTING'] = True
    client = module.app.test_client()
    client.environ_base['HTTP_AUTHORIZATION'] = 'Basic ' + base64.b64encode(
        b'test-staff:test-only-never-production'
    ).decode('ascii')
    page = client.get('/admin').get_data(as_text=True)
    token = re.search(r'name="csrf-token" content="([^"]+)"', page)
    if token:
        client.environ_base['HTTP_X_CSRF_TOKEN'] = token.group(1)
    return client


@pytest.mark.parametrize('seat', ['1', '12', 'A-7'])
def test_seat_when_order_page_requested(client: FlaskClient, seat: str) -> None:
    # Given a QR seat query; When rendered; Then seat text is retained.
    response = client.get('/order', query_string={'seat': seat})
    assert response.status_code == 200
    assert seat in response.get_data(as_text=True)


def test_drink_when_customer_submits(client: FlaskClient) -> None:
    # Given a synthetic drink; When posted; Then the exact seat/value is stored.
    response = client.post('/order?seat=12', json={'drink': '아메리카노(COLD)'})
    assert response.status_code == 200
    with sqlite3.connect('app.db') as conn:
        assert conn.execute('SELECT seat,drink FROM orders').fetchall() == [('12', '아메리카노(COLD)')]


def test_manual_when_staff_submits(client: FlaskClient) -> None:
    # Given a synthetic staff order; When submitted; Then it appears in admin.
    response = client.post('/master-order', json={'seat': '9', 'drink': '캐모마일(HOT)'})
    assert response.status_code == 200
    assert '캐모마일(HOT)' in client.get('/admin').get_data(as_text=True)


def test_manual_error_when_fields_missing(client: FlaskClient) -> None:
    # Given missing fields; When submitted; Then the existing error contract remains.
    assert client.post('/master-order', json={}).status_code == 400


def test_delete_when_order_exists(client: FlaskClient) -> None:
    # Given a synthetic order; When deleted; Then it is absent from the DB.
    client.post('/order?seat=1', json={'drink': '루이보스(HOT)'})
    assert client.post('/delete-order', json={'id': 1}).status_code == 200
    with sqlite3.connect('app.db') as conn:
        assert conn.execute('SELECT COUNT(*) FROM orders').fetchone() == (0,)


def test_delete_error_when_id_missing(client: FlaskClient) -> None:
    # Given no ID; When deletion requested; Then a 400 is returned.
    assert client.post('/delete-order', json={}).status_code == 400


def test_delete_all_when_orders_exist(client: FlaskClient) -> None:
    # Given synthetic orders; When cleared; Then no orders remain.
    client.post('/order?seat=2', json={'drink': '페퍼민트(COLD)'})
    client.post('/order?seat=3', json={'drink': '얼그레이(HOT)'})
    assert client.post('/delete-all-orders').status_code == 200
    with sqlite3.connect('app.db') as conn:
        assert conn.execute('SELECT COUNT(*) FROM orders').fetchone() == (0,)


def test_completion_when_requested(client: FlaskClient) -> None:
    # Given a seat; When completion rendered; Then seat and ad contracts remain.
    page = client.get('/order-complete?seat=12').get_data(as_text=True)
    assert '12' in page and 'DAN-NO3XVRFTivoc3r2E' in page and 'AF6385937' in page


def test_mobile_accessibility_when_admin_rendered(client: FlaskClient) -> None:
    # Given admin; When rendered; Then responsive viewport and document language exist.
    page = client.get('/admin').get_data(as_text=True)
    assert 'name="viewport"' in page and 'lang="ko"' in page


@pytest.mark.parametrize('drink', [
    '아메리카노(HOT)', '아메리카노(COLD)', '캐모마일(HOT)', '캐모마일(COLD)',
    '페퍼민트(HOT)', '페퍼민트(COLD)', '루이보스(HOT)', '루이보스(COLD)',
    '얼그레이(HOT)', '얼그레이(COLD)', '핫초코(Only HOT)', '아이스티(Only ICE)',
    '사과주스(Only ICE)', '오렌지주스(Only ICE)',
])
def test_menu_contract_when_drink_selected(client: FlaskClient, drink: str) -> None:
    # Given an original menu value; When ordering; Then exact value is stored.
    assert drink in client.get('/order?seat=1').get_data(as_text=True)
    assert client.post('/order?seat=1', json={'drink': drink}).status_code == 200
    with sqlite3.connect('app.db') as conn:
        assert conn.execute('SELECT drink FROM orders').fetchone() == (drink,)


def test_seat_escaping_when_query_contains_markup(client: FlaskClient) -> None:
    # Given untrusted seat text; When rendered; Then it cannot inject an element.
    page = client.get('/order', query_string={'seat': '<img src=x onerror=alert(1)>'}).get_data(as_text=True)
    assert '<img src=x onerror=alert(1)>' not in page
    assert '&lt;img' in page


class SeatMapParser(HTMLParser):
    """Accumulate the semantic current-seat markers from rendered HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.current_seats: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        fields = dict(attrs)
        seat = fields.get('data-map-seat')
        if fields.get('aria-current') == 'location' and seat is not None:
            self.current_seats.append(seat)


@pytest.mark.parametrize('seat', [str(n) for n in range(1, 13)])
def test_map_highlight_when_qr_seat_selected(client: FlaskClient, seat: str) -> None:
    # Given a seat QR; When order page renders; Then exactly that seat is marked.
    parser = SeatMapParser()
    parser.feed(client.get('/order', query_string={'seat': seat}).get_data(as_text=True))
    assert parser.current_seats == [seat]
