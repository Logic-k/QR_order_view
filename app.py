import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO
import eventlet

# Flask 애플리케이션 생성
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Firebase 설정
firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
if firebase_credentials:
    firebase_credentials_dict = json.loads(firebase_credentials)
    cred = credentials.Certificate(firebase_credentials_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase 연결 완료!")
else:
    print("❌ Firebase 환경 변수를 찾을 수 없습니다.")

# 주문 페이지
@app.route("/order", methods=["GET", "POST"])
def order():
    seat_number = request.args.get("seat", "1")

    if request.method == "POST":
        data = request.json
        order_data = {
            "seat": seat_number,
            "salt": data.get("saltType"),
            "drink": data.get("drink"),
            "status": "대기 중"
        }
        new_order_ref = db.collection("orders").add(order_data)
        order_data["id"] = new_order_ref[1].id

        # 실시간 주문 업데이트 (WebSocket 이벤트 전송)
        socketio.emit("new_order", order_data)

        return jsonify({"message": "주문이 완료되었습니다!"})

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
            <option value="아메리카노(HOT)">아메리카노(HOT)</option>
            <option value="아메리카노(COLD)">아메리카노(COLD)</option>
            <option value="캐모마일(HOT)">캐모마일(HOT)</option>
            <option value="캐모마일(COLD)">캐모마일(COLD)</option>
        </select><br/>
        <button onclick="placeOrder()">주문하기</button>
    </body>
    </html>
    ''', seat_number=seat_number)

# 관리자 페이지
@app.route("/admin")
def admin():
    orders = {order.to_dict().get("seat"): {**order.to_dict(), "id": order.id} for order in db.collection("orders").stream()}
    return render_template_string('''
    <html>
    <head>
        <title>관리자 페이지</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <script>
            var socket = io();
            socket.on('new_order', function(order) {
                location.reload();
            });
            socket.on('delete_order', function(order) {
                location.reload();
            });
            function deleteOrder(orderId) {
                fetch('/delete-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: orderId })
                }).then(() => location.reload());
            }
        </script>
    </head>
    <body>
        <h2>주문 관리</h2>
        <ul>
            {% for seat, order in orders.items() %}
                <li>
                    좌석 {{ seat }}: {{ order.salt }} + {{ order.drink }}
                    <button onclick="deleteOrder('{{ order.id }}')">삭제</button>
                </li>
            {% endfor %}
        </ul>
    </body>
    </html>
    ''', orders=orders)

# 개별 주문 삭제 API
@app.route("/delete-order", methods=["POST"])
def delete_order():
    order_id = request.json.get("id")
    if order_id:
        db.collection("orders").document(order_id).delete()
        socketio.emit("delete_order", {"id": order_id})
        return jsonify({"message": "주문이 삭제되었습니다."})
    return jsonify({"error": "유효한 주문 ID가 없습니다."}), 400

# WebSocket 실행
if __name__ == "__main__":
    eventlet.monkey_patch()
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, debug=True, host="0.0.0.0", port=port)