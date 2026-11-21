import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, render_template, request, send_from_directory

from road_ai import analyze_road_image


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = BASE_DIR / "roadguard.db"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["DATABASE"] = str(DB_PATH)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                citizen_name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                location TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                description TEXT,
                image_name TEXT,
                damage_type TEXT DEFAULT 'Unknown',
                severity TEXT DEFAULT 'Low',
                priority_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Submitted',
                ai_confidence REAL DEFAULT 0,
                analysis_notes TEXT,
                duplicate_of INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (duplicate_of) REFERENCES complaints(id)
            );
            """
        )
        existing_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(complaints)").fetchall()
        }
        advanced_columns = {
            "hazard_type": "TEXT",
            "road_type": "TEXT",
            "traffic_impact": "TEXT",
            "safety_risk": "TEXT",
            "observed_at": "TEXT",
            "affected_area": "TEXT",
        }
        for column, column_type in advanced_columns.items():
            if column not in existing_columns:
                db.execute(
                    f"ALTER TABLE complaints ADD COLUMN {column} {column_type}"
                )


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_coordinate(value, field_name, minimum, maximum):
    if value in (None, ""):
        return None
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number")
    if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
        raise ValueError(f"{field_name} is outside the valid range")
    return coordinate


def complaint_to_dict(row):
    item = dict(row)
    item["image_url"] = (
        f"/static/uploads/{item['image_name']}" if item["image_name"] else None
    )
    return item


@app.before_request
def ensure_database():
    database_path = app.config["DATABASE"]
    if app.config.get("_INITIALIZED_DATABASE") != database_path:
        init_db()
        app.config["_INITIALIZED_DATABASE"] = database_path


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": "The uploaded request exceeds the 10 MB limit"}), 413


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/complaints", methods=["GET", "POST"])
def complaints():
    if request.method == "POST":
        citizen_name = request.form.get("citizen_name", "").strip()
        location = request.form.get("location", "").strip()
        if not citizen_name or not location:
            return jsonify({"error": "Name and location are required"}), 400
        if len(citizen_name) > 120 or len(location) > 250:
            return jsonify({"error": "Name or location is too long"}), 400

        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        description = request.form.get("description", "").strip()
        hazard_type = request.form.get("hazard_type", "").strip()
        road_type = request.form.get("road_type", "").strip()
        traffic_impact = request.form.get("traffic_impact", "").strip()
        safety_risk = request.form.get("safety_risk", "").strip()
        observed_at = request.form.get("observed_at", "").strip()
        affected_area = request.form.get("affected_area", "").strip()
        advanced_fields = (
            hazard_type,
            road_type,
            traffic_impact,
            safety_risk,
            observed_at,
            affected_area,
        )
        if len(phone) > 40 or len(email) > 254 or len(description) > 2000:
            return jsonify({"error": "A submitted field exceeds its maximum length"}), 400
        if any(len(value) > 120 for value in advanced_fields):
            return jsonify({"error": "An advanced detail exceeds its maximum length"}), 400
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return jsonify({"error": "Enter a valid email address"}), 400
        try:
            latitude = parse_coordinate(request.form.get("latitude"), "Latitude", -90, 90)
            longitude = parse_coordinate(request.form.get("longitude"), "Longitude", -180, 180)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if (latitude is None) != (longitude is None):
            return jsonify({"error": "Latitude and longitude must be provided together"}), 400

        image_name = None
        image = request.files.get("image")
        if image and image.filename:
            if not allowed_file(image.filename):
                return jsonify({"error": "Unsupported image type"}), 400
            try:
                image.stream.seek(0)
                with Image.open(image.stream) as uploaded_image:
                    uploaded_image.verify()
                image.stream.seek(0)
            except (
                UnidentifiedImageError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
                OSError,
                ValueError,
            ):
                return jsonify({"error": "The uploaded file is not a valid image"}), 400
            image_name = (
                f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_"
                f"{secure_filename(image.filename)}"
            )
            upload_dir = Path(app.config["UPLOAD_FOLDER"])
            upload_dir.mkdir(parents=True, exist_ok=True)
            image.save(upload_dir / image_name)

        analysis = (
            analyze_road_image(str(Path(app.config["UPLOAD_FOLDER"]) / image_name))
            if image_name
            else {
                "damage_type": "Not analyzed",
                "severity": "Low",
                "priority_score": 20,
                "confidence": 0.0,
                "notes": "No image provided.",
            }
        )

        now = datetime.utcnow().isoformat(timespec="seconds")
        normalized_location = location.lower().strip()
        with get_db() as db:
            duplicate = db.execute(
                """
                SELECT id FROM complaints
                WHERE LOWER(TRIM(location)) = ? AND status NOT IN ('Resolved', 'Rejected')
                ORDER BY created_at DESC LIMIT 1
                """,
                (normalized_location,),
            ).fetchone()

            duplicate_id = duplicate["id"] if duplicate else None
            priority_score = analysis["priority_score"]
            risk_bonus = {
                "Immediate danger": 20,
                "High": 15,
                "Moderate": 8,
                "Low": 3,
            }.get(safety_risk, 0)
            traffic_bonus = {
                "Road fully blocked": 15,
                "Single-lane blockage": 10,
                "Minor slowdown": 5,
            }.get(traffic_impact, 0)
            priority_score = min(100, priority_score + risk_bonus + traffic_bonus)
            if duplicate_id:
                priority_score = min(100, priority_score + 10)

            cursor = db.execute(
                """
                INSERT INTO complaints (
                    citizen_name, phone, email, location, latitude, longitude,
                    description, image_name, damage_type, severity,
                    priority_score, status, ai_confidence, analysis_notes,
                    duplicate_of, hazard_type, road_type, traffic_impact,
                    safety_risk, observed_at, affected_area, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    citizen_name,
                    phone,
                    email,
                    location,
                    latitude,
                    longitude,
                    description,
                    image_name,
                    analysis["damage_type"],
                    analysis["severity"],
                    priority_score,
                    "Submitted",
                    analysis["confidence"],
                    analysis["notes"],
                    duplicate_id,
                    hazard_type,
                    road_type,
                    traffic_impact,
                    safety_risk,
                    observed_at,
                    affected_area,
                    now,
                    now,
                ),
            )
            complaint_id = cursor.lastrowid
            complaint = db.execute(
                "SELECT * FROM complaints WHERE id = ?", (complaint_id,)
            ).fetchone()

        return jsonify({
            "message": "Complaint submitted successfully",
            "complaint": complaint_to_dict(complaint),
            "is_duplicate": duplicate_id is not None,
        }), 201

    status = request.args.get("status")
    severity = request.args.get("severity")
    search = request.args.get("search")
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if search:
        query += " AND (citizen_name LIKE ? OR location LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    query += " ORDER BY priority_score DESC, created_at DESC"

    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return jsonify([complaint_to_dict(row) for row in rows])


@app.route("/api/complaints/<int:complaint_id>", methods=["GET", "PATCH"])
def complaint_detail(complaint_id):
    with get_db() as db:
        if request.method == "PATCH":
            payload = request.get_json(silent=True) or {}
            status = payload.get("status")
            allowed_statuses = {"Submitted", "Assigned", "In Progress", "Resolved", "Rejected"}
            if status not in allowed_statuses:
                return jsonify({"error": "Invalid status"}), 400
            db.execute(
                "UPDATE complaints SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.utcnow().isoformat(timespec="seconds"), complaint_id),
            )
        row = db.execute(
            "SELECT * FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "Complaint not found"}), 404
    return jsonify(complaint_to_dict(row))


@app.route("/api/stats")
def stats():
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) AS count FROM complaints").fetchone()["count"]
        resolved = db.execute(
            "SELECT COUNT(*) AS count FROM complaints WHERE status = 'Resolved'"
        ).fetchone()["count"]
        critical = db.execute(
            "SELECT COUNT(*) AS count FROM complaints WHERE severity = 'Critical'"
        ).fetchone()["count"]
        pending = db.execute(
            "SELECT COUNT(*) AS count FROM complaints WHERE status NOT IN ('Resolved', 'Rejected')"
        ).fetchone()["count"]
        severities = db.execute(
            "SELECT severity, COUNT(*) AS count FROM complaints GROUP BY severity"
        ).fetchall()
    return jsonify({
        "total": total,
        "resolved": resolved,
        "critical": critical,
        "pending": pending,
        "severity": {row["severity"]: row["count"] for row in severities},
    })


@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    init_db()
    try:
        from waitress import serve
    except ImportError:
        raise SystemExit(
            "Waitress is required. Run: py -m pip install -r requirements.txt"
        )

    print("RoadGuard AI production server: http://127.0.0.1:5000")
    serve(app, host="127.0.0.1", port=5000)
