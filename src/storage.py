import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jds.db"

# Fields stored as JSON strings that are deserialized on read
_JSON_FIELDS = {
    "required_skills",
    "nice_to_have_skills",
    "tech_stack",
    "red_flags",
    "culture_signals",
    "score_breakdown",
}

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company             TEXT,
    role                TEXT,
    level               TEXT,
    required_skills     TEXT,
    nice_to_have_skills TEXT,
    experience_years    REAL,
    tech_stack          TEXT,
    red_flags           TEXT,
    culture_signals     TEXT,
    score_breakdown     TEXT,
    match_score         INTEGER,
    summary             TEXT,
    file_name           TEXT,
    file_hash           TEXT,
    created_at          TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_CREATE_TABLE)
        for col_def in ("file_name TEXT", "file_hash TEXT", "score_breakdown TEXT"):
            try:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_def}")
            except sqlite3.OperationalError:
                pass
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_file_hash ON jobs(file_hash)"
        )


def hash_exists(file_hash: str) -> bool:
    sql = "SELECT 1 FROM jobs WHERE file_hash = ? LIMIT 1"
    with _connect() as conn:
        return conn.execute(sql, (file_hash,)).fetchone() is not None


def save_job(data: dict, file_name: str = None, file_hash: str = None) -> int:
    row = {
        "company": data.get("company"),
        "role": data.get("role"),
        "level": data.get("level"),
        "required_skills": json.dumps(data.get("required_skills", [])),
        "nice_to_have_skills": json.dumps(data.get("nice_to_have_skills", [])),
        "experience_years": data.get("experience_years"),
        "tech_stack": json.dumps(data.get("tech_stack", [])),
        "red_flags": json.dumps(data.get("red_flags", [])),
        "culture_signals": json.dumps(data.get("culture_signals", [])),
        "score_breakdown": json.dumps(data.get("score_breakdown") or {}),
        "match_score": data.get("match_score"),
        "summary": data.get("summary"),
        "file_name": file_name,
        "file_hash": file_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sql = """
        INSERT INTO jobs (
            company, role, level, required_skills, nice_to_have_skills,
            experience_years, tech_stack, red_flags, culture_signals,
            score_breakdown, match_score, summary, file_name, file_hash, created_at
        ) VALUES (
            :company, :role, :level, :required_skills, :nice_to_have_skills,
            :experience_years, :tech_stack, :red_flags, :culture_signals,
            :score_breakdown, :match_score, :summary, :file_name, :file_hash, :created_at
        )
    """
    with _connect() as conn:
        cursor = conn.execute(sql, row)
        return cursor.lastrowid


def fetch_all_jobs() -> list[dict]:
    sql = "SELECT * FROM jobs ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    results = []
    for row in rows:
        result = dict(row)
        for field in _JSON_FIELDS:
            if result.get(field):
                result[field] = json.loads(result[field])
            else:
                result[field] = []
        results.append(result)
    return results


def list_jobs() -> list[dict]:
    sql = "SELECT id, company, role, created_at FROM jobs ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def fetch_job(job_id: int) -> dict | None:
    sql = "SELECT * FROM jobs WHERE id = ?"
    with _connect() as conn:
        row = conn.execute(sql, (job_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    for field in _JSON_FIELDS:
        if result.get(field):
            result[field] = json.loads(result[field])
    return result
