import os, secrets, uuid, functools, hashlib, time, click, requests, certifi, mysql.connector
from urllib.parse import urlencode
from flask import Flask, request, jsonify, session, send_from_directory, redirect, g
from werkzeug.utils import secure_filename

def _load_env():
    """Tiny .env loader (KEY=value per line) so no extra package is needed."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_load_env()

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE, "public"), static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config.update(MAX_CONTENT_LENGTH=4*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
UP = os.path.join(os.path.dirname(__file__), "uploads")
try: os.makedirs(UP, exist_ok=True)
except OSError: pass   # read-only filesystem (Vercel) - images go to Cloudinary instead

CATS = ["Sedan", "SUV", "Bike", "Sports", "Supercar", "Luxury", "Other"]   # model types
STATUSES = ["Pending", "Approved", "Rejected", "Completed"]
EXT = {"png", "jpg", "jpeg", "webp", "gif"}

# ---- Discord OAuth2 settings (create an app at https://discord.com/developers/applications) ----
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:5000/auth/discord/callback")
# Discord user IDs that are always admins (comma separated). More admins: `flask make-admin <discord_id>`
ADMIN_IDS = {i.strip() for i in os.environ.get("ADMIN_DISCORD_IDS", "").split(",") if i.strip()}
DISCORD_API = "https://discord.com/api"


def db():
    cfg = dict(host=os.environ.get("DB_HOST", "localhost"), port=int(os.environ.get("DB_PORT", "3306")),
               user=os.environ.get("DB_USER", "root"), password=os.environ.get("DB_PASS", ""),
               database=os.environ.get("DB_NAME", "showroom"), connection_timeout=10)
    if os.environ.get("DB_SSL", "0") == "1":      # required by TiDB Cloud / Aiven / most online MySQL hosts
        cfg.update(ssl_disabled=False, ssl_ca=certifi.where(), ssl_verify_cert=os.environ.get("DB_SSL_VERIFY", "1") != "0")
    return mysql.connector.connect(**cfg)

def q(sql, args=(), one=False, write=False):
    c = db(); cur = c.cursor(dictionary=True)
    try:
        cur.execute(sql, args)
        if write: c.commit(); return cur.lastrowid or cur.rowcount
        rows = cur.fetchall(); return (rows[0] if rows else None) if one else rows
    finally: cur.close(); c.close()


# ---------- auth helpers ----------
def current_user():
    """Logged-in user row (re-read from the DB each request so admin changes apply immediately)."""
    if "user" not in g:
        g.user = q("SELECT * FROM users WHERE id=%s", (session["uid"],), one=True) if session.get("uid") else None
    return g.user

def login_required(f):
    @functools.wraps(f)
    def w(*a, **k):
        if not current_user(): return jsonify(error="Please log in with Discord."), 401
        return f(*a, **k)
    return w

def admin_only(f):
    @functools.wraps(f)
    def w(*a, **k):
        u = current_user()
        if not u: return jsonify(error="Please log in with Discord."), 401
        if not u["is_admin"]: return jsonify(error="Admin access required."), 403
        return f(*a, **k)
    return w

def avatar_url(u):
    if u.get("avatar"): return f"https://cdn.discordapp.com/avatars/{u['discord_id']}/{u['avatar']}.png?size=64"
    return f"https://cdn.discordapp.com/embed/avatars/{(int(u['discord_id']) >> 22) % 6}.png"

def public_user(u):
    return dict(id=u["id"], discord_id=u["discord_id"], username=u["username"], name=u["display_name"] or u["username"],
                avatar=avatar_url(u), is_admin=bool(u["is_admin"]))


# ---------- Discord login ----------
@app.get("/auth/discord")
def discord_login():
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET):
        return redirect("/?" + urlencode(dict(auth_error="Discord login is not configured on the server yet.")))
    session["oauth_state"] = state = secrets.token_urlsafe(24)
    return redirect(f"{DISCORD_API}/oauth2/authorize?" + urlencode(dict(client_id=DISCORD_CLIENT_ID, response_type="code",
        redirect_uri=DISCORD_REDIRECT_URI, scope="identify", state=state, prompt="none")))

@app.get("/auth/discord/callback")
def discord_callback():
    fail = lambda m: redirect("/?" + urlencode(dict(auth_error=m)))
    if request.args.get("error"): return fail("Discord login was cancelled.")
    if not request.args.get("state") or request.args["state"] != session.pop("oauth_state", None): return fail("Login session expired. Please try again.")
    try:
        t = requests.post(f"{DISCORD_API}/oauth2/token", timeout=10, data=dict(client_id=DISCORD_CLIENT_ID,
            client_secret=DISCORD_CLIENT_SECRET, grant_type="authorization_code", code=request.args.get("code", ""),
            redirect_uri=DISCORD_REDIRECT_URI), headers={"Content-Type": "application/x-www-form-urlencoded"})
        t.raise_for_status()
        me = requests.get(f"{DISCORD_API}/users/@me", timeout=10, headers={"Authorization": "Bearer " + t.json()["access_token"]})
        me.raise_for_status(); du = me.json()
    except (requests.RequestException, KeyError, ValueError):
        return fail("Could not verify your Discord account. Please try again.")

    did = str(du["id"])
    q("""INSERT INTO users(discord_id,username,display_name,avatar,is_admin,last_login) VALUES(%s,%s,%s,%s,%s,NOW())
         ON DUPLICATE KEY UPDATE username=VALUES(username), display_name=VALUES(display_name), avatar=VALUES(avatar), last_login=NOW(),
         is_admin=IF(%s=1,1,is_admin)""",
      (did, du.get("username", "")[:80], (du.get("global_name") or "")[:80], du.get("avatar"), 1 if did in ADMIN_IDS else 0, 1 if did in ADMIN_IDS else 0), write=True)
    u = q("SELECT * FROM users WHERE discord_id=%s", (did,), one=True)
    q("INSERT INTO login_log(user_id,ip,user_agent) VALUES(%s,%s,%s)", (u["id"], request.remote_addr, request.headers.get("User-Agent", "")[:255]), write=True)
    session.clear(); session["uid"] = u["id"]
    return redirect("/")

@app.get("/api/me")
def me():
    u = current_user()
    return jsonify(user=public_user(u) if u else None, discord_configured=bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET))

@app.post("/api/auth/logout")
def logout(): session.clear(); return jsonify(ok=True)


# ---------- vehicle validation ----------
def clean_vehicle(d):
    """Admin input: name, model type, plate, upgrade, old owner (seller), dealer, purchase amount, listing price."""
    try:
        v = dict(
            name=str(d["name"]).strip()[:80],
            category=d["category"],
            plate_no=str(d["plate_no"]).strip().upper()[:20],
            upgrade=1 if str(d.get("upgrade", "0")) in ("1", "true", "True") else 0,
            seller=str(d["seller"]).strip()[:80],
            dealer=str(d["dealer"]).strip()[:80],
            purchase_price=int(d["purchase_price"]),
            price=int(d["price"]),
            description=str(d.get("description", "")).strip()[:2000],
            featured=1 if str(d.get("featured", "0")) in ("1", "true", "True") else 0)
    except (KeyError, ValueError, TypeError):
        return None, "Please fill in every required vehicle detail with valid values."
    if not all([v["name"], v["plate_no"], v["seller"], v["dealer"]]): return None, "Name, plate, seller (old owner) and dealer are required."
    if v["category"] not in CATS: return None, "Invalid model type."
    if v["purchase_price"] < 0 or v["price"] < 0: return None, "Amounts cannot be negative."
    return v, None

def cloudinary_upload(f, ext):
    """Signed upload to Cloudinary using CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME. Returns the https URL."""
    from urllib.parse import urlparse
    u = urlparse(os.environ["CLOUDINARY_URL"])
    key, secret, cloud = u.username, u.password, u.hostname
    params = dict(folder="topx-showroom", timestamp=str(int(time.time())))
    sig = hashlib.sha1(("&".join(f"{k}={params[k]}" for k in sorted(params)) + secret).encode()).hexdigest()
    r = requests.post(f"https://api.cloudinary.com/v1_1/{cloud}/image/upload", timeout=30,
                      data=dict(params, api_key=key, signature=sig), files={"file": (uuid.uuid4().hex + "." + ext, f.stream, f.mimetype)})
    if r.status_code != 200: raise ValueError("Image upload failed: " + r.text[:150])
    return r.json()["secure_url"].replace("/upload/", "/upload/w_1400,q_auto,f_auto/", 1)

def save_image(vals):
    f = request.files.get("image")
    if not f or not f.filename: return
    ext = secure_filename(f.filename).rsplit(".", 1)[-1].lower()
    if ext not in EXT: raise ValueError("Image must be png, jpg, webp or gif.")
    if os.environ.get("CLOUDINARY_URL"):
        vals["image"] = cloudinary_upload(f, ext)          # full https URL (online hosting)
    else:
        name = uuid.uuid4().hex + "." + ext                # local disk (running on your own PC)
        f.save(os.path.join(UP, name)); vals["image"] = name

@app.route("/")
def index(): return send_from_directory(os.path.join(BASE, "public"), "index.html")
@app.route("/admin")
def admin_page(): return redirect("/#/admin")

@app.route("/uploads/<path:n>")
@login_required
def uploads(n): return send_from_directory(UP, n)


# ---------- catalog (logged-in users) ----------
@app.get("/api/vehicles")
@login_required
def vehicles():
    # Catalog shows: name, model type, plate, upgrade, seller (old owner). Dealer + purchase price stay private.
    return jsonify(q("SELECT id,name,category,plate_no,upgrade,seller,price,description,image,status,available,featured,created_at "
                     "FROM vehicles ORDER BY (status='Sold'), featured DESC, created_at DESC"))

@app.post("/api/bookings")
@login_required
def book():
    u = current_user()
    d = request.get_json(silent=True) or {}
    name, pid, msg = (str(d.get(k, "")).strip() for k in ("player_name", "player_id", "message"))
    if not (2 <= len(name) <= 60 and pid.isdigit() and len(pid) <= 10):
        return jsonify(error="Enter a name and a numeric in-game ID."), 400
    veh = q("SELECT id,available FROM vehicles WHERE id=%s", (d.get("vehicle_id"),), one=True)
    if not veh: return jsonify(error="Vehicle not found."), 404
    if not veh["available"]: return jsonify(error="This vehicle is not open for booking."), 400
    if q("SELECT id FROM bookings WHERE player_id=%s AND vehicle_id=%s AND status IN ('Pending','Approved')", (pid, veh["id"]), one=True):
        return jsonify(error="You already have an active booking for this vehicle."), 409
    ref = "BK-" + secrets.token_hex(3).upper()
    q("INSERT INTO bookings(ref,vehicle_id,user_id,discord_id,player_name,player_id,discord,message) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
      (ref, veh["id"], u["id"], u["discord_id"], name, pid, u["username"], msg[:500]), write=True)
    return jsonify(ref=ref), 201

@app.get("/api/bookings/<ref>")
@login_required
def status(ref):
    u = current_user()
    r = q("SELECT b.ref,b.status,b.created_at,b.player_name,b.user_id,v.name vehicle FROM bookings b JOIN vehicles v ON v.id=b.vehicle_id WHERE b.ref=%s", (ref.upper().strip(),), one=True)
    if not r or (r["user_id"] not in (None, u["id"]) and not u["is_admin"]): return jsonify(error="No booking with that reference."), 404
    r.pop("user_id"); return jsonify(r)


# ---------- admin: vehicles (CRUD) ----------
@app.get("/api/admin/vehicles")
@admin_only
def admin_vehicles(): return jsonify(q("SELECT * FROM vehicles ORDER BY (status='Sold'), created_at DESC"))

@app.post("/api/admin/vehicles")
@app.put("/api/admin/vehicles/<int:vid>")
@admin_only
def save_vehicle(vid=None):
    v, err = clean_vehicle(request.form)
    if err: return jsonify(error=err), 400
    if q("SELECT id FROM vehicles WHERE plate_no=%s AND status='Available' AND id<>%s", (v["plate_no"], vid or 0), one=True):
        return jsonify(error="A vehicle with this plate number is already in stock."), 409
    try: save_image(v)
    except ValueError as e: return jsonify(error=str(e)), 400
    cols = list(v)
    if vid:
        q(f"UPDATE vehicles SET {','.join(c+'=%s' for c in cols)} WHERE id=%s", (*v.values(), vid), write=True)
    else:
        vid = q(f"INSERT INTO vehicles({','.join(cols)}) VALUES({','.join(['%s']*len(cols))})", tuple(v.values()), write=True)
    return jsonify(id=vid)

@app.delete("/api/admin/vehicles/<int:vid>")
@admin_only
def del_vehicle(vid): q("DELETE FROM vehicles WHERE id=%s", (vid,), write=True); return jsonify(ok=True)

@app.post("/api/admin/vehicles/<int:vid>/sell")
@admin_only
def sell_vehicle(vid):
    """Mark a vehicle Sold and write the full sales-log row in ONE transaction."""
    d = request.get_json(silent=True) or {}
    try:
        customer = str(d["customer"]).strip()[:80]
        sell_dealer = str(d["sell_dealer"]).strip()[:80]
        amount = int(d["sold_amount"])
        note = str(d.get("note", "")).strip()[:500]
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Enter customer name, selling dealer and sold amount."), 400
    if not customer or not sell_dealer: return jsonify(error="Customer name and selling dealer are required."), 400
    if amount < 0: return jsonify(error="Sold amount cannot be negative."), 400
    c = db(); cur = c.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM vehicles WHERE id=%s FOR UPDATE", (vid,)); v = cur.fetchone()
        if not v: return jsonify(error="Vehicle not found."), 404
        if v["status"] == "Sold": return jsonify(error="This vehicle is already marked as sold."), 409
        cur.execute("""INSERT INTO sales_log(vehicle_id,vehicle_name,model_type,plate_no,upgrade,seller,buy_dealer,purchase_price,
                       customer,sell_dealer,sold_amount,note,logged_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (vid, v["name"], v["category"], v["plate_no"], v["upgrade"], v["seller"], v["dealer"], v["purchase_price"],
             customer, sell_dealer, amount, note, current_user()["username"]))
        cur.execute("UPDATE vehicles SET status='Sold', available=0, featured=0 WHERE id=%s", (vid,))
        c.commit()
        return jsonify(ok=True, sale_id=cur.lastrowid)
    except Exception:
        c.rollback(); raise
    finally: cur.close(); c.close()

@app.post("/api/admin/vehicles/<int:vid>/relist")
@admin_only
def relist_vehicle(vid):
    """Put a sold vehicle back in stock (e.g. the sale fell through). The sales-log entry is kept; delete it separately."""
    q("UPDATE vehicles SET status='Available', available=1 WHERE id=%s", (vid,), write=True); return jsonify(ok=True)


# ---------- admin: bookings ----------
@app.get("/api/admin/bookings")
@admin_only
def bookings():
    return jsonify(q("SELECT b.*, v.name vehicle FROM bookings b JOIN vehicles v ON v.id=b.vehicle_id ORDER BY b.created_at DESC"))

@app.patch("/api/admin/bookings/<int:bid>")
@admin_only
def set_status(bid):
    s = (request.get_json(silent=True) or {}).get("status")
    if s not in STATUSES: return jsonify(error="Invalid status."), 400
    q("UPDATE bookings SET status=%s WHERE id=%s", (s, bid), write=True); return jsonify(ok=True)

@app.delete("/api/admin/bookings/<int:bid>")
@admin_only
def del_booking(bid): q("DELETE FROM bookings WHERE id=%s", (bid,), write=True); return jsonify(ok=True)


# ---------- admin: sales log ----------
@app.get("/api/admin/sales")
@admin_only
def sales(): return jsonify(q("SELECT * FROM sales_log ORDER BY created_at DESC"))

@app.put("/api/admin/sales/<int:sid>")
@admin_only
def edit_sale(sid):
    d = request.get_json(silent=True) or {}
    try:
        customer = str(d["customer"]).strip()[:80]; sell_dealer = str(d["sell_dealer"]).strip()[:80]
        amount = int(d["sold_amount"]); note = str(d.get("note", "")).strip()[:500]
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Please enter valid sale details."), 400
    if not customer or not sell_dealer or amount < 0: return jsonify(error="Customer, selling dealer and a valid amount are required."), 400
    q("UPDATE sales_log SET customer=%s, sell_dealer=%s, sold_amount=%s, note=%s WHERE id=%s", (customer, sell_dealer, amount, note, sid), write=True)
    return jsonify(ok=True)

@app.delete("/api/admin/sales/<int:sid>")
@admin_only
def del_sale(sid): q("DELETE FROM sales_log WHERE id=%s", (sid,), write=True); return jsonify(ok=True)

@app.get("/api/admin/stats")
@admin_only
def stats():
    c = lambda s: q(s, one=True)["n"]
    return jsonify(vehicles=c("SELECT COUNT(*) n FROM vehicles"), in_stock=c("SELECT COUNT(*) n FROM vehicles WHERE status='Available'"),
        sold=c("SELECT COUNT(*) n FROM vehicles WHERE status='Sold'"), users=c("SELECT COUNT(*) n FROM users"),
        bookings=c("SELECT COUNT(*) n FROM bookings"), pending=c("SELECT COUNT(*) n FROM bookings WHERE status='Pending'"),
        popular=q("SELECT v.name, COUNT(*) n FROM bookings b JOIN vehicles v ON v.id=b.vehicle_id GROUP BY v.id ORDER BY n DESC LIMIT 5"),
        recent=q("SELECT b.ref,b.player_name,b.status,b.created_at,v.name vehicle FROM bookings b JOIN vehicles v ON v.id=b.vehicle_id ORDER BY b.created_at DESC LIMIT 6"))

@app.get("/api/admin/users")
@admin_only
def users(): return jsonify(q("SELECT id,discord_id,username,display_name,is_admin,created_at,last_login FROM users ORDER BY last_login DESC"))

@app.cli.command("make-admin")
@click.argument("discord_id")
def make_admin(discord_id):
    """flask make-admin <discord_id>   (Discord: Settings > Advanced > Developer Mode, then right-click yourself > Copy User ID)"""
    q("INSERT INTO users(discord_id,username,is_admin) VALUES(%s,'(pending first login)',1) ON DUPLICATE KEY UPDATE is_admin=1", (discord_id.strip(),), write=True)
    click.echo("Admin saved. They will get admin access when they log in with Discord.")

if __name__ == "__main__": app.run(debug=False, port=5000)
