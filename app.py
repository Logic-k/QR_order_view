# 관리자 페이지 (자리 형상화 UI 적용)
@app.route("/admin")
def admin():
    orders_raw = db.collection("orders").stream()
    orders = {}

    for order in orders_raw:
        order_data = order.to_dict()
        seat_number = order_data.get("seat")
        if seat_number not in orders:
            orders[seat_number] = []
        orders[seat_number].append({**order_data, "id": order.id})

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
        </style>
        <script>
            function deleteOrder(orderId) {
                fetch('/delete-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: orderId })
                }).then(res => res.json()).then(() => location.reload());
            }
            function deleteAllOrders() {
                if (confirm('정말 모든 주문을 삭제하시겠습니까?')) {
                    fetch('/delete-all-orders', {
                        method: 'POST'
                    }).then(() => location.reload());
                }
            }
        </script>
    <script>
            setInterval(() => {
                location.reload();
            }, 5000); // 5초마다 새로고침
        </script>
    <script>
    let refreshTime = 5; // 새로고침 간격 (초 단위)
    function updateTimer() {
        document.getElementById('refresh-timer').innerText = `새로고침까지 ${refreshTime}초`;
        refreshTime--;
        if (refreshTime < 0) {
            location.reload();
        } else {
            setTimeout(updateTimer, 1000);
        }
    }
    document.addEventListener("DOMContentLoaded", updateTimer);
</script>    </head>
    <body>
        <h2>주문 관리</h2>
        <div class="layout">
            <div class="column">
                {% for seat_number in range(9, 13) %}
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
    </body>
    </html>
    ''', orders=orders)
