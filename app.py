import os
import sqlite3
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from datetime import datetime, timedelta

# Flask 애플리케이션 생성
app = Flask(__name__)

# 데이터베이스 파일 경로
DB_FILE = "app.db"

# 테이블 생성 (앱 실행 시 한 번 실행됨)
def create_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seat TEXT NOT NULL,
            salt TEXT NOT NULL,
            drink TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '대기 중'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            people_count INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            memo TEXT,
            assigned_seats TEXT
        )
    """)
    conn.commit()
    conn.close()

create_tables()


# ---------------------- 시간 슬롯 생성 ----------------------
def generate_time_slots(start="10:00", end="20:00", interval_minutes=10):
    slots = []
    t = datetime.strptime(start, "%H:%M")
    end_t = datetime.strptime(end, "%H:%M")
    while t < end_t:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=interval_minutes)
    return slots

# ---------------------- 예약 삭제 API ----------------------
@app.route("/delete-reservation/<int:reservation_id>", methods=["POST"])
def delete_reservation(reservation_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservations WHERE id=?", (reservation_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("reserve"))

# ---------------------- 예약 등록 및 시각화 ----------------------
@app.route("/reserve", methods=["GET", "POST"])
def reserve():
    if request.method == "POST":
        data = request.form
        name = data.get("name")
        start_time = data.get("start_time")
        duration = 30  # 고정 30분
        people_count = int(data.get("people_count"))
        payment_method = data.get("payment_method")
        memo = data.get("memo")
        assigned_seats = data.getlist("assigned_seats")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reservations
            (name, start_time, duration, people_count, payment_method, memo, assigned_seats)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, start_time, duration, people_count, payment_method, memo, ','.join(assigned_seats)))
        conn.commit()
        conn.close()
        return redirect(url_for("reserve"))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, assigned_seats, start_time, duration, memo FROM reservations")
    reservations = cursor.fetchall()
    conn.close()

    slots = generate_time_slots()
    seats = [str(i) for i in range(1, 13)]

    timetable = {slot: {seat: [] for seat in seats} for slot in slots}
    for rid, name, assigned, start, dur, memo in reservations:
        st = datetime.strptime(start, "%H:%M")
        for i in range(int(dur) // 10):
            t = (st + timedelta(minutes=10 * i)).strftime("%H:%M")
            if t not in timetable:
                continue
            for s in assigned.split(','):
                timetable[t][s].append(
    f"<div style='background:#d9edf7; border:1px solid #bce8f1; padding:3px; margin-bottom:2px; border-radius:4px; font-size:13px;'>"
    f"<strong>{name}</strong><br/><small>{memo}</small><br/>"
    f"<form method='POST' action='/delete-reservation/{rid}' style='margin-top:2px;'>"
    f"<button type='submit' style='font-size:10px; background:#f2dede; border:none; color:#a94442; border-radius:3px;'>삭제</button>"
    f"</form></div>"
)

    table_html = """
    <style>
    table { width: 100%; font-size: 14px; border-collapse: collapse; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
    th { background-color: #f2f2f2; }
    td > div { margin-bottom: 4px; }
    </style>
    <table><tr><th>시간</th>""" + ''.join(f"<th>{s}번</th>" for s in seats) + "</tr>"
    for time in slots:
        table_html += f"<tr><td>{time}</td>" + ''.join(f"<td>{''.join(timetable[time][s])}</td>" for s in seats) + "</tr>"
    table_html += "</table>"

    form_html = '''
    <h2>예약 등록</h2>
    <form method="POST">
        예약자명: <input name="name" required><br/>
        시작 시간: <input type="time" name="start_time" required><br/>
        인원 수: <input type="number" name="people_count" value="1" min="1" max="12" required><br/>
        결제 방식:
        <select name="payment_method">
            <option value="계좌이체">계좌이체</option>
            <option value="현금">현금</option>
            <option value="카드">카드</option>
        </select><br/>
        좌석 선택:<br/>
        ''' + ''.join(f'<label><input type="checkbox" name="assigned_seats" value="{s}">{s}번</label> ' for s in seats) + '''<br/>
        특이사항: <textarea name="memo"></textarea><br/>
        <button type="submit">예약 등록</button>
    </form>
    <h2>예약 현황</h2>
    '''

    return render_template_string(form_html + table_html)


# 주문 페이지 (QR 스캔)
@app.route("/order", methods=["GET", "POST"])
def order():
    seat_number = request.args.get("seat", "1")

    if request.method == "POST":
        data = request.json
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (seat, salt, drink) 
            VALUES (?, ?, ?)
        """, (seat_number, data.get("saltType"), data.get("drink")))
        conn.commit()
        conn.close()
        return jsonify({"message": "주문이 완료되었습니다! (Order completed!) (订单已完成!)"})

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
            .logo - container{
                position: fixed; /* 화면 최상단 고정 */
                top : 0;
                left: 50 %;
                transform: translateX(-50 %); /* 가운데 정렬 */
                width: 100 %;
                text - align: center;
                padding: 10px 0;
                z - index: 1000; /* 다른 요소보다 위에 위치 */
            }
            .logo{
                width: 120px;  /* 로고 크기 조절 */
                height: 120px;
                border - radius: 50 %; /* 원형 유지 */
                object - fit: cover;
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
                }).then(() => {
                    window.location.href = "/order-complete?seat=" + {{ seat_number }};
                });
            }
        </script>
    </head>
    <body>
	<div class="logo-container">
    		<img src="{{ url_for('static', filename='logo.png') }}" class="logo" alt="Logo">
	</div>
	<div class="announcement">
    		불편하신 점이 있다면 직원을 불러주세요😊<br/>
    		(If you have any inconvenience, please call a staff member!)<br/>
    		(如果有不便之处，请呼叫工作人员!)
	</div>
        <div class="container">
           <h2>자리 {{ seat_number }}번 (Seat No. {{ seat_number }}) (座位 {{ seat_number }})</h2>
           <label>족욕 소금 선택 (Foot Bath Salt) (足浴盐选择):</label>
            <select id="salt">
                <option value="라벤더">라벤더 (Lavender / 薰衣草)</option>
                <option value="스피아민트">스피아민트 (Spearmint / 留兰香)</option>
                <option value="히말라야">히말라야 (Himalayan / 喜马拉雅)</option>
            </select><br/>
            <label>음료 선택 (Drink Selection) (饮料选择):</label>
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
            <button onclick="placeOrder()">주문하기 (Order Now)</button>
        </div>
	<div class="announcement">즐거운 시간 보내세요! (Enjoy your time!) (祝您玩得开心!)</div>
    </body>
    </html>
    ''', seat_number=seat_number)

# ✅ 주문 완료 페이지 (애드핏 광고 배치)
@app.route("/order-complete")
def order_complete():
    seat_number = request.args.get("seat", "1")

    return render_template_string('''
    <html>
    <head>
        <title>주문 완료 | Order Complete | 订单完成</title>
        <meta name="robots" content="index, follow">
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
            .highlight {
                font-size: 20px;
                font-weight: bold;
                color: #4CAF50;
            }
            .announcement {
                margin-top: 15px;
                font-size: 14px;
                color: #666;
                line-height: 1.6;
            }
            /* ✅ 광고 배너 스타일 */
            .ad-container {
                margin-top: 20px;
                text-align: center;
                width: 100%;
            }
            .scroll-ad {
                width: 100%;
                text-align: center;
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🎉 주문 완료 | Order Complete | 订单完成</h2>
            <p>자리 <span class="highlight">{{ seat_number }}</span>번의 주문이 정상적으로 접수되었습니다.</p>
            <p>Order for seat <span class="highlight">{{ seat_number }}</span> has been successfully received.</p>
            <p>座位 <span class="highlight">{{ seat_number }}</span> 的订单已成功提交。</p>

            <p>주문이 준비되면 직원이 알려드립니다! 😊</p>
            <p>Our staff will notify you when your order is ready. 😊</p>
            <p>您的订单准备好后，工作人员会通知您。 😊</p>

            <div class="announcement">
                추가로 궁금한 사항이 있으면 직원을 불러주세요.<br/>
                If you have any inquiries, please call a staff member.<br/>
                如果您有任何疑问，请呼叫工作人员。
            </div>
            <p style="font-size: 14px; color: #666;"> "📢 광고 클릭은 개발자에게 큰 힘이 됩니다! | Clicking ads greatly supports the developer! | 点击广告对开发者大有帮助！"</p>

            <!-- ✅ 중앙 배너 광고 -->
            <div class="ad-container">
            <script type="text/javascript" src="//t1.daumcdn.net/kas/static/ba.min.js"></script>
            <ins class="kakao_ad_area" style="display:none;"
                 data-ad-unit="DAN-NO3XVRFTivoc3r2E"
                 data-ad-width="320"
                 data-ad-height="50"></ins>
            <script>
                kakaoAdfit.push({});
            </script>
            </div>
        </div>

            <!-- ✅ 스크롤 가능한 배너 광고 -->
            <div class="scroll-ad">
                <script src="https://ads-partners.coupang.com/g.js"></script>
                <script>
                    new PartnersCoupang.G({"id":848440,"template":"carousel","trackingCode":"AF6385937","width":"320","height":"100","tsource":""});
                </script>
            <!-- ✅ 대가성 문구 추가 (announcement 클래스 활용) -->
            <div class="announcement">
                ※ 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.<br/>
            </div>
    </body>
    </html>
    ''', seat_number=seat_number)



# 관리자 페이지 (자리 형상화 UI)
@app.route("/admin")
def admin():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
    orders_raw = cursor.fetchall()
    conn.close()

    orders = {}
    for order in orders_raw:
        order_id, seat, salt, drink, status = order
        if seat not in orders:
            orders[seat] = []
        orders[seat].append({"id": order_id, "salt": salt, "drink": drink, "status": status})

    return render_template_string('''
    <html>
    <head>
        <title>관리자 페이지</title>
        <style>
            body {
                font-family: 'Noto Sans', sans-serif;
                text-align: center;
                background: linear-gradient(to bottom, #3b8ed6, #dff6ff);
                color: white;
            }
            .layout {
                display: flex;
                flex-direction: row;
                align-items: center;
                justify-content: center;
                gap: 50px;
            }
            .seat-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 20px;
            }
            .seat {
                background: rgba(255, 255, 255, 0.8);
                padding: 10px;
                border-radius: 8px;
                text-align: center;
                color: black;
                font-size: 14px;
                font-weight: bold;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 80px;
                width: 80px;
                cursor: pointer;
                position: relative;
            }
            .seat.occupied {
                background: #ffcc00;
            }
            .seat .delete-btn {
                font-size: 12px;
                color: white;
                background: red;
                padding: 5px 10px;
                border-radius: 5px;
                cursor: pointer;
                border: none;
                margin-top: 5px;
            }
            .row {
                display: flex;
                justify-content: center;
                gap: 10px;
            }
            .column {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .delete-all-btn {
                margin-top: 20px;
                padding: 10px 15px;
                font-size: 16px;
                background: black;
                color: white;
                border: none;
                cursor: pointer;
                border-radius: 5px;
            }
            .delete-all-btn:hover {
                background: gray;
            }    
            .logo - container{
                position: fixed; /* 화면 최상단 고정 */
                top : 0;
                left: 50 %;
                transform: translateX(-50 %); /* 가운데 정렬 */
                width: 100 %;
                text - align: center;
                padding: 10px 0;
                z - index: 1000; /* 다른 요소보다 위에 위치 */
            }
            .logo{
                width: 120px;  /* 로고 크기 조절 */
                height: 120px;
                border - radius: 50 %; /* 원형 유지 */
                object - fit: cover;
            }
        </style>
        <script>
            function deleteOrder(orderId) {
                fetch('/delete-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: orderId })
                }).then(() => location.reload());
            }
            function deleteAllOrders() {
                fetch('/delete-all-orders', {
                    method: 'POST'
                }).then(() => location.reload());
            }
        </script>
    <script>
            setInterval(() => {
                location.reload();
            }, 30000); // 30초마다 새로고침
        </script>
        <script>
            function toggleMasterForm() {
                const form = document.getElementById("master-order-form");
                form.style.display = form.style.display === "none" ? "block" : "none";
            }

            function submitMasterOrder() {
                const seat = document.getElementById("master-seat").value;
                const salt = document.getElementById("master-salt").value;
                const drink = document.getElementById("master-drink").value;

                if (!seat || !salt || !drink) {
                    alert("모든 항목을 선택해주세요.");
                    return;
                }

                fetch('/master-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ seat: seat, saltType: salt, drink: drink })
                }).then(res => res.json()).then(data => {
                    alert(data.message);
                    location.reload();
                });
            }
        </script>
    </head>
    <body>
	<div class="logo-container">
    		<img src="{{ url_for('static', filename='logo.png') }}" class="logo" alt="Logo">
	</div>
        <h2>주문 관리</h2>
        <div class="layout">
            <div class="column">
                {% for seat_number in range(12, 8, -1) %}
                    <div class="seat {% if orders.get(seat_number|string) %}occupied{% endif %}">
                        {{ seat_number }}번
                        {% for order in orders.get(seat_number|string, []) %}
                            <div>{{ order.salt }}</div>
                            <div>{{ order.drink }}</div>
                            <button class="delete-btn" onclick="deleteOrder('{{ order.id }}')">삭제</button>
                        {% endfor %}
                    </div>
                {% endfor %}
            </div>
            <div class="seat-container">
                <div class="row">
                    {% for seat_number in range(1, 9) %}
                        <div class="seat {% if orders.get(seat_number|string) %}occupied{% endif %}">
                            {{ seat_number }}번
                            {% for order in orders.get(seat_number|string, []) %}
                                <div>{{ order.salt }}</div>
                                <div>{{ order.drink }}</div>
                                <button class="delete-btn" onclick="deleteOrder('{{ order.id }}')">삭제</button>
                            {% endfor %}
                        </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        <button class="delete-all-btn" onclick="deleteAllOrders()">모든 주문 삭제</button>
        <button onclick="toggleMasterForm()">마스터 주문 입력</button>

        <div id="master-order-form" style="display: none; margin-top: 20px; background: white; padding: 15px; color: black; border-radius: 10px;">
            <h3>마스터 주문 입력</h3>
        <label>자리 번호:</label>
        <select id="master-seat" style="padding:5px;">
          {% for num in range(1, 13) %}
            <option value="{{ num }}">{{ num }}번</option>
          {% endfor %}
        </select><br/>
            <label>소금 선택:</label>
            <select id="master-salt" style="padding:5px;">
                <option value="라벤더">라벤더</option>
                <option value="스피아민트">스피아민트</option>
                <option value="히말라야">히말라야</option>
            </select><br/>
            <label>음료 선택:</label>
            <select id="master-drink" style="padding:5px;">
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
            <button onclick="submitMasterOrder()" style="margin-top:10px;">주문 등록</button>
        </div>
    </body>
    </html>
    ''', orders=orders, range=range)

# 개별 주문 삭제 API
@app.route("/delete-order", methods=["POST"])
def delete_order():
    order_id = request.json.get("id")
    if order_id:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE id=?", (order_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "주문이 삭제되었습니다."})
    return jsonify({"error": "유효한 주문 ID가 없습니다."}), 400

# 모든 주문 삭제 API
@app.route("/delete-all-orders", methods=["POST"])
def delete_all_orders():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders")
    conn.commit()
    conn.close()
    return jsonify({"message": "모든 주문이 삭제되었습니다."})

# 마스터 주문 입력 API (관리자가 수동으로 주문)
@app.route("/master-order", methods=["POST"])
def master_order():
    data = request.json
    seat = data.get("seat")
    salt = data.get("saltType")
    drink = data.get("drink")

    if seat and salt and drink:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (seat, salt, drink)
            VALUES (?, ?, ?)
        """, (seat, salt, drink))
        conn.commit()
        conn.close()
        return jsonify({"message": f"{seat}번 자리에 마스터 주문이 등록되었습니다."})
    return jsonify({"error": "모든 필드를 입력해주세요."}), 400

#크롤러 허용 설정
@app.route("/robots.txt")
def robots():
	return "User-agent: *\nDisallow:", 200, {"Content-Type" : "text/plain"}

# Flask 서버 실행
if __name__ == "__main__":
    app.run(debug=True)
