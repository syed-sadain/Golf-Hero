"""
GolfHero - Subscription Golf Platform with Charity & Draw Engine
Flask + PostgreSQL + Stripe
Author: Digital Heroes Trainee Build
"""

import os
import random
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from collections import Counter

import psycopg2
import psycopg2.extras
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# ─── App Config ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.jinja_env.filters['fromjson'] = json.loads

import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:Pass%40123@localhost:5432/golfhero"
)

STRIPE_PUBLIC_KEY  = os.environ.get("STRIPE_PUBLIC_KEY",  "pk_test_placeholder")
STRIPE_SECRET_KEY  = os.environ.get("STRIPE_SECRET_KEY",  "sk_test_placeholder")
MONTHLY_PRICE_ID   = os.environ.get("MONTHLY_PRICE_ID",   "price_monthly")
YEARLY_PRICE_ID    = os.environ.get("YEARLY_PRICE_ID",    "price_yearly")

MONTHLY_PRICE = 9.99
YEARLY_PRICE  = 89.99
MIN_CHARITY_PCT = 10   # Minimum 10% goes to charity

# ─── DB Helpers ────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def query(sql, args=(), one=False, commit=False):
    db   = get_db()
    cur  = db.cursor()
    cur.execute(sql, args)
    if commit:
        db.commit()
        return cur.rowcount
    rv = cur.fetchone() if one else cur.fetchall()
    return rv

def execute(sql, args=()):
    db  = get_db()
    cur = db.cursor()
    cur.execute(sql, args)
    db.commit()
    return cur

# ─── DB Init ───────────────────────────────────────────────────────────────────

def init_db():
    db  = get_db()
    cur = db.cursor()
    
    statements = """
    CREATE TABLE IF NOT EXISTS users (
        id              SERIAL PRIMARY KEY,
        name            VARCHAR(120) NOT NULL,
        email           VARCHAR(120) UNIQUE NOT NULL,
        password_hash   TEXT NOT NULL,
        role            VARCHAR(20) DEFAULT 'subscriber',
        subscription    VARCHAR(20) DEFAULT 'inactive',
        sub_plan        VARCHAR(20),
        sub_start       TIMESTAMP,
        sub_end         TIMESTAMP,
        stripe_customer TEXT,
        charity_id      INT,
        charity_pct     INT DEFAULT 10,
        created_at      TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS charities (
        id          SERIAL PRIMARY KEY,
        name        VARCHAR(200) NOT NULL,
        description TEXT,
        image_url   TEXT,
        website     TEXT,
        featured    BOOLEAN DEFAULT FALSE,
        active      BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS scores (
        id          SERIAL PRIMARY KEY,
        user_id     INT REFERENCES users(id) ON DELETE CASCADE,
        score       INT NOT NULL CHECK(score BETWEEN 1 AND 45),
        score_date  DATE NOT NULL,
        created_at  TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, score_date)
    );

    CREATE TABLE IF NOT EXISTS draws (
        id              SERIAL PRIMARY KEY,
        month           VARCHAR(20) NOT NULL,
        year            INT NOT NULL,
        draw_type       VARCHAR(20) DEFAULT 'random',
        drawn_numbers   TEXT,
        status          VARCHAR(20) DEFAULT 'pending',
        jackpot_rollover NUMERIC(10,2) DEFAULT 0,
        total_pool      NUMERIC(10,2) DEFAULT 0,
        published_at    TIMESTAMP,
        created_at      TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS draw_entries (
        id          SERIAL PRIMARY KEY,
        draw_id     INT REFERENCES draws(id),
        user_id     INT REFERENCES users(id),
        numbers     TEXT NOT NULL,
        match_count INT DEFAULT 0,
        prize_tier  VARCHAR(20),
        created_at  TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS winners (
        id              SERIAL PRIMARY KEY,
        draw_id         INT REFERENCES draws(id),
        user_id         INT REFERENCES users(id),
        match_type      VARCHAR(20),
        prize_amount    NUMERIC(10,2),
        proof_url       TEXT,
        status          VARCHAR(20) DEFAULT 'pending',
        admin_notes     TEXT,
        payout_date     TIMESTAMP,
        created_at      TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS charity_donations (
        id          SERIAL PRIMARY KEY,
        user_id     INT REFERENCES users(id),
        charity_id  INT REFERENCES charities(id),
        amount      NUMERIC(10,2),
        month       VARCHAR(20),
        year        INT,
        created_at  TIMESTAMP DEFAULT NOW()
    );
    """
    
    for stmt in statements.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    db.commit()

    # Seed admin user
    cur.execute("SELECT id FROM users WHERE email = 'admin@golfhero.com'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (name, email, password_hash, role, subscription)
            VALUES (%s,%s,%s,'admin','active')
        """, ("Admin", "admin@golfhero.com",
              generate_password_hash("Admin@123")))

    # Seed charities
    cur.execute("SELECT id FROM charities LIMIT 1")
    if not cur.fetchone():
        charities = [
            ("Golf4Good Foundation", "Supporting underprivileged youth through golf programmes.", True),
            ("Green Fairways Trust", "Environmental conservation on golf courses worldwide.", True),
            ("Swing & Smile", "Therapeutic golf for adults with disabilities.", False),
            ("Caddie for Cancer", "Raising funds for cancer research through golf tournaments.", False),
            ("Junior Golf Dreams", "Providing equipment and coaching to junior golfers.", False),
        ]
        for name, desc, featured in charities:
            cur.execute("""
                INSERT INTO charities (name, description, featured)
                VALUES (%s,%s,%s)
            """, (name, desc, featured))
    db.commit()
    print("✅  DB initialised")

# ─── Auth Helpers ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if "user_id" not in session:
        return None
    return query("SELECT * FROM users WHERE id = %s", (session["user_id"],), one=True)

# ─── Prize Pool Calculations ───────────────────────────────────────────────────

def calculate_prize_pool(sub_count, monthly_price=MONTHLY_PRICE, rollover=0):
    gross = sub_count * monthly_price
    charity_pool = gross * 0.10
    prize_gross  = gross - charity_pool + rollover
    return {
        "total_pool":   round(prize_gross, 2),
        "five_match":   round(prize_gross * 0.40, 2),
        "four_match":   round(prize_gross * 0.35, 2),
        "three_match":  round(prize_gross * 0.25, 2),
        "charity_pool": round(charity_pool, 2),
    }

def run_draw_algorithm(draw_type="random", month=None, year=None):
    """Generate 5 draw numbers (1-45)"""
    if draw_type == "algorithm":
        # Weighted by most frequent user scores
        rows = query("SELECT score FROM scores")
        if rows:
            all_scores = [r["score"] for r in rows]
            freq = Counter(all_scores)
            population = list(freq.keys())
            weights    = [freq[s] for s in population]
            # Pick 5 unique weighted numbers
            chosen = []
            pop_copy = population[:]
            wt_copy  = weights[:]
            while len(chosen) < 5 and pop_copy:
                pick = random.choices(pop_copy, weights=wt_copy, k=1)[0]
                if pick not in chosen:
                    chosen.append(pick)
                idx = pop_copy.index(pick)
                pop_copy.pop(idx)
                wt_copy.pop(idx)
            # If not enough unique, fill randomly
            while len(chosen) < 5:
                n = random.randint(1, 45)
                if n not in chosen:
                    chosen.append(n)
            return sorted(chosen)
    # Default: random
    return sorted(random.sample(range(1, 46), 5))

def check_user_matches(user_numbers, drawn_numbers):
    user_set  = set(user_numbers)
    drawn_set = set(drawn_numbers)
    matches   = len(user_set & drawn_set)
    return matches

# ─── PUBLIC ROUTES ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    charities = query("SELECT * FROM charities WHERE featured=TRUE AND active=TRUE LIMIT 3")
    # Latest published draw
    latest_draw = query("""
        SELECT * FROM draws WHERE status='published'
        ORDER BY published_at DESC LIMIT 1
    """, one=True)
    # Stats
    user_count   = query("SELECT COUNT(*) as c FROM users WHERE role='subscriber'", one=True)["c"]
    charity_total = query("SELECT COALESCE(SUM(amount),0) as t FROM charity_donations", one=True)["t"]
    return render_template("index.html",
        charities=charities,
        latest_draw=latest_draw,
        user_count=user_count,
        charity_total=charity_total,
        stripe_key=STRIPE_PUBLIC_KEY,
        monthly_price=MONTHLY_PRICE,
        yearly_price=YEARLY_PRICE,
    )

@app.route("/charities")
def charities():
    search = request.args.get("q", "")
    if search:
        rows = query(
            "SELECT * FROM charities WHERE active=TRUE AND name ILIKE %s ORDER BY featured DESC",
            (f"%{search}%",)
        )
    else:
        rows = query("SELECT * FROM charities WHERE active=TRUE ORDER BY featured DESC")
    return render_template("charities.html", charities=rows, search=search)

@app.route("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html")

# ─── AUTH ROUTES ───────────────────────────────────────────────────────────────

@app.route("/signup", methods=["GET", "POST"])
def signup():
    charities_list = query("SELECT id,name FROM charities WHERE active=TRUE ORDER BY name")
    if request.method == "POST":
        name         = request.form.get("name", "").strip()
        email        = request.form.get("email", "").strip().lower()
        password     = request.form.get("password", "")
        plan         = request.form.get("plan", "monthly")
        charity_id   = request.form.get("charity_id")
        charity_pct  = int(request.form.get("charity_pct", MIN_CHARITY_PCT))

        if charity_pct < MIN_CHARITY_PCT:
            charity_pct = MIN_CHARITY_PCT

        if not all([name, email, password]):
            flash("All fields are required.", "danger")
            return render_template("signup.html", charities=charities_list)

        existing = query("SELECT id FROM users WHERE email=%s", (email,), one=True)
        if existing:
            flash("An account with this email already exists.", "danger")
            return render_template("signup.html", charities=charities_list)

        pw_hash = generate_password_hash(password)
        sub_end = datetime.now() + timedelta(days=365 if plan=="yearly" else 30)

        execute("""
            INSERT INTO users (name,email,password_hash,subscription,sub_plan,sub_start,sub_end,charity_id,charity_pct)
            VALUES (%s,%s,%s,'active',%s,NOW(),%s,%s,%s)
        """, (name, email, pw_hash, plan, sub_end, charity_id or None, charity_pct))

        user = query("SELECT * FROM users WHERE email=%s", (email,), one=True)
        session["user_id"] = user["id"]
        session["role"]    = user["role"]
        session["name"]    = user["name"]
        flash(f"Welcome, {name}! Your account is active.", "success")
        return redirect(url_for("dashboard"))

    return render_template("signup.html", charities=charities_list,
                           monthly_price=MONTHLY_PRICE, yearly_price=YEARLY_PRICE)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user     = query("SELECT * FROM users WHERE email=%s", (email,), one=True)

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"]    = user["role"]
            session["name"]    = user["name"]
            flash(f"Welcome back, {user['name']}!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

# ─── SUBSCRIBER DASHBOARD ──────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    scores = query("""
        SELECT * FROM scores WHERE user_id=%s
        ORDER BY score_date DESC LIMIT 5
    """, (user["id"],))
    charity = None
    if user["charity_id"]:
        charity = query("SELECT * FROM charities WHERE id=%s", (user["charity_id"],), one=True)

    latest_draw = query("""
        SELECT * FROM draws WHERE status='published'
        ORDER BY published_at DESC LIMIT 1
    """, one=True)

    winnings = query("""
        SELECT w.*, d.month, d.year FROM winners w
        JOIN draws d ON d.id=w.draw_id
        WHERE w.user_id=%s ORDER BY w.created_at DESC
    """, (user["id"],))

    total_won = sum(float(w["prize_amount"] or 0) for w in winnings)

    upcoming_draw = query("""
        SELECT * FROM draws WHERE status='pending'
        ORDER BY created_at DESC LIMIT 1
    """, one=True)

    # Participation count
    participation = query(
        "SELECT COUNT(*) as c FROM draw_entries WHERE user_id=%s", (user["id"],), one=True
    )["c"]

    return render_template("dashboard.html",
        user=user, scores=scores, charity=charity,
        latest_draw=latest_draw, winnings=winnings,
        total_won=total_won, participation=participation,
        upcoming_draw=upcoming_draw,
        min_charity=MIN_CHARITY_PCT,
        now=datetime.now(),
    )

# ─── SCORE MANAGEMENT ──────────────────────────────────────────────────────────

@app.route("/scores/add", methods=["POST"])
@login_required
def add_score():
    user_id    = session["user_id"]
    score_val  = request.form.get("score", type=int)
    score_date = request.form.get("score_date")

    if not score_val or not score_date:
        flash("Score and date are required.", "danger")
        return redirect(url_for("dashboard"))

    if score_val < 1 or score_val > 45:
        flash("Score must be between 1 and 45 (Stableford).", "danger")
        return redirect(url_for("dashboard"))

    # Check duplicate date
    existing = query(
        "SELECT id FROM scores WHERE user_id=%s AND score_date=%s",
        (user_id, score_date), one=True
    )
    if existing:
        flash("A score for this date already exists. Edit or delete it.", "warning")
        return redirect(url_for("dashboard"))

    # Rolling 5-score logic: if already 5 scores, remove oldest
    count = query("SELECT COUNT(*) as c FROM scores WHERE user_id=%s", (user_id,), one=True)["c"]
    if count >= 5:
        oldest = query("""
            SELECT id FROM scores WHERE user_id=%s
            ORDER BY score_date ASC LIMIT 1
        """, (user_id,), one=True)
        execute("DELETE FROM scores WHERE id=%s", (oldest["id"],))

    execute("""
        INSERT INTO scores (user_id, score, score_date)
        VALUES (%s,%s,%s)
    """, (user_id, score_val, score_date))
    flash("Score added successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/scores/edit/<int:score_id>", methods=["POST"])
@login_required
def edit_score(score_id):
    user_id   = session["user_id"]
    score_val = request.form.get("score", type=int)

    if not score_val or score_val < 1 or score_val > 45:
        flash("Invalid score value.", "danger")
        return redirect(url_for("dashboard"))

    execute("""
        UPDATE scores SET score=%s WHERE id=%s AND user_id=%s
    """, (score_val, score_id, user_id))
    flash("Score updated.", "success")
    return redirect(url_for("dashboard"))

@app.route("/scores/delete/<int:score_id>", methods=["POST"])
@login_required
def delete_score(score_id):
    execute("DELETE FROM scores WHERE id=%s AND user_id=%s", (score_id, session["user_id"]))
    flash("Score removed.", "info")
    return redirect(url_for("dashboard"))

# ─── PROFILE / CHARITY SETTINGS ────────────────────────────────────────────────

@app.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    uid         = session["user_id"]
    charity_id  = request.form.get("charity_id")
    charity_pct = int(request.form.get("charity_pct", MIN_CHARITY_PCT))
    if charity_pct < MIN_CHARITY_PCT:
        charity_pct = MIN_CHARITY_PCT

    execute("""
        UPDATE users SET charity_id=%s, charity_pct=%s WHERE id=%s
    """, (charity_id or None, charity_pct, uid))
    flash("Profile updated successfully!", "success")
    return redirect(url_for("dashboard"))

# ─── WINNER PROOF UPLOAD ───────────────────────────────────────────────────────

@app.route("/winner/upload-proof/<int:winner_id>", methods=["POST"])
@login_required
def upload_proof(winner_id):
    uid      = session["user_id"]
    proof    = request.form.get("proof_url", "").strip()
    winner   = query("SELECT * FROM winners WHERE id=%s AND user_id=%s", (winner_id, uid), one=True)
    if not winner:
        flash("Record not found.", "danger")
        return redirect(url_for("dashboard"))

    execute("UPDATE winners SET proof_url=%s, status='proof_submitted' WHERE id=%s",
            (proof, winner_id))
    flash("Proof submitted! Admin will review shortly.", "success")
    return redirect(url_for("dashboard"))

# ─── ADMIN — DASHBOARD ─────────────────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "users":         query("SELECT COUNT(*) as c FROM users WHERE role='subscriber'", one=True)["c"],
        "active_subs":   query("SELECT COUNT(*) as c FROM users WHERE subscription='active'", one=True)["c"],
        "charities":     query("SELECT COUNT(*) as c FROM charities", one=True)["c"],
        "draws":         query("SELECT COUNT(*) as c FROM draws WHERE status='published'", one=True)["c"],
        "pending_winners": query("SELECT COUNT(*) as c FROM winners WHERE status='pending'", one=True)["c"],
        "charity_total": query("SELECT COALESCE(SUM(amount),0) as t FROM charity_donations", one=True)["t"],
        "prize_paid":    query("SELECT COALESCE(SUM(prize_amount),0) as t FROM winners WHERE status='paid'", one=True)["t"],
    }
    recent_users  = query("SELECT * FROM users ORDER BY created_at DESC LIMIT 5")
    pending_winners = query("""
        SELECT w.*, u.name as uname, d.month, d.year
        FROM winners w
        JOIN users u ON u.id=w.user_id
        JOIN draws d ON d.id=w.draw_id
        WHERE w.status IN ('pending','proof_submitted')
        ORDER BY w.created_at DESC LIMIT 10
    """)
    pool = calculate_prize_pool(stats["active_subs"])
    return render_template("admin/dashboard.html",
        stats=stats, recent_users=recent_users,
        pending_winners=pending_winners, pool=pool)

# ─── ADMIN — USERS ─────────────────────────────────────────────────────────────

@app.route("/admin/users")
@admin_required
def admin_users():
    users = query("""
        SELECT u.*, c.name as charity_name
        FROM users u LEFT JOIN charities c ON c.id=u.charity_id
        ORDER BY u.created_at DESC
    """)
    return render_template("admin/users.html", users=users)

@app.route("/admin/users/<int:user_id>")
@admin_required
def admin_user_detail(user_id):
    user    = query("SELECT * FROM users WHERE id=%s", (user_id,), one=True)
    scores  = query("SELECT * FROM scores WHERE user_id=%s ORDER BY score_date DESC", (user_id,))
    winnings = query("SELECT * FROM winners WHERE user_id=%s", (user_id,))
    charities_list = query("SELECT id,name FROM charities WHERE active=TRUE")
    return render_template("admin/user_detail.html",
        user=user, scores=scores, winnings=winnings, charities=charities_list)

@app.route("/admin/users/<int:user_id>/update", methods=["POST"])
@admin_required
def admin_update_user(user_id):
    subscription = request.form.get("subscription")
    execute("UPDATE users SET subscription=%s WHERE id=%s", (subscription, user_id))
    flash("User updated.", "success")
    return redirect(url_for("admin_user_detail", user_id=user_id))

@app.route("/admin/users/<int:user_id>/score/edit", methods=["POST"])
@admin_required
def admin_edit_score(user_id):
    score_id  = request.form.get("score_id", type=int)
    score_val = request.form.get("score", type=int)
    execute("UPDATE scores SET score=%s WHERE id=%s AND user_id=%s",
            (score_val, score_id, user_id))
    flash("Score updated by admin.", "success")
    return redirect(url_for("admin_user_detail", user_id=user_id))

# ─── ADMIN — DRAWS ─────────────────────────────────────────────────────────────

@app.route("/admin/draws")
@admin_required
def admin_draws():
    draws = query("SELECT * FROM draws ORDER BY created_at DESC")
    now   = datetime.now()
    return render_template("admin/draws.html", draws=draws, now=now)

@app.route("/admin/draws/create", methods=["POST"])
@admin_required
def admin_create_draw():
    month     = request.form.get("month")
    year      = request.form.get("year", type=int)
    draw_type = request.form.get("draw_type", "random")
    execute("""
        INSERT INTO draws (month, year, draw_type)
        VALUES (%s,%s,%s)
    """, (month, year, draw_type))
    flash("Draw created.", "success")
    return redirect(url_for("admin_draws"))

@app.route("/admin/draws/<int:draw_id>/simulate", methods=["POST"])
@admin_required
def admin_simulate_draw(draw_id):
    draw   = query("SELECT * FROM draws WHERE id=%s", (draw_id,), one=True)
    nums   = run_draw_algorithm(draw["draw_type"], draw["month"], draw["year"])
    execute("UPDATE draws SET drawn_numbers=%s WHERE id=%s",
            (json.dumps(nums), draw_id))
    flash(f"Simulation complete. Numbers: {nums}", "info")
    return redirect(url_for("admin_draws"))

@app.route("/admin/draws/<int:draw_id>/publish", methods=["POST"])
@admin_required
def admin_publish_draw(draw_id):
    draw   = query("SELECT * FROM draws WHERE id=%s", (draw_id,), one=True)
    if not draw["drawn_numbers"]:
        nums = run_draw_algorithm(draw["draw_type"])
        execute("UPDATE draws SET drawn_numbers=%s WHERE id=%s",
                (json.dumps(nums), draw_id))
    else:
        nums = json.loads(draw["drawn_numbers"])

    # Calculate prize pool
    active_count = query("SELECT COUNT(*) as c FROM users WHERE subscription='active'", one=True)["c"]
    # Check jackpot rollover
    prev_jackpot = query("""
        SELECT jackpot_rollover FROM draws WHERE status='published'
        ORDER BY published_at DESC LIMIT 1
    """, one=True)
    rollover = float(prev_jackpot["jackpot_rollover"]) if prev_jackpot else 0
    pool = calculate_prize_pool(active_count, rollover=rollover)

    execute("""
        UPDATE draws SET status='published', published_at=NOW(),
        total_pool=%s WHERE id=%s
    """, (pool["total_pool"], draw_id))

    # Score each subscriber who has 5 scores
    subscribers = query("""
        SELECT u.id, array_agg(s.score) as scores
        FROM users u
        JOIN scores s ON s.user_id=u.id
        WHERE u.subscription='active'
        GROUP BY u.id
        HAVING COUNT(s.id)=5
    """)

    jackpot_claimed = False
    for sub in subscribers:
        user_nums   = sub["scores"]
        match_count = check_user_matches(user_nums, nums)
        if match_count >= 3:
            prize_tier = {5: "5-match", 4: "4-match", 3: "3-match"}.get(match_count)
            prize_pool_val = {
                "5-match": pool["five_match"],
                "4-match": pool["four_match"],
                "3-match": pool["three_match"],
            }.get(prize_tier, 0)

            execute("""
                INSERT INTO draw_entries (draw_id, user_id, numbers, match_count, prize_tier)
                VALUES (%s,%s,%s,%s,%s)
            """, (draw_id, sub["id"], json.dumps(user_nums), match_count, prize_tier))

            # Count winners in same tier for prize splitting
            execute("""
                INSERT INTO winners (draw_id, user_id, match_type, prize_amount)
                VALUES (%s,%s,%s,%s)
            """, (draw_id, sub["id"], prize_tier, prize_pool_val))

            if match_count == 5:
                jackpot_claimed = True

    # Rollover jackpot if not claimed
    if not jackpot_claimed:
        execute("UPDATE draws SET jackpot_rollover=%s WHERE id=%s",
                (pool["five_match"] + rollover, draw_id))

    flash(f"Draw published! Numbers: {nums}", "success")
    return redirect(url_for("admin_draws"))

# ─── ADMIN — CHARITIES ─────────────────────────────────────────────────────────

@app.route("/admin/charities")
@admin_required
def admin_charities():
    charities = query("SELECT * FROM charities ORDER BY created_at DESC")
    return render_template("admin/charities.html", charities=charities)

@app.route("/admin/charities/add", methods=["POST"])
@admin_required
def admin_add_charity():
    name     = request.form.get("name", "").strip()
    desc     = request.form.get("description", "").strip()
    website  = request.form.get("website", "").strip()
    featured = True if request.form.get("featured") else False    
    if not name:
        flash("Charity name required.", "danger")
        return redirect(url_for("admin_charities"))
    execute("""
        INSERT INTO charities (name, description, website, featured)
        VALUES (%s,%s,%s,%s)
    """, (name, desc, website, featured))
    flash("Charity added.", "success")
    return redirect(url_for("admin_charities"))

@app.route("/admin/charities/<int:cid>/toggle", methods=["POST"])
@admin_required
def admin_toggle_charity(cid):
    execute("UPDATE charities SET active = NOT active WHERE id=%s", (cid,))
    flash("Charity status updated.", "success")
    return redirect(url_for("admin_charities"))

@app.route("/admin/charities/<int:cid>/delete", methods=["POST"])
@admin_required
def admin_delete_charity(cid):
    execute("DELETE FROM charities WHERE id=%s", (cid,))
    flash("Charity removed.", "success")
    return redirect(url_for("admin_charities"))

# ─── ADMIN — WINNERS ───────────────────────────────────────────────────────────

@app.route("/admin/winners")
@admin_required
def admin_winners():
    winners = query("""
        SELECT w.*, u.name as uname, u.email as uemail,
               d.month, d.year, d.drawn_numbers
        FROM winners w
        JOIN users u ON u.id=w.user_id
        JOIN draws d ON d.id=w.draw_id
        ORDER BY w.created_at DESC
    """)
    return render_template("admin/winners.html", winners=winners)

@app.route("/admin/winners/<int:wid>/approve", methods=["POST"])
@admin_required
def admin_approve_winner(wid):
    notes = request.form.get("notes", "")
    execute("""
        UPDATE winners SET status='paid', payout_date=NOW(), admin_notes=%s
        WHERE id=%s
    """, (notes, wid))
    flash("Winner approved & marked as paid.", "success")
    return redirect(url_for("admin_winners"))

@app.route("/admin/winners/<int:wid>/reject", methods=["POST"])
@admin_required
def admin_reject_winner(wid):
    notes = request.form.get("notes", "")
    execute("UPDATE winners SET status='rejected', admin_notes=%s WHERE id=%s", (notes, wid))
    flash("Winner rejected.", "warning")
    return redirect(url_for("admin_winners"))

# ─── ADMIN — REPORTS ───────────────────────────────────────────────────────────

@app.route("/admin/reports")
@admin_required
def admin_reports():
    user_count     = query("SELECT COUNT(*) as c FROM users WHERE role='subscriber'", one=True)["c"]
    active_subs    = query("SELECT COUNT(*) as c FROM users WHERE subscription='active'", one=True)["c"]
    total_draws    = query("SELECT COUNT(*) as c FROM draws WHERE status='published'", one=True)["c"]
    prize_paid     = query("SELECT COALESCE(SUM(prize_amount),0) as t FROM winners WHERE status='paid'", one=True)["t"]
    charity_total  = query("SELECT COALESCE(SUM(amount),0) as t FROM charity_donations", one=True)["t"]
    charity_breakdown = query("""
        SELECT c.name, COALESCE(SUM(d.amount),0) as total
        FROM charities c
        LEFT JOIN charity_donations d ON d.charity_id=c.id
        GROUP BY c.name ORDER BY total DESC
    """)
    monthly_scores = query("""
        SELECT DATE_TRUNC('month', score_date) as month, COUNT(*) as count, AVG(score) as avg_score
        FROM scores GROUP BY 1 ORDER BY 1 DESC LIMIT 12
    """)
    pool = calculate_prize_pool(active_subs)
    return render_template("admin/reports.html",
        user_count=user_count, active_subs=active_subs,
        total_draws=total_draws, prize_paid=prize_paid,
        charity_total=charity_total, charity_breakdown=charity_breakdown,
        monthly_scores=monthly_scores, pool=pool)

# ─── API — MISC ────────────────────────────────────────────────────────────────

@app.route("/api/draw-numbers")
@admin_required
def api_draw_numbers():
    draw_type = request.args.get("type", "random")
    nums = run_draw_algorithm(draw_type)
    return jsonify({"numbers": nums})

# ─── CLI ───────────────────────────────────────────────────────────────────────

@app.cli.command("init-db")
def cli_init_db():
    with app.app_context():
        init_db()

# ─── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        try:
            init_db()
        except Exception as e:
            print(f"DB init warning: {e}")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
