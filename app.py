import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify, render_template_string

# Flask 애플리케이션 생성
app = Flask(__name__)

# 환경 변수에서 Firebase JSON 키 가져오기
firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")

if firebase_credentials:
    firebase_credentials_dict = json.loads(firebase_credentials)  # JSON 문자열을 Python 딕셔너리로 변환
    cred = credentials.Certificate(firebase_credentials_dict)  # Firebase 인증 객체 생성
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
        db.collection("orders").add(order_data)
        return jsonify({"message": "주문이 완료되었습니다!"})

    return render_template_string('''
    <html>
    <head>
        <title>QR 주문</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: 'Noto Sans', sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                text-align: center;
                background-color: #FAF3E0;
            }
            .container {
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
                max-width: 350px;
                width: 90%;
            }
            select, button {
                font-size: 18px;
                padding: 10px;
                margin: 10px 0;
                width: 100%;
                border-radius: 8px;
                border: 1px solid #ccc;
            }
            button {
                background-color: #4CAF50;
                color: white;
                border: none;
                cursor: pointer;
            }
            button:hover {
                background-color: #45a049;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            table, th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: center;
            }
            th {
                background-color: #4CAF50;
                color: white;
            }
        </style>
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
            function deleteOrder(orderId) {
                fetch('/delete-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: orderId })
                }).then(() => window.location.reload());
            }
            function deleteAllOrders() {
                fetch('/delete-all-orders', {
                    method: 'POST'
                }).then(() => window.location.reload());
            }
        </script>
    </head>
    <body>
        <div class="container">
            <h2>자리 {{ seat_number }}번 주문</h2>
            <label>족욕 소금 선택:</label>
            <select id="salt">
                <option value="라벤더">라벤더 (Lavender / 薰衣草)</option>
                <option value="스피아민트">스피아민트 (Spearmint / 留兰香)</option>
                <option value="히말라야">히말라야 (Himalayan / 喜马拉雅)</option>
            </select><br/>
            <label>음료 선택:</label>
            <select id="drink">
    <option value="아메리카노(HOT)">아메리카노(HOT) / 美式咖啡 (热)</option>
    <option value="아메리카노(COLD)">아메리카노(COLD) / 美式咖啡 (冰)</option>
    <option value="캐모마일(HOT)">캐모마일(HOT) / 洋甘菊茶 (热)</option>
    <option value="캐모마일(COLD)">캐모마일(COLD) / 洋甘菊茶 (冰)</option>
    <option value="페퍼민트(HOT)">페퍼민트(HOT) / 薄荷茶 (热)</option>
    <option value="페퍼민트(COLD)">페퍼민트(COLD) / 薄荷茶 (冰)</option>
    <option value="루이보스(HOT)">루이보스(HOT) / 南非红茶 (热)</option>
    <option value="루이보스(COLD)">루이보스(COLD) / 南非红茶 (冰)</option>
    <option value="얼그레이(HOT)">얼그레이(HOT) / 伯爵茶 (热)</option>
    <option value="얼그레이(COLD)">얼그레이(COLD) / 伯爵茶 (冰)</option>
    <option value="핫초코(Only HOT)">핫초코(Only HOT) / 热巧克力</option>
    <option value="아이스티(Only ICE)">아이스티(Only ICE) / 冰茶</option>
    <option value="사과주스(Only ICE)">사과주스(Only ICE) / 苹果汁</option>
    <option value="오렌지주스(Only ICE)">오렌지주스(Only ICE) / 橙汁</option>
</select><br/>
            <button onclick="placeOrder()">주문하기</button>
        </div>
    </body>
    </html>
    ''', seat_number=seat_number)

# 관리자 페이지 (표 형식 + 삭제 기능 추가)
@app.route("/admin")
def admin():
    orders = db.collection("orders").stream()
    order_rows = "".join(
        f"<tr><td>{order.to_dict().get('seat')}</td><td>{order.to_dict().get('salt')}</td><td>{order.to_dict().get('drink')}</td><td><button onclick=\"deleteOrder('{order.id}')\">삭제</button></td></tr>"
        for order in orders
    )
    
    return render_template_string('''
    <html>
    <head>
        <title>관리자 페이지</title>
        <style>
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #4CAF50; color: white; }
        </style>
    </head>
    <body>
        <h2>주문 관리</h2>
        <table>
            <tr>
                <th>자리</th>
                <th>족욕 소금</th>
                <th>음료</th>
                <th>삭제</th>
            </tr>
            {{ order_rows|safe }}
        </table>
        <br>
        <button onclick="deleteAllOrders()">모든 주문 삭제</button>
    </body>
    </html>
    ''', order_rows=order_rows)
