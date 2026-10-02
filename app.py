import hashlib
import hmac
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Final, NewType, TypeAlias, TypedDict

from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8192
DB_FILE: Final = str(Path(os.environ.get('QR_DATABASE_PATH', Path(__file__).with_name('app.db'))).resolve())
ADMIN_ENDPOINTS: Final = frozenset({'admin', 'master_order', 'delete_order', 'delete_all_orders'})
SEATS: Final = frozenset(str(number) for number in range(1, 13))
DRINKS: Final = frozenset({
    '아메리카노(HOT)', '아메리카노(COLD)', '캐모마일(HOT)', '캐모마일(COLD)',
    '페퍼민트(HOT)', '페퍼민트(COLD)', '루이보스(HOT)', '루이보스(COLD)',
    '얼그레이(HOT)', '얼그레이(COLD)', '핫초코(Only HOT)', '아이스티(Only ICE)',
    '사과주스(Only ICE)', '오렌지주스(Only ICE)',
})
Seat = NewType('Seat', str)
Drink = NewType('Drink', str)
OrderId = NewType('OrderId', int)
JsonValue: TypeAlias = str | int | float | bool | None | list['JsonValue'] | dict[str, 'JsonValue']
RouteResult: TypeAlias = str | Response | tuple[Response, int]


class StoredOrder(TypedDict):
    id: int
    drink: str
    status: str


def csrf_token() -> str:
    # Password-keyed HMAC shares tokens across Gunicorn workers and rotates with credentials.
    return hmac.new(
        os.environ.get('QR_ADMIN_PASSWORD', '').encode('utf-8'),
        ('qr-admin-csrf:v1:' + os.environ.get('QR_ADMIN_USER', 'admin')).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


@app.before_request
def protect_admin() -> RouteResult | None:
    if request.endpoint not in ADMIN_ENDPOINTS:
        return None
    username = os.environ.get('QR_ADMIN_USER', 'admin')
    password = os.environ.get('QR_ADMIN_PASSWORD', '')
    if not username or not password:
        return jsonify(error='관리자 접근 설정이 필요합니다.'), 503
    auth = request.authorization
    user_ok = hmac.compare_digest((auth.username or '').encode('utf-8'), username.encode('utf-8')) if auth else False
    password_ok = hmac.compare_digest((auth.password or '').encode('utf-8'), password.encode('utf-8')) if auth else False
    if not (auth and auth.type.lower() == 'basic' and user_ok and password_ok):
        response = jsonify(error='관리자 인증이 필요합니다.')
        response.status_code = 401
        response.headers['WWW-Authenticate'] = 'Basic realm="QR staff", charset="UTF-8"'
        return response
    if request.method == 'POST' and not hmac.compare_digest(
        request.headers.get('X-CSRF-Token', '').encode('utf-8'), csrf_token().encode('utf-8')
    ):
        return jsonify(error='페이지를 새로고침한 후 다시 시도해주세요.'), 403
    return None


@app.after_request
def prevent_admin_cache(response: Response) -> Response:
    if request.endpoint in ADMIN_ENDPOINTS:
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['Vary'] = 'Authorization'
    return response


@app.errorhandler(sqlite3.Error)
def storage_error(error: sqlite3.Error) -> tuple[Response, int]:
    app.logger.exception('Order storage failed', exc_info=error)
    return jsonify(error='주문 처리를 확인할 수 없습니다. 직원에게 확인해주세요.'), 503


def parse_seat(raw: JsonValue) -> Seat | None:
    if isinstance(raw, str) and raw.strip() and raw.isprintable() and len(raw) <= 32:
        return Seat(raw)
    return None


def parse_drink(raw: JsonValue) -> Drink | None:
    if isinstance(raw, str) and raw in DRINKS:
        return Drink(raw)
    return None


def parse_order_id(raw: JsonValue) -> OrderId | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int) and 0 < raw <= 9223372036854775807:
        return OrderId(raw)
    if isinstance(raw, str) and raw.isascii() and raw.isdigit() and len(raw) <= 19:
        number = int(raw)
        if 0 < number <= 9223372036854775807:
            return OrderId(number)
    return None


def create_tables() -> None:
    with closing(sqlite3.connect(DB_FILE)) as conn, conn:
        _ = conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seat TEXT NOT NULL,
                drink TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '대기 중'
            )
        """)


create_tables()


@app.route('/order', methods=['GET', 'POST'])
def order() -> RouteResult:
    seat_number = parse_seat(request.args.get('seat', '1'))
    if seat_number is None:
        return jsonify(error='유효한 자리 표시(1~32자)가 필요합니다.'), 400
    if request.method == 'POST':
        data: JsonValue = request.get_json(silent=True)
        drink = parse_drink(data.get('drink')) if isinstance(data, dict) else None
        if drink is None:
            return jsonify(error='메뉴에서 음료를 선택해주세요.'), 400
        with closing(sqlite3.connect(DB_FILE)) as conn, conn:
            _ = conn.execute('INSERT INTO orders (seat, drink) VALUES (?, ?)', (seat_number, drink))
        return jsonify(message='주문이 완료되었습니다! (Order completed!) (订单已完成!)')
    return render_template('order.html', seat_number=seat_number, valid_drinks=DRINKS)


@app.route('/order-complete')
def order_complete() -> RouteResult:
    seat_number = parse_seat(request.args.get('seat', '1'))
    if seat_number is None:
        return jsonify(error='유효한 자리 표시(1~32자)가 필요합니다.'), 400
    return render_template('complete.html', seat_number=seat_number)


@app.route('/admin')
def admin() -> str:
    with closing(sqlite3.connect(DB_FILE)) as conn:
        orders_raw: list[tuple[int, str, str, str]] = conn.execute('SELECT id, seat, drink, status FROM orders ORDER BY id').fetchall()
    orders: dict[str, list[StoredOrder]] = {}
    for order_id, seat, drink, status in orders_raw:
        orders.setdefault(seat, []).append({'id': order_id, 'drink': drink, 'status': status})
    return render_template('admin.html', orders=orders, range=range, csrf_token=csrf_token(), valid_seats=SEATS, valid_drinks=DRINKS)


@app.route('/delete-order', methods=['POST'])
def delete_order() -> RouteResult:
    data: JsonValue = request.get_json(silent=True)
    order_id = parse_order_id(data.get('id')) if isinstance(data, dict) else None
    if order_id is not None:
        with closing(sqlite3.connect(DB_FILE)) as conn, conn:
            _ = conn.execute('DELETE FROM orders WHERE id=?', (order_id,))
        return jsonify(message='주문이 삭제되었습니다.')
    return jsonify(error='유효한 주문 ID가 없습니다.'), 400


@app.route('/delete-all-orders', methods=['POST'])
def delete_all_orders() -> Response:
    with closing(sqlite3.connect(DB_FILE)) as conn, conn:
        _ = conn.execute('DELETE FROM orders')
    return jsonify(message='모든 주문이 삭제되었습니다.')


@app.route('/master-order', methods=['POST'])
def master_order() -> RouteResult:
    data: JsonValue = request.get_json(silent=True)
    seat = parse_seat(data.get('seat')) if isinstance(data, dict) else None
    drink = parse_drink(data.get('drink')) if isinstance(data, dict) else None
    if seat and drink:
        with closing(sqlite3.connect(DB_FILE)) as conn, conn:
            _ = conn.execute('INSERT INTO orders (seat, drink) VALUES (?, ?)', (seat, drink))
        return jsonify(message=f'{seat}번 자리에 마스터 주문이 등록되었습니다.')
    return jsonify(error='자리와 메뉴의 음료를 선택해주세요.'), 400


@app.route('/robots.txt')
def robots() -> tuple[str, int, dict[str, str]]:
    return 'User-agent: *\nDisallow:', 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
