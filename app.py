import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify, render_template_string

# Flask 애플리케이션 생성 (이 부분이 없으면 Render에서 실행되지 않음)
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
        <h2>자리 {{ seat_number }}번 주문</h2>
        <label>족욕 소금 선택:</label>
        <select id="salt"><option value="라벤더">라벤더</option><option value="녹차">녹차</option></select><br/>
        <label>음료 선택:</label>
        <select id="drink"><option value="커피">커피</option><option value="차">차</option></select><br/>
        <button onclick="placeOrder()">주문하기</button>
    </body>
    </html>
    ''', seat_number=seat_number)

# 관리자 페이지 (주문 확인)
@app.route("/admin")
def admin():
    orders = db.collection("orders").stream()
    order_list = [
        f"자리 {o.get('seat')}: {o.get('salt')}, {o.get('drink')} ({o.get('status')})"
        for o in orders
    ]
    
    return "<br>".join(order_list) + '''<br><br><a href="/admin">새로고침</a>'''

# Render에서 실행될 때는 반드시 "app"이 정의되어 있어야 함
if __name__ == "__main__":
    app.run(debug=True)
