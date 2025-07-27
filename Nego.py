import os
import time
import uuid
from datetime import datetime
from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = 'tutaj_wstaw_tajny_klucz'  # Upewnij się, że używasz bezpiecznego klucza!
socketio = SocketIO(app, cors_allowed_origins="*")

# Inicjalizacja Flask-Limiter – aplikacja przekazywana jako app=app
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=[])

# Konfiguracja dla uploadu plików
app.config["UPLOAD_FOLDER"] = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Globalne słowniki przechowujące dane użytkowników, tokeny weryfikacyjne, tokeny resetujące oraz aukcje
users = {}
email_verification_tokens = {}
password_reset_tokens = {}
auctions = {}

# Rejestracja filtra datetimeformat do szablonów Jinja2
@app.template_filter('datetimeformat')
def datetimeformat_filter(timestamp):
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%dT%H:%M')

def check_auction_status(auction):
    if auction.get("startTime") is not None and auction.get("isActive", False):
        now = time.time()
        if now >= auction["startTime"] + auction["duration"]:
            auction["isActive"] = False
            socketio.emit("auction_ended", {"auction_id": auction["auction_id"]})

# --------------------- REJESTRACJA, WERYFIKACJA E‑MAIL I LOGOWANIE --------------------- #

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        if not email or not username or not password or not confirm_password:
            flash("Wszystkie pola są wymagane", "danger")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("Hasła nie są takie same", "danger")
            return redirect(url_for("register"))
        if email in users:
            flash("Użytkownik z tym adresem e‑mail już istnieje", "danger")
            return redirect(url_for("register"))
        # Zapisujemy użytkownika jako niezweryfikowanego
        users[email] = {
            "username": username,
            "password": generate_password_hash(password),
            "is_verified": False
        }
        # Generujemy token weryfikacyjny
        token = str(uuid.uuid4())
        email_verification_tokens[token] = email
        verify_link = url_for("verify_email", token=token, _external=True)
        # W produkcyjnej aplikacji link należy wysłać e‑mailowo
        flash(f"Konto zostało utworzone. Aby je aktywować, kliknij w link weryfikacyjny (demo): {verify_link}", "info")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route('/verify/<token>')
def verify_email(token):
    email = email_verification_tokens.get(token)
    if not email:
        flash("Token weryfikacyjny jest nieprawidłowy lub wygasł", "danger")
        return redirect(url_for("login"))
    # Oznaczamy konto jako zweryfikowane
    users[email]["is_verified"] = True
    del email_verification_tokens[token]
    flash("Adres e‑mail został zweryfikowany. Możesz się teraz zalogować.", "success")
    return redirect(url_for("login"))

# Ograniczenie prób logowania do 5 na minutę (dla danego IP)
@app.route('/login', methods=["GET", "POST"])
@limiter.limit("5 per minute", error_message="Za dużo prób logowania, spróbuj ponownie za minutę.")
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        # Wyjątek dla administratora – logowanie bez weryfikacji
        if email == "admin@admin.admin" and password == "admin":
            session["user"] = {"email": "admin", "username": "admin"}
            session["username"] = "admin"
            flash("Zalogowano jako administrator", "success")
            return redirect(url_for("index"))
        if not email or not password:
            flash("Musisz podać e‑mail i hasło", "danger")
            return redirect(url_for("login"))
        user = users.get(email)
        if user is None or not check_password_hash(user["password"], password):
            flash("Nieprawidłowe dane logowania", "danger")
            return redirect(url_for("login"))
        if not user.get("is_verified"):
            flash("Konto nie zostało zweryfikowane. Sprawdź swój e‑mail i kliknij w link weryfikacyjny.", "warning")
            return redirect(url_for("login"))
        session["user"] = {"email": email, "username": user["username"]}
        session["username"] = user["username"]
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop("user", None)
    session.pop("username", None)
    return redirect(url_for("login"))

# --------------------- RESETOWANIE HASŁA --------------------- #

@app.route('/reset-request', methods=["GET", "POST"])
def reset_request():
    if request.method == "POST":
        email = request.form.get("email")
        if email not in users:
            flash("Podany adres e‑mail nie został znaleziony", "danger")
            return redirect(url_for("reset_request"))
        token = str(uuid.uuid4())
        password_reset_tokens[token] = email
        reset_link = url_for("reset_password", token=token, _external=True)
        # W produkcyjnej aplikacji link resetujący należy wysłać e‑mailowo
        flash(f"Link do resetowania hasła (demo): {reset_link}", "info")
        return redirect(url_for("login"))
    return render_template("reset_request.html")

@app.route('/reset/<token>', methods=["GET", "POST"])
def reset_password(token):
    email = password_reset_tokens.get(token)
    if not email:
        flash("Token resetowania hasła jest nieprawidłowy lub wygasł", "danger")
        return redirect(url_for("reset_request"))
    if request.method == "POST":
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        if new_password != confirm_password:
            flash("Hasła nie są takie same", "danger")
            return redirect(url_for("reset_password", token=token))
        users[email]["password"] = generate_password_hash(new_password)
        del password_reset_tokens[token]
        flash("Hasło zostało zresetowane. Możesz się teraz zalogować.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", token=token)

# --------------------- STRONY APLIKACJI I AUKCJE --------------------- #

@app.route('/')
def index():
    if "username" not in session:
        return redirect(url_for("login"))
    for auction in auctions.values():
        check_auction_status(auction)
    return render_template("index.html", auctions=auctions)

@app.route('/new-auction', methods=["POST"])
def new_auction():
    auction_id = str(uuid.uuid4())
    auction_data = {
        "auction_id": auction_id,
        "item": request.form["item"],
        "startingPrice": int(request.form["startingPrice"]),
        "duration": int(request.form["duration"]),
        "minIncrement": int(request.form["minIncrement"]),
        "startTime": None,
        "lowestBid": None,
        "bids": [],
        "isActive": True,
        "invited_users": {}
    }
    start_time_str = request.form["startTime"]
    try:
        auction_data["startTime"] = int(datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M").timestamp())
    except ValueError:
        return "Nieprawidłowy format daty.", 400
    auctions[auction_id] = auction_data
    return redirect(url_for("admin", auction_id=auction_id))

@app.route('/new-auction_ajax', methods=["GET"])
def new_auction_ajax():
    return render_template("new_auction_ajax.html")

@app.route('/login-auction', methods=["GET", "POST"])
def login_auction():
    auction_id = request.args.get("auction_id")
    if request.method == "POST":
        auction_id = request.form.get("auction_id")
        username = request.form.get("username")
        if not auction_id or auction_id not in auctions:
            return "Aukcja nie istnieje", 404
        check_auction_status(auctions[auction_id])
        return redirect(url_for("admin", auction_id=auction_id))
    if auction_id:
        return render_template("login_auction.html", auction_id=auction_id)
    else:
        active_auctions = {aid: a for aid, a in auctions.items() if a["isActive"]}
        return render_template("login_auction_list.html", auctions=active_auctions)

@app.route('/archive', methods=["GET"])
def archive():
    auction_id = request.args.get("auction_id")
    if auction_id:
        auction = auctions.get(auction_id)
        if not auction:
            return "Aukcja nie znaleziona", 404
        check_auction_status(auction)
        return render_template("archive.html", auction=auction)
    else:
        archived_auctions = {aid: a for aid, a in auctions.items() if not a["isActive"]}
        return render_template("archive.html", auctions=archived_auctions)

@app.route('/delete_auction/<auction_id>', methods=["DELETE"])
def delete_auction(auction_id):
    if auction_id in auctions:
        del auctions[auction_id]
        socketio.emit("auction_deleted", {"auction_id": auction_id})
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Aukcja nie znaleziona"}), 404

@app.route('/admin/<auction_id>', methods=["GET", "POST"])
def admin(auction_id):
    auction = auctions.get(auction_id)
    if not auction:
        return "Aukcja nie znaleziona", 404
    check_auction_status(auction)
    if request.method == "POST":
        auction["item"] = request.form["item"]
        auction["minIncrement"] = int(request.form["minIncrement"])
        auction["startingPrice"] = int(request.form["startingPrice"])
        auction["duration"] = int(request.form["duration"])
        start_time_str = request.form["startTime"]
        try:
            auction["startTime"] = int(datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M").timestamp())
        except ValueError:
            return "Nieprawidłowy format daty.", 400
    return render_template("admin.html", auction=auction)

@app.route('/reset_auction/<auction_id>', methods=["POST"])
def reset_auction(auction_id):
    auction = auctions.get(auction_id)
    if not auction:
        return jsonify({"error": "Aukcja nie znaleziona"}), 404
    auction["lowestBid"] = None
    auction["bids"] = []
    auction["startTime"] = None
    auction["isActive"] = True
    socketio.emit("auction_reset", {"auction_id": auction_id})
    return jsonify({"success": True})

@app.route('/end_auction/<auction_id>', methods=["POST"])
def end_auction_route(auction_id):
    auction = auctions.get(auction_id)
    if not auction:
        return jsonify({"error": "Aukcja nie znaleziona"}), 404
    auction["isActive"] = False
    socketio.emit("auction_ended", {"auction_id": auction_id})
    return jsonify({"success": True})

@app.route('/send_invitation/<auction_id>', methods=["POST"])
def send_invitation(auction_id):
    auction = auctions.get(auction_id)
    if not auction:
        return jsonify({"error": "Aukcja nie znaleziona"}), 404
    user_name = request.json.get("user_name")
    if not user_name:
        return jsonify({"error": "Brak imienia użytkownika."}), 400
    token = str(uuid.uuid4())
    auction["invited_users"][token] = user_name
    link = f"http://127.0.0.1:4000/auction/{auction_id}/{token}"
    return jsonify({"link": link})

@app.route('/api/bids/<auction_id>', methods=["POST"])
def submit_bid(auction_id):
    if auction_id not in auctions:
        return jsonify({"error": "Aukcja nie znaleziona"}), 404
    auction = auctions[auction_id]
    data = request.get_json()
    price = data.get("price")
    token = data.get("token")
    if price is None:
        return jsonify({"error": "Brak ceny oferty"}), 400
    if auction["lowestBid"] is not None:
        if price >= auction["lowestBid"]["price"]:
            return jsonify({"error": "Oferta musi być niższa od obecnej najniższej"}), 400
    else:
        if price >= auction["startingPrice"]:
            return jsonify({"error": "Oferta musi być niższa od ceny wywoławczej"}), 400
    bid = {"bidder": token, "price": price}
    auction["bids"].append(bid)
    auction["lowestBid"] = bid
    current_time = time.time()
    remaining = int(auction["startTime"] + auction["duration"] - current_time)
    if remaining < 0:
        remaining = 0
    socketio.emit("new_bid", {"auction_id": auction_id, "price": price, "newDuration": remaining})
    return jsonify({"success": True})

@app.route('/auction/<auction_id>/<token>')
def auction_view(auction_id, token):
    auction = auctions.get(auction_id)
    if not auction:
        return "Aukcja nie znaleziona", 404
    check_auction_status(auction)
    if token not in auction["invited_users"]:
        return "Nieprawidłowy token.", 403
    return render_template("user.html", auction=auction, user_name=auction["invited_users"][token], token=token)

@app.route('/auction-terms/<auction_id>/<token>')
def auction_terms(auction_id, token):
    auction = auctions.get(auction_id)
    if not auction:
        return "Aukcja nie znaleziona", 404
    if token not in auction["invited_users"]:
        return "Nieprawidłowy token.", 403
    return render_template("auction_terms.html", auction=auction, token=token)

@app.route('/terms')
def terms():
    return render_template("terms.html")

# --------------------- USTAWIENIA --------------------- #

@app.route('/settings', methods=["GET", "POST"])
def settings():
    if "username" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        if "banner_file" in request.files:
            file = request.files["banner_file"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + "_" + filename
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
                file.save(file_path)
                session["banner_image"] = url_for('static', filename="uploads/" + unique_filename)
                flash("Banner został zaktualizowany (plik).", "success")
            elif file:
                flash("Nieprawidłowy typ pliku. Dozwolone formaty: png, jpg, jpeg, gif.", "danger")
        banner_url = request.form.get("banner_url")
        if banner_url:
            session["banner_image"] = banner_url
            flash("Banner został zaktualizowany (URL).", "success")
        return redirect(url_for("settings"))
    default_banner = url_for('static', filename='images/banner.jpg')
    banner_image = session.get("banner_image", default_banner)
    return render_template("settings.html", banner_image=banner_image)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=4000)
