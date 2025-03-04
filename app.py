import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy

# Flask 애플리케이션 생성
app = Flask(__name__)

# SQLite 데이터베이스 설정
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
# SQLite 데이터베이스 연결 설정
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  

db = SQLAlchemy(app)

with app.app_context():
    db.create_all()
    print("✅ 데이터베이스가 생성되었습니다!")

# 주문 테이블 정의
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seat = db.Column(db.String(10), nullable=False)
    salt = db.Column(db.String(50), nullable=False)
    drink = db.Column(db.String(50), nullable=False)

# 주문 로그 테이블 (주문이 삭제되더라도 기록을 남김)
class OrderLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seat = db.Column(db.String(10), nullable=False)
    salt = db.Column(db.String(50), nullable=False)
    drink = db.Column(db.String(50), nullable=False)

# 데이터베이스 초기화 함수
def init_db():
    with app.app_context():
        db.create_all()
        print("✅ SQLite 데이터베이스가 초기화되었습니다!")

# Flask 실행 시 DB 초기화
if __name__ == "__main__":
    init_db()
    app.run(debug=True)


@app.route("/order", methods=["GET", "POST"])
def order():
    seat_number = request.args.get("seat", "1")

    if request.method == "POST":
        data = request.json
        new_order = Order(
            seat=seat_number,
            salt=data.get("saltType"),
            drink=data.get("drink")
        )
        db.session.add(new_order)
        db.session.commit()

        # 주문 로그에도 저장 (관리자가 주문을 삭제해도 기록은 남김)
        new_log = OrderLog(
            seat=seat_number,
            salt=data.get("saltType"),
            drink=data.get("drink")
        )
        db.session.add(new_log)
        db.session.commit()

        return jsonify({"message": "주문이 완료되었습니다! (Order completed!) (订单已完成!)"})

    return render_template_string('''
    <html>
    <head>
        <title>QR 주문</title>
        <script>
            function placeOrder() {
                let salt = document.getElementById('salt').value;
                let drink = document.getElementById('drink').value;
                fetch(window.location.href, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ saltType: salt, drink: drink })
                }).then(res => res.json()).then(data => alert(data.message));
            }
        </script>
    </head>
    <body>
        <h2>자리 {{ seat_number }}번</h2>
        <label>족욕 소금 선택:</label>
        <select id="salt">
            <option value="라벤더">라벤더</option>
            <option value="스피아민트">스피아민트</option>
            <option value="히말라야">히말라야</option>
        </select><br/>
        <label>음료 선택:</label>
        <select id="drink">
            <option value="아메리카노">아메리카노</option>
            <option value="캐모마일">캐모마일</option>
            <option value="루이보스">루이보스</option>
        </select><br/>
        <button onclick="placeOrder()">주문하기</button>
    </body>
    </html>
    ''', seat_number=seat_number)


@app.route("/admin")
def admin():
    orders = Order.query.all()  # 현재 주문 목록 가져오기
    order_logs = OrderLog.query.all()  # 주문 로그 가져오기

    return render_template_string('''
    <html>
    <head>
        <title>관리자 페이지</title>
        <script>
            function deleteOrder(orderId) {
                fetch('/delete-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: orderId })
                }).then(() => location.reload());
            }
            function deleteAllOrders() {
                fetch('/delete-all-orders', { method: 'POST' }).then(() => location.reload());
            }
        </script>
    </head>
    <body>
        <h2>주문 관리</h2>
        <table border="1">
            <tr>
                <th>주문번호</th>
                <th>자리</th>
                <th>족욕 소금</th>
                <th>음료</th>
                <th>삭제</th>
            </tr>
            {% for order in orders %}
            <tr>
                <td>{{ order.id }}</td>
                <td>{{ order.seat }}</td>
                <td>{{ order.salt }}</td>
                <td>{{ order.drink }}</td>
                <td><button onclick="deleteOrder('{{ order.id }}')">삭제</button></td>
            </tr>
            {% endfor %}
        </table>
        <button onclick="deleteAllOrders()">모든 주문 삭제</button>

        <h2>주문 로그</h2>
        <table border="1">
            <tr>
                <th>주문번호</th>
                <th>자리</th>
                <th>족욕 소금</th>
                <th>음료</th>
            </tr>
            {% for log in order_logs %}
            <tr>
                <td>{{ log.id }}</td>
                <td>{{ log.seat }}</td>
                <td>{{ log.salt }}</td>
                <td>{{ log.drink }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    ''', orders=orders, order_logs=order_logs)

@app.route("/delete-order", methods=["POST"])
def delete_order():
    order_id = request.json.get("id")
    order = Order.query.get(order_id)
    if order:
        db.session.delete(order)
        db.session.commit()
        return jsonify({"message": "주문이 삭제되었습니다."})
    return jsonify({"error": "유효한 주문 ID가 없습니다."}), 400

@app.route("/delete-all-orders", methods=["POST"])
def delete_all_orders():
    db.session.query(Order).delete()
    db.session.commit()
    return jsonify({"message": "모든 주문이 삭제되었습니다."})



