from flask import Flask, render_template, request, redirect,session
import sqlite3
import threading
import webbrowser
import os
import sys
if getattr(sys, 'frozen', False):
    resource_path = sys._MEIPASS
else:
    resource_path = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(resource_path, "templates"),
    static_folder=os.path.join(resource_path, "static")
)
app.secret_key="smartqueue-secret-key"

SERVICE_TIME = 5

def get_db():
    db_path = os.path.join(
        os.path.dirname(os.path.abspath(sys.executable))
        if getattr(sys, 'frozen', False)
        else os.path.dirname(os.path.abspath(__file__)),
        "queue.db"
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            token TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin123":

            session["admin_logged_in"] = True

            return redirect("/admin")

        else:

            return render_template(
                "login.html",
                error="Invalid username or password"
            )

    return render_template("login.html")
@app.route("/logout")
def logout():
    session.pop("admin_logged_in",None)
    return redirect("/login")
@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = get_db()

    current_serving = conn.execute("""
        SELECT * FROM customers
        WHERE status = 'serving'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    completed_customers = conn.execute("""
        SELECT * FROM customers
        WHERE status = 'completed'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        current_serving=current_serving,
        completed_customers=completed_customers
    )

@app.route("/")
def home():

    conn = get_db()

    # Get waiting customers
    customers = conn.execute("""
        SELECT * FROM customers
        WHERE status = 'waiting'
        ORDER BY id
    """).fetchall()

    # Add position and waiting time
    queue = []

    for position, customer in enumerate(customers):
        customer_data = dict(customer)
        customer_data["position"] = position + 1
        customer_data["wait_time"] = position * SERVICE_TIME
        queue.append(customer_data)

    # Get currently serving customer
    current_serving = conn.execute("""
        SELECT * FROM customers
        WHERE status = 'serving'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()
    completed_customers = conn.execute("""
        SELECT * FROM customers
        WHERE status = 'completed'
        ORDER BY id DESC
    """).fetchall()
    search_token = request.args.get("search")
    search_customer = None

    if search_token:
        search_customer = conn.execute("""
            SELECT * FROM customers
            WHERE token = ?
        """, (search_token.upper(),)).fetchone()
    new_token=request.args.get("token")
    new_customer=None
    if new_token:
        new_customer=conn.execute("""
            SELECT * FROM customers
            WHERE token=?
        """,(new_token,)).fetchone()

    conn.close()

    return render_template(
        "index.html",
        queue=queue,
        total_waiting=len(queue),
        current_serving=current_serving,
        completed_customers=completed_customers,
        new_customer=new_customer,
        search_customer=search_customer
    )
@app.route("/queue-status")
def queue_status():

    conn = get_db()

    customers = conn.execute("""
        SELECT * FROM customers
        WHERE status = 'waiting'
        ORDER BY id
    """).fetchall()

    current_serving = conn.execute("""
        SELECT * FROM customers
        WHERE status = 'serving'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    queue = []

    for position, customer in enumerate(customers):
        queue.append({
            "token": customer["token"],
            "name": customer["name"],
            "position": position + 1,
            "wait_time": position * SERVICE_TIME
        })

    return {
        "queue": queue,
        "current_serving": (
            {
                "token": current_serving["token"],
                "name": current_serving["name"]
            }
            if current_serving else None
        )
    }

@app.route("/add", methods=["POST"])
def add_customer():

    name = request.form.get("name", "").strip()

    if name:

        conn = get_db()

        # Generate next token number
        last_customer = conn.execute("""
            SELECT id FROM customers
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if last_customer:
            token_number = last_customer["id"] + 1
        else:
            token_number = 1

        token = f"A{token_number:02d}"

        # Save customer in database
        conn.execute("""
            INSERT INTO customers (name, token, status)
            VALUES (?, ?, ?)
        """, (name, token, "waiting"))

        conn.commit()
        conn.close()

    return redirect(f"/?token={token}")


@app.route("/next", methods=["POST"])
def call_next():
    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = get_db()

    # Finish the currently serving customer
    conn.execute("""
        UPDATE customers
        SET status = 'completed'
        WHERE status = 'serving'
    """)

    # Find the first waiting customer
    customer = conn.execute("""
        SELECT id FROM customers
        WHERE status = 'waiting'
        ORDER BY id
        LIMIT 1
    """).fetchone()

    if customer:

        # Make the next customer currently serving
        conn.execute("""
            UPDATE customers
            SET status = 'serving'
            WHERE id = ?
        """, (customer["id"],))

    conn.commit()
    conn.close()

    return redirect("/")

init_db()


if __name__ == "__main__":
    threading.Timer(1.5,lambda:webbrowser.open("http://127.0.0.1:5000/")
    ).start()
    app.run(host="0.0.0.0",port=5000,debug=False)