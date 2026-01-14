from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
import sqlite3
import re
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = "poolkaro-secret"
socketio = SocketIO(app)

DB = "rides.db"

# ================== DATABASE ==================

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destination TEXT,
            mode TEXT,
            max_seats INTEGER,
            status TEXT DEFAULT 'OPEN',
            created_at TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ride_id INTEGER,
            username TEXT,
            joined_at TEXT,
            UNIQUE(ride_id, username)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Database ready")

# ================== PARSE data.txt ==================

def save_destination(destination):
    with open("destination.txt", "w", encoding="utf-8") as f:
        f.write(destination + "\n")


def read_prices():
    prices = {
        "rapido": {"Bike": 0, "Auto": 0, "Cab": 0},
        "uber": {"Bike": 0, "Auto": 0, "Cab": 0}
    }
    
    try:
        with open("data.txt", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Split by Rapido and Uber sections
        current_provider = None
        
        for line in content.split("\n"):
            line = line.strip()
            
            if "rapido" in line.lower():
                current_provider = "rapido"
                continue
            elif "uber" in line.lower():
                current_provider = "uber"
                continue
            
            if not current_provider or not line:
                continue
            
            # Parse: "Bike = ₹46" or "Auto = 85"
            match = re.search(r'(bike|auto|cab)\s*(?:economy)?\s*=\s*₹?(\d+)', line, re.IGNORECASE)
            
            if match:
                mode_raw = match.group(1).lower()
                price = int(match.group(2))
                
                # Normalize mode name
                if mode_raw == "bike":
                    mode = "Bike"
                elif mode_raw == "auto":
                    mode = "Auto"
                elif mode_raw == "cab":
                    mode = "Cab"
                else:
                    continue
                
                prices[current_provider][mode] = price
        
        print(f"📄 Loaded prices: {prices}")
        return prices
        
    except FileNotFoundError:
        print("⚠️  data.txt not found, using defaults")
        return {
            "rapido": {"Bike": 50, "Auto": 90, "Cab": 110},
            "uber": {"Bike": 55, "Auto": 95, "Cab": 130}
        }

# ================== ROUTES ==================

@app.route("/")
def home():
    """Step 1: Enter destination"""
    return render_template("index.html")


@app.route("/prices", methods=["POST"])
def show_prices():
    """Step 2: Show prices from data.txt"""
    
    destination = request.form.get("destination", "").strip()
    
    if not destination:
        return redirect(url_for("home"))

    # ✅ SAVE destination to destination.txt
    save_destination(destination)

    # Read prices from data.txt
    prices = read_prices()
    
    # Build options for display
    modes = {
        "Bike": {"seats": 1, "chat": False},
        "Auto": {"seats": 3, "chat": True},
        "Cab": {"seats": 4, "chat": True}
    }
    
    options = []
    for mode, config in modes.items():
        rapido_price = prices["rapido"].get(mode, 0)
        uber_price = prices["uber"].get(mode, 0)
        best_price = min(rapido_price, uber_price) if rapido_price and uber_price else (rapido_price or uber_price)
        
        options.append({
            "mode": mode,
            "rapido": rapido_price,
            "uber": uber_price,
            "best": best_price,
            "per_person": round(best_price / config["seats"], 2),
            "seats": config["seats"],
            "chat": config["chat"]
        })
    
    return render_template("prices.html", 
        destination=destination, 
        options=options
    )


@app.route("/join", methods=["POST"])
def join():
    """Step 3: Join or create ride, get room ID"""
    
    destination = request.form.get("destination", "").strip()
    mode = request.form.get("mode", "").strip()
    username = request.form.get("username", "").strip()
    
    if not destination or not mode:
        return redirect(url_for("home"))
    
    if not username:
        username = f"Rider{int(datetime.now().timestamp()) % 10000}"
    
    # Seat config
    seats_config = {"Bike": 1, "Auto": 3, "Cab": 4}
    max_seats = seats_config.get(mode, 3)
    
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    # Find existing open ride for same destination + mode
    cur.execute("""
        SELECT r.id, r.max_seats, COUNT(p.id) as filled
        FROM rides r
        LEFT JOIN participants p ON r.id = p.ride_id
        WHERE r.destination = ? AND r.mode = ? AND r.status = 'OPEN'
        GROUP BY r.id
        HAVING filled < r.max_seats
        ORDER BY r.created_at DESC
        LIMIT 1
    """, (destination, mode))
    
    existing = cur.fetchone()
    
    if existing:
        ride_id = existing[0]
    else:
        # Create new ride
        cur.execute("""
            INSERT INTO rides (destination, mode, max_seats, status, created_at)
            VALUES (?, ?, ?, 'OPEN', ?)
        """, (destination, mode, max_seats, datetime.now().isoformat()))
        ride_id = cur.lastrowid
    
    # Add participant (ignore if already exists)
    try:
        cur.execute("""
            INSERT INTO participants (ride_id, username, joined_at)
            VALUES (?, ?, ?)
        """, (ride_id, username, datetime.now().isoformat()))
    except sqlite3.IntegrityError:
        pass  # Already joined
    
    # Check if ride is now full
    cur.execute("SELECT COUNT(*) FROM participants WHERE ride_id = ?", (ride_id,))
    count = cur.fetchone()[0]
    
    if count >= max_seats:
        cur.execute("UPDATE rides SET status = 'FULL' WHERE id = ?", (ride_id,))
    
    # Get all participants
    cur.execute("SELECT username FROM participants WHERE ride_id = ?", (ride_id,))
    participants = [row[0] for row in cur.fetchall()]
    
    conn.commit()
    conn.close()
    
    room_id = f"ride_{ride_id}"
    
    return render_template("room.html",
        room_id=room_id,
        ride_id=ride_id,
        destination=destination,
        mode=mode,
        username=username,
        participants=participants,
        max_seats=max_seats,
        chat_enabled=(mode != "Bike")
    )

# ================== SOCKET EVENTS ==================

@socketio.on("join_room")
def handle_join(data):
    room = data.get("room")
    username = data.get("username")
    
    join_room(room)
    emit("system", {"msg": f"🟢 {username} joined"}, room=room)


@socketio.on("send_message")
def handle_message(data):
    room = data.get("room")
    username = data.get("username")
    message = data.get("message", "").strip()
    
    if message:
        emit("chat", {
            "username": username,
            "message": message,
            "time": datetime.now().strftime("%H:%M")
        }, room=room)


@socketio.on("leave_room")
def handle_leave(data):
    room = data.get("room")
    username = data.get("username")
    
    emit("system", {"msg": f"🔴 {username} left"}, room=room)

# ================== START ==================

if __name__ == "__main__":
    init_db()
    print("\n🚗 Pool Karo running at http://localhost:5000\n")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
