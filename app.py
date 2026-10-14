import re
import sqlite3
from datetime import datetime, timezone

from flask import Flask, flash, g, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = "change-this-later"  # needed for flash messages

DATABASE = "hostel.db"
REQUEST_TYPES = ["Cleaning", "Plumbing", "Electrical", "Wi-Fi", "Furniture", "Other"]
STATUSES = ["Pending", "In progress", "Done"]
ROOM_PATTERN = re.compile(r"^[A-Z]-\d{3}$")  # example: A-204


# ---------- Database helpers ----------

def get_db():
    """Open one database connection per request and reuse it."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # lets us use row["room"]
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the requests table the first time the app runs."""
    db = sqlite3.connect(DATABASE)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            room        TEXT NOT NULL,
            type        TEXT NOT NULL,
            description TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'Pending',
            created_at  TEXT NOT NULL
        )
        """
    )
    db.commit()
    db.close()


init_db()


# ---------- Template helper ----------

@app.template_filter("time_ago")
def time_ago(value):
    """Turn a saved timestamp into text like '2 hours ago'."""
    created = datetime.fromisoformat(value)
    seconds = int((datetime.now(timezone.utc) - created).total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


# ---------- Pages ----------

@app.route("/", methods=["GET", "POST"])
def report():
    if request.method == "POST":
        room = request.form.get("room", "").strip().upper()
        description = request.form.get("description", "").strip()
        is_emergency = request.form.get("emergency") == "1"
        request_type = "Emergency" if is_emergency else request.form.get("type", "")

        # Validation, with messages a student can understand
        if not ROOM_PATTERN.match(room):
            flash("Room number must look like A-204.", "error")
        elif not is_emergency and request_type not in REQUEST_TYPES:
            flash("Please choose a request type.", "error")
        elif not is_emergency and len(description) < 5:
            flash("Please describe the problem in a few words.", "error")
        else:
            if is_emergency and not description:
                description = "Emergency. No details given."
            db = get_db()
            cursor = db.execute(
                "INSERT INTO requests (room, type, description, created_at) "
                "VALUES (?, ?, ?, ?)",
                (room, request_type, description,
                 datetime.now(timezone.utc).isoformat()),
            )
            db.commit()
            flash(f"Your request has been received. Request number: #{cursor.lastrowid}", "success")
            return redirect(url_for("my_requests"))

        # Validation failed: show the form again, keeping what they typed
        return render_template("report.html", types=REQUEST_TYPES,
                               room=room, description=description,
                               selected=request.form.get("type", ""))

    return render_template("report.html", types=REQUEST_TYPES,
                           room="", description="", selected="")


@app.route("/requests")
def my_requests():
    db = get_db()
    rows = db.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    return render_template("requests.html", requests=rows)


@app.route("/staff")
def staff():
    type_filter = request.args.get("type", "")
    status_filter = request.args.get("status", "")

    query = "SELECT * FROM requests WHERE 1=1"
    params = []
    if type_filter:
        query += " AND type = ?"
        params.append(type_filter)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    # Open emergencies first, then open requests (oldest first), then done ones
    query += (" ORDER BY (type = 'Emergency' AND status != 'Done') DESC,"
              " (status = 'Done') ASC,"
              " CASE WHEN status = 'Done' THEN -id ELSE id END ASC")

    db = get_db()
    rows = db.execute(query, params).fetchall()

    counts = {r["status"]: r["n"] for r in db.execute(
        "SELECT status, COUNT(*) AS n FROM requests GROUP BY status")}
    open_emergencies = db.execute(
        "SELECT COUNT(*) FROM requests WHERE type = 'Emergency' AND status != 'Done'"
    ).fetchone()[0]

    return render_template(
        "staff.html", requests=rows,
        types=REQUEST_TYPES + ["Emergency"], statuses=STATUSES,
        type_filter=type_filter, status_filter=status_filter,
        open_emergencies=open_emergencies,
        pending=counts.get("Pending", 0),
        in_progress=counts.get("In progress", 0),
        done=counts.get("Done", 0),
    )


@app.route("/staff/<int:request_id>/status", methods=["POST"])
def update_status(request_id):
    new_status = request.form.get("status", "")
    if new_status in STATUSES:
        db = get_db()
        db.execute("UPDATE requests SET status = ? WHERE id = ?",
                   (new_status, request_id))
        db.commit()
    return redirect(url_for("staff"))
if __name__ == "__main__":
    app.run(debug=True)
