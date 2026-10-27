# Flask app with CORS and the GET /health endpoint.
import psycopg
from flask import Flask, jsonify
from flask_cors import CORS

from app.config import ALLOWED_ORIGIN
from app.db import get_connection
from app.ollama_routes import ollama_bp
from app.sessions import sessions_bp

app = Flask(__name__)
CORS(app, origins=[ALLOWED_ORIGIN])
app.register_blueprint(ollama_bp)
app.register_blueprint(sessions_bp)

# Fixed count queries, one per table (never built with string formatting).
COUNT_QUERIES = {
    "tm_vaitro": "SELECT COUNT(*) FROM tm_vaitro",
    "tm_huongxutri": "SELECT COUNT(*) FROM tm_huongxutri",
    "tm_lydoketthuc": "SELECT COUNT(*) FROM tm_lydoketthuc",
    "tm_prompt": "SELECT COUNT(*) FROM tm_prompt",
    "tt_hoithoai": "SELECT COUNT(*) FROM tt_hoithoai",
    "tt_tinnhan": "SELECT COUNT(*) FROM tt_tinnhan",
    "tt_tinnhan_ketqua": "SELECT COUNT(*) FROM tt_tinnhan_ketqua",
    "tt_tinnhan_phantich": "SELECT COUNT(*) FROM tt_tinnhan_phantich",
}


@app.get("/health")
def health():
    # Check the database and return the row count of each table.
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            tables = {}
            for name, query in COUNT_QUERIES.items():
                cur.execute(query)
                tables[name] = cur.fetchone()[0]
    except psycopg.OperationalError:
        # Fixed message: driver text may contain host or user details.
        return jsonify(status="error", detail="Cannot connect to the database"), 503
    except psycopg.Error:
        return jsonify(status="error", detail="Database query failed"), 503
    return jsonify(status="ok", database="chatbot_db", tables=tables)
