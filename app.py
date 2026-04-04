import os
import sqlite3
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)

DB_FILE = "app.db"

# 테이블 생성
def create_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seat TEXT NOT NULL,
            drink TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '대기 중'
        )
    """)
    conn.commit()
    conn.close()

create_tables()

# 주문 페이지
@app.route("/order", methods=["GET", "POST"])
def order():
    seat_number = request.args.get("seat", "1")

    if request.method == "POST":
        data = request.json
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders (seat, drink)
            VALUES (?, ?)
        """, (seat_number, data.get("drink")))

        conn.commit()
        conn.close()

        return jsonify({"message": "주문이 완료되었습니다! (Order completed!) (订单已完成!)"})

    return render_template_string('''

<html>
<head>
<title>QR 주문</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>

body{
font-family:'Noto Sans',sans-serif;
margin:0;
padding:0;
display:flex;
flex-direction:column;
align-items:center;
justify-content:center;
height:100vh;
text-align:center;
background-color:#FAF3E0;
}

.container{
background:white;
padding:20px;
border-radius:12px;
box-shadow:0 4px 10px rgba(0,0,0,0.1);
max-width:350px;
width:90%;
}

select,button{
font-size:18px;
padding:10px;
margin:10px 0;
width:100%;
border-radius:8px;
border:1px solid #ccc;
}

button{
background-color:#4CAF50;
color:white;
border:none;
cursor:pointer;
}

button:hover{
background-color:#45a049;
}

.logo{
width:120px;
height:120px;
border-radius:50%;
object-fit:cover;
}

</style>

<script>

function placeOrder(){

let drink=document.getElementById('drink').value;

fetch(window.location.href,{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({drink:drink})
}).then(()=>{
window.location.href="/order-complete?seat="+{{seat_number}};
})

}

</script>

</head>

<body>

<img src="{{ url_for('static', filename='logo.png') }}" class="logo">

<div class="container">

<h2>자리 {{ seat_number }}번</h2>

<label>음료 선택</label>

<select id="drink">

<option value="아메리카노(HOT)">아메리카노 HOT</option>
<option value="아메리카노(COLD)">아메리카노 ICE</option>
<option value="캐모마일(HOT)">캐모마일 HOT</option>
<option value="캐모마일(COLD)">캐모마일 ICE</option>
<option value="페퍼민트(HOT)">페퍼민트 HOT</option>
<option value="페퍼민트(COLD)">페퍼민트 ICE</option>
<option value="루이보스(HOT)">루이보스 HOT</option>
<option value="루이보스(COLD)">루이보스 ICE</option>
<option value="얼그레이(HOT)">얼그레이 HOT</option>
<option value="얼그레이(COLD)">얼그레이 ICE</option>
<option value="핫초코">핫초코</option>
<option value="아이스티">아이스티</option>
<option value="사과주스">사과주스</option>
<option value="오렌지주스">오렌지주스</option>

</select>

<button onclick="placeOrder()">주문하기</button>

</div>

</body>
</html>

''', seat_number=seat_number)


# 주문 완료 페이지
@app.route("/order-complete")
def order_complete():
    seat_number = request.args.get("seat","1")

    return f"""
    <html>
    <body style='text-align:center;font-family:Noto Sans'>
    <h2>주문 완료</h2>
    <p>{seat_number}번 자리 주문이 접수되었습니다.</p>
    </body>
    </html>
    """


# 관리자 페이지
@app.route("/admin")
def admin():

    conn=sqlite3.connect(DB_FILE)
    cursor=conn.cursor()

    cursor.execute("SELECT * FROM orders")
    rows=cursor.fetchall()

    conn.close()

    orders={}

    for r in rows:
        order_id,seat,drink,status=r

        if seat not in orders:
            orders[seat]=[]

        orders[seat].append({
            "id":order_id,
            "drink":drink,
            "status":status
        })

    return render_template_string("""

<html>
<head>

<title>관리자 페이지</title>

<style>

body{
font-family:Noto Sans;
text-align:center;
background:#3b8ed6;
color:white;
}

.seat{
background:white;
color:black;
padding:10px;
margin:10px;
border-radius:10px;
display:inline-block;
width:120px;
}

button{
background:red;
color:white;
border:none;
padding:5px 10px;
cursor:pointer;
margin-top:5px;
}

</style>

<script>

function deleteOrder(id){

fetch('/delete-order',{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({id:id})
}).then(()=>location.reload())

}

</script>

</head>

<body>

<h2>주문 관리</h2>

{% for seat,items in orders.items() %}

<div class="seat">

<b>{{seat}}번</b>

{% for o in items %}

<div>{{o.drink}}</div>
<button onclick="deleteOrder('{{o.id}}')">삭제</button>

{% endfor %}

</div>

{% endfor %}

</body>
</html>

""",orders=orders)



@app.route("/delete-order",methods=["POST"])
def delete_order():

    order_id=request.json.get("id")

    conn=sqlite3.connect(DB_FILE)
    cursor=conn.cursor()

    cursor.execute("DELETE FROM orders WHERE id=?",(order_id,))

    conn.commit()
    conn.close()

    return jsonify({"message":"삭제 완료"})


@app.route("/delete-all-orders",methods=["POST"])
def delete_all_orders():

    conn=sqlite3.connect(DB_FILE)
    cursor=conn.cursor()

    cursor.execute("DELETE FROM orders")

    conn.commit()
    conn.close()

    return jsonify({"message":"전체 삭제"})


if __name__=="__main__":
    app.run(debug=True)