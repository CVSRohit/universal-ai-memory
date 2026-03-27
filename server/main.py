"""
Personal-OS Memory API
FastAPI service for accessing the Personal-OS SQLite database
Designed for MCP integration with AI agents
"""

import os
import re
import sqlite3
import secrets
import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict
from contextlib import contextmanager
from pathlib import Path
from io import BytesIO

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File, Form, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import boto3
from botocore.config import Config

# ============== CONFIGURATION ==============

# API Key for authentication (set via environment variable)
API_KEY = os.environ.get("API_KEY", "")

# Database path - uses persistent volume on Fly.io
DB_PATH = os.environ.get("DB_PATH", "/data/memory.db")

# Owner info (configurable)
OWNER_NAME = os.environ.get("OWNER_NAME", "")

# S3/Tigris configuration for file storage
S3_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL_S3", "https://fly.storage.tigris.dev")
S3_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "")
S3_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
S3_BUCKET = os.environ.get("BUCKET_NAME", "personal-os-files")
S3_REGION = os.environ.get("AWS_REGION", "auto")

# File upload limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Blocked SQL patterns (destructive DDL)
BLOCKED_SQL_PATTERNS = [
    r'\bDROP\s+TABLE\b',
    r'\bDROP\s+DATABASE\b',
    r'\bTRUNCATE\b',
    r'\bALTER\s+TABLE\s+\w+\s+DROP\b',
]

app = FastAPI(
    title="Personal-OS Memory API",
    description="Universal AI Memory System - MCP Compatible",
    version="2.1.0"
)

# CORS - Allow dashboard and common local dev origins
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== AUTHENTICATION ==============

def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Verify API key if one is configured"""
    if not API_KEY:
        # No API key configured - allow all requests (for local dev)
        return True
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ============== HELPERS ==============

def get_s3_client():
    """Get S3 client for Tigris"""
    if not S3_ACCESS_KEY:
        return None
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version='s3v4')
    )

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def dict_from_row(row):
    return dict(row) if row else None

def is_sql_destructive(sql: str) -> bool:
    """Check if SQL contains destructive DDL patterns"""
    sql_upper = sql.upper()
    for pattern in BLOCKED_SQL_PATTERNS:
        if re.search(pattern, sql_upper, re.IGNORECASE):
            return True
    return False

# ============== MODELS ==============

class Person(BaseModel):
    name: str = Field(..., max_length=500)
    relationship: Optional[str] = Field(None, max_length=200)
    organization: Optional[str] = Field(None, max_length=500)
    role: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    linkedin: Optional[str] = Field(None, max_length=500)
    twitter: Optional[str] = Field(None, max_length=200)
    website: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    how_we_met: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=50000)
    tags: Optional[str] = Field(None, max_length=1000)
    importance: Optional[int] = Field(3, ge=1, le=5)

class Project(BaseModel):
    name: str = Field(..., max_length=500)
    description: Optional[str] = Field(None, max_length=50000)
    status: Optional[str] = Field("active", max_length=50)
    category: Optional[str] = Field(None, max_length=200)
    tech_stack: Optional[str] = Field(None, max_length=1000)
    github_url: Optional[str] = Field(None, max_length=500)
    website_url: Optional[str] = Field(None, max_length=500)
    start_date: Optional[str] = Field(None, max_length=20)
    end_date: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=50000)
    tags: Optional[str] = Field(None, max_length=1000)

class Interaction(BaseModel):
    person_id: int
    type: str = Field(..., max_length=100)
    date: str = Field(..., max_length=20)
    summary: str = Field(..., max_length=5000)
    notes: Optional[str] = Field(None, max_length=50000)
    follow_up: Optional[str] = Field(None, max_length=2000)

class Note(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    content: str = Field(..., max_length=100000)
    category: Optional[str] = Field(None, max_length=200)
    tags: Optional[str] = Field(None, max_length=1000)
    related_person_id: Optional[int] = None
    related_project_id: Optional[int] = None

class TableSchema(BaseModel):
    table_name: str = Field(..., max_length=100)
    columns: Dict[str, str]

class RecordData(BaseModel):
    data: Dict[str, Any]

class SeedData(BaseModel):
    identity: Optional[List[dict]] = None
    skills: Optional[List[dict]] = None
    education: Optional[List[dict]] = None
    work_experience: Optional[List[dict]] = None
    projects: Optional[List[dict]] = None

class SQLRequest(BaseModel):
    sql: str = Field(..., max_length=10000)
    params: Optional[List[Any]] = None

# ============== PUBLIC ENDPOINTS (No Auth) ==============

STATIC_DIR = Path(__file__).parent / "static"

@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the dashboard"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Personal-OS Memory API</h1><p>Dashboard not found. API is running.</p>")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Serve the dashboard"""
    return root()

@app.get("/health")
def health():
    """Health check - no auth required"""
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api")
def api_info():
    """API information for AI agents"""
    return {
        "service": "Personal-OS Memory API",
        "version": "2.1.0",
        "owner": OWNER_NAME if OWNER_NAME else "(not configured)",
        "mcp_compatible": True,
        "auth_required": bool(API_KEY),
        "capabilities": [
            "identity_management",
            "people_crm",
            "project_tracking",
            "dynamic_tables",
            "full_text_search",
            "sql_queries",
            "file_storage"
        ]
    }

@app.get("/dashboard-data")
def dashboard_data(_: bool = Depends(verify_api_key)):
    """Return all data needed for the dashboard"""
    with get_db() as conn:
        identity = conn.execute("SELECT key, value, category FROM identity").fetchall()
        skills = conn.execute("SELECT * FROM skills").fetchall()
        education = conn.execute("SELECT * FROM education ORDER BY end_year DESC").fetchall()
        work = conn.execute("SELECT * FROM work_experience ORDER BY end_date DESC NULLS FIRST").fetchall()
        people = conn.execute("SELECT * FROM people ORDER BY name LIMIT 100").fetchall()
        projects = conn.execute("SELECT * FROM projects ORDER BY created_at DESC LIMIT 100").fetchall()

        return {
            "identity": [dict_from_row(r) for r in identity],
            "skills": [dict_from_row(r) for r in skills],
            "education": [dict_from_row(r) for r in education],
            "work_experience": [dict_from_row(r) for r in work],
            "people": [dict_from_row(r) for r in people],
            "projects": [dict_from_row(r) for r in projects]
        }

# ============== IDENTITY (Auth Required) ==============

@app.get("/identity")
def get_identity(_: bool = Depends(verify_api_key)):
    with get_db() as conn:
        rows = conn.execute("SELECT key, value, category FROM identity").fetchall()
        return {"identity": [dict_from_row(r) for r in rows]}

@app.get("/identity/{key}")
def get_identity_key(key: str, _: bool = Depends(verify_api_key)):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM identity WHERE key = ?", (key,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"key": key, "value": row["value"]}

# ============== PEOPLE (Auth Required) ==============

@app.get("/people")
def list_people(
    relationship: Optional[str] = None,
    organization: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    _: bool = Depends(verify_api_key)
):
    with get_db() as conn:
        query = "SELECT * FROM people WHERE 1=1"
        params = []

        if relationship:
            query += " AND relationship = ?"
            params.append(relationship)
        if organization:
            query += " AND organization LIKE ?"
            params.append(f"%{organization}%")
        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")

        query += " ORDER BY importance DESC, name ASC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return {"people": [dict_from_row(r) for r in rows], "count": len(rows)}

@app.get("/people/{person_id}")
def get_person(person_id: int, _: bool = Depends(verify_api_key)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Person not found")
        return dict_from_row(row)

@app.post("/people")
def create_person(person: Person, _: bool = Depends(verify_api_key)):
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO people (name, relationship, organization, role, email, phone,
                              linkedin, twitter, website, location, how_we_met, notes, tags, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (person.name, person.relationship, person.organization, person.role,
              person.email, person.phone, person.linkedin, person.twitter, person.website,
              person.location, person.how_we_met, person.notes, person.tags, person.importance))
        conn.commit()
        return {"id": cursor.lastrowid, "message": "Person created"}

@app.put("/people/{person_id}")
def update_person(person_id: int, person: Person, _: bool = Depends(verify_api_key)):
    with get_db() as conn:
        conn.execute("""
            UPDATE people SET name=?, relationship=?, organization=?, role=?, email=?,
                            phone=?, linkedin=?, twitter=?, website=?, location=?,
                            how_we_met=?, notes=?, tags=?, importance=?, updated_at=?
            WHERE id = ?
        """, (person.name, person.relationship, person.organization, person.role,
              person.email, person.phone, person.linkedin, person.twitter, person.website,
              person.location, person.how_we_met, person.notes, person.tags, person.importance,
              datetime.now(), person_id))
        conn.commit()
        return {"id": person_id, "message": "Person updated"}

# ============== PROJECTS (Auth Required) ==============

@app.get("/projects")
def list_projects(
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    _: bool = Depends(verify_api_key)
):
    with get_db() as conn:
        query = "SELECT * FROM projects WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return {"projects": [dict_from_row(r) for r in rows], "count": len(rows)}

@app.post("/projects")
def create_project(project: Project, _: bool = Depends(verify_api_key)):
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO projects (name, description, status, category, tech_stack,
                                github_url, website_url, start_date, end_date, notes, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project.name, project.description, project.status, project.category,
              project.tech_stack, project.github_url, project.website_url,
              project.start_date, project.end_date, project.notes, project.tags))
        conn.commit()
        return {"id": cursor.lastrowid, "message": "Project created"}

# ============== INTERACTIONS (Auth Required) ==============

@app.get("/interactions")
def list_interactions(
    person_id: Optional[int] = None,
    type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    _: bool = Depends(verify_api_key)
):
    with get_db() as conn:
        query = """
            SELECT i.*, p.name as person_name
            FROM interactions i
            LEFT JOIN people p ON i.person_id = p.id
            WHERE 1=1
        """
        params = []

        if person_id:
            query += " AND i.person_id = ?"
            params.append(person_id)
        if type:
            query += " AND i.type = ?"
            params.append(type)

        query += " ORDER BY i.date DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return {"interactions": [dict_from_row(r) for r in rows], "count": len(rows)}

@app.post("/interactions")
def create_interaction(interaction: Interaction, _: bool = Depends(verify_api_key)):
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO interactions (person_id, type, date, summary, notes, follow_up)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (interaction.person_id, interaction.type, interaction.date,
              interaction.summary, interaction.notes, interaction.follow_up))
        conn.commit()

        conn.execute("UPDATE people SET last_contact = ? WHERE id = ?",
                    (interaction.date, interaction.person_id))
        conn.commit()

        return {"id": cursor.lastrowid, "message": "Interaction logged"}

# ============== NOTES (Auth Required) ==============

@app.get("/notes")
def list_notes(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    _: bool = Depends(verify_api_key)
):
    with get_db() as conn:
        query = "SELECT * FROM notes WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return {"notes": [dict_from_row(r) for r in rows], "count": len(rows)}

@app.post("/notes")
def create_note(note: Note, _: bool = Depends(verify_api_key)):
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO notes (title, content, category, tags, related_person_id, related_project_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (note.title, note.content, note.category, note.tags,
              note.related_person_id, note.related_project_id))
        conn.commit()
        return {"id": cursor.lastrowid, "message": "Note created"}

# ============== SEARCH (Auth Required) ==============

@app.get("/search")
def search(q: str, limit: int = Query(default=20, le=100), _: bool = Depends(verify_api_key)):
    """Search across people, projects, and notes"""
    results = {"people": [], "projects": [], "notes": []}

    with get_db() as conn:
        people = conn.execute("""
            SELECT id, name, relationship, organization, 'person' as type
            FROM people
            WHERE name LIKE ? OR organization LIKE ? OR notes LIKE ?
            LIMIT ?
        """, (f"%{q}%", f"%{q}%", f"%{q}%", limit)).fetchall()
        results["people"] = [dict_from_row(r) for r in people]

        projects = conn.execute("""
            SELECT id, name, status, category, 'project' as type
            FROM projects
            WHERE name LIKE ? OR description LIKE ? OR notes LIKE ?
            LIMIT ?
        """, (f"%{q}%", f"%{q}%", f"%{q}%", limit)).fetchall()
        results["projects"] = [dict_from_row(r) for r in projects]

        notes = conn.execute("""
            SELECT id, title, category, 'note' as type
            FROM notes
            WHERE title LIKE ? OR content LIKE ?
            LIMIT ?
        """, (f"%{q}%", f"%{q}%", limit)).fetchall()
        results["notes"] = [dict_from_row(r) for r in notes]

    return results

# ============== SKILLS & EDUCATION (Auth Required) ==============

@app.get("/skills")
def list_skills(_: bool = Depends(verify_api_key)):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM skills ORDER BY category, proficiency DESC").fetchall()
        return {"skills": [dict_from_row(r) for r in rows]}

@app.get("/education")
def list_education(_: bool = Depends(verify_api_key)):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM education ORDER BY end_year DESC").fetchall()
        return {"education": [dict_from_row(r) for r in rows]}

@app.get("/work")
def list_work(_: bool = Depends(verify_api_key)):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM work_experience ORDER BY start_date DESC").fetchall()
        return {"work_experience": [dict_from_row(r) for r in rows]}

# ============== RAW QUERY (Auth Required) ==============

@app.post("/query")
def raw_query(sql: str, _: bool = Depends(verify_api_key)):
    """Execute read-only SQL query"""
    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")

    with get_db() as conn:
        try:
            rows = conn.execute(sql).fetchall()
            return {"results": [dict_from_row(r) for r in rows], "count": len(rows)}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

# ============== SEED/IMPORT (Auth Required) ==============

@app.post("/seed")
def seed_database(data: SeedData, _: bool = Depends(verify_api_key)):
    """Bulk import data into the database"""
    results = {}

    with get_db() as conn:
        if data.identity:
            for item in data.identity:
                conn.execute(
                    "INSERT OR REPLACE INTO identity (key, value, category) VALUES (?, ?, ?)",
                    (item.get("key"), item.get("value"), item.get("category"))
                )
            results["identity"] = len(data.identity)

        if data.skills:
            for item in data.skills:
                conn.execute(
                    "INSERT INTO skills (name, category, proficiency, notes) VALUES (?, ?, ?, ?)",
                    (item.get("name"), item.get("category"), item.get("proficiency"), item.get("notes"))
                )
            results["skills"] = len(data.skills)

        if data.education:
            for item in data.education:
                conn.execute(
                    """INSERT INTO education (institution, degree, field, start_year, end_year, achievements, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (item.get("institution"), item.get("degree"), item.get("field"),
                     item.get("start_year"), item.get("end_year"), item.get("achievements"), item.get("notes"))
                )
            results["education"] = len(data.education)

        if data.work_experience:
            for item in data.work_experience:
                conn.execute(
                    """INSERT INTO work_experience (company, role, location, start_date, end_date, description, achievements, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item.get("company"), item.get("role"), item.get("location"),
                     item.get("start_date"), item.get("end_date"), item.get("description"),
                     item.get("achievements"), item.get("notes"))
                )
            results["work_experience"] = len(data.work_experience)

        if data.projects:
            for item in data.projects:
                conn.execute(
                    """INSERT INTO projects (name, description, status, category, tech_stack, github_url, website_url, notes, tags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item.get("name"), item.get("description"), item.get("status", "active"),
                     item.get("category"), item.get("tech_stack"), item.get("github_url"),
                     item.get("website_url"), item.get("notes"), item.get("tags"))
                )
            results["projects"] = len(data.projects)

        conn.commit()

    return {"message": "Data seeded successfully", "counts": results}

# ============== DYNAMIC TABLES (Auth Required) ==============

def sanitize_name(name: str) -> str:
    """Sanitize table/column names to prevent SQL injection"""
    return re.sub(r'[^a-zA-Z0-9_]', '', name)

@app.get("/tables")
def list_tables(_: bool = Depends(verify_api_key)):
    """List all tables in the database"""
    with get_db() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

        result = []
        for table in tables:
            table_name = table['name']
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            count = conn.execute(f"SELECT COUNT(*) as c FROM {table_name}").fetchone()

            result.append({
                "name": table_name,
                "columns": [{"name": c['name'], "type": c['type']} for c in columns],
                "record_count": count['c']
            })

        return {"tables": result}

@app.post("/tables")
def create_table(schema: TableSchema, _: bool = Depends(verify_api_key)):
    """Create a new table dynamically (for AI agents)"""
    table_name = sanitize_name(schema.table_name)

    if not table_name:
        raise HTTPException(status_code=400, detail="Invalid table name")

    col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    for col_name, col_type in schema.columns.items():
        safe_col = sanitize_name(col_name)
        safe_type = col_type.upper() if col_type.upper() in ['TEXT', 'INTEGER', 'REAL', 'BLOB'] else 'TEXT'
        col_defs.append(f"{safe_col} {safe_type}")

    col_defs.append("created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    col_defs.append("updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"

    with get_db() as conn:
        try:
            conn.execute(sql)
            conn.commit()
            return {"message": f"Table '{table_name}' created", "sql": sql}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

@app.get("/tables/{table_name}")
def get_table_records(
    table_name: str,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    _: bool = Depends(verify_api_key)
):
    """Get records from any table"""
    safe_table = sanitize_name(table_name)

    with get_db() as conn:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (safe_table,)
        ).fetchone()

        if not exists:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        rows = conn.execute(
            f"SELECT * FROM {safe_table} ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()

        total = conn.execute(f"SELECT COUNT(*) as c FROM {safe_table}").fetchone()

        return {
            "table": safe_table,
            "records": [dict_from_row(r) for r in rows],
            "count": len(rows),
            "total": total['c']
        }

@app.post("/tables/{table_name}")
def insert_record(table_name: str, record: RecordData, _: bool = Depends(verify_api_key)):
    """Insert a record into any table"""
    safe_table = sanitize_name(table_name)

    with get_db() as conn:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (safe_table,)
        ).fetchone()

        if not exists:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        columns_info = conn.execute(f"PRAGMA table_info({safe_table})").fetchall()
        valid_columns = {c['name'] for c in columns_info}

        data = {sanitize_name(k): v for k, v in record.data.items() if sanitize_name(k) in valid_columns}

        if not data:
            raise HTTPException(status_code=400, detail="No valid columns in data")

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())

        try:
            cursor = conn.execute(
                f"INSERT INTO {safe_table} ({columns}) VALUES ({placeholders})",
                values
            )
            conn.commit()
            return {"id": cursor.lastrowid, "message": f"Record inserted into '{safe_table}'"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

@app.put("/tables/{table_name}/{record_id}")
def update_record(table_name: str, record_id: int, record: RecordData, _: bool = Depends(verify_api_key)):
    """Update a record in any table"""
    safe_table = sanitize_name(table_name)

    with get_db() as conn:
        columns_info = conn.execute(f"PRAGMA table_info({safe_table})").fetchall()
        valid_columns = {c['name'] for c in columns_info}

        data = {sanitize_name(k): v for k, v in record.data.items() if sanitize_name(k) in valid_columns}
        data['updated_at'] = datetime.now().isoformat()

        if not data:
            raise HTTPException(status_code=400, detail="No valid columns in data")

        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [record_id]

        try:
            conn.execute(f"UPDATE {safe_table} SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return {"id": record_id, "message": f"Record updated in '{safe_table}'"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

@app.delete("/tables/{table_name}/{record_id}")
def delete_record(table_name: str, record_id: int, _: bool = Depends(verify_api_key)):
    """Delete a record from any table"""
    safe_table = sanitize_name(table_name)

    with get_db() as conn:
        try:
            conn.execute(f"DELETE FROM {safe_table} WHERE id = ?", (record_id,))
            conn.commit()
            return {"message": f"Record {record_id} deleted from '{safe_table}'"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

# ============== EXECUTE SQL (Auth Required, with safeguards) ==============

@app.post("/execute")
def execute_sql(request: SQLRequest, _: bool = Depends(verify_api_key)):
    """Execute SQL - blocks destructive DDL (DROP TABLE, TRUNCATE, etc.)"""
    sql = request.sql.strip()
    params = request.params or []

    # Block destructive DDL
    if is_sql_destructive(sql):
        raise HTTPException(
            status_code=403,
            detail="Destructive DDL operations (DROP TABLE, TRUNCATE, ALTER TABLE DROP) are blocked. Use the web dashboard for schema changes."
        )

    is_read = sql.upper().startswith(('SELECT', 'PRAGMA'))

    with get_db() as conn:
        try:
            if is_read:
                rows = conn.execute(sql, params).fetchall()
                return {"results": [dict_from_row(r) for r in rows], "count": len(rows)}
            else:
                cursor = conn.execute(sql, params)
                conn.commit()
                return {
                    "message": "SQL executed successfully",
                    "rows_affected": cursor.rowcount,
                    "last_row_id": cursor.lastrowid
                }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

# ============== FILE STORAGE (Auth Required) ==============

@app.get("/files")
def list_files(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    person_id: Optional[int] = None,
    project_id: Optional[int] = None,
    limit: int = Query(default=50, le=200),
    _: bool = Depends(verify_api_key)
):
    """List uploaded files"""
    with get_db() as conn:
        query = "SELECT * FROM files WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")
        if person_id:
            query += " AND related_person_id = ?"
            params.append(person_id)
        if project_id:
            query += " AND related_project_id = ?"
            params.append(project_id)

        query += " ORDER BY uploaded_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return {"files": [dict_from_row(r) for r in rows], "count": len(rows)}

@app.get("/files/{file_id}")
def get_file_info(file_id: int, _: bool = Depends(verify_api_key)):
    """Get file metadata"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        return dict_from_row(row)

@app.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    related_person_id: Optional[int] = Form(None),
    related_project_id: Optional[int] = Form(None),
    _: bool = Depends(verify_api_key)
):
    """Upload a file (max 50MB)"""
    s3 = get_s3_client()
    if not s3:
        raise HTTPException(status_code=503, detail="File storage not configured")

    # Read with size limit
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB")

    ext = Path(file.filename).suffix if file.filename else ""
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    s3_key = f"files/{unique_filename}"

    try:
        s3.upload_fileobj(
            BytesIO(content),
            S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO files (filename, original_filename, content_type, size_bytes, s3_key,
                             category, tags, description, related_person_id, related_project_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (unique_filename, file.filename, file.content_type, file_size, s3_key,
              category, tags, description, related_person_id, related_project_id))
        conn.commit()
        file_id = cursor.lastrowid

    return {
        "id": file_id,
        "filename": unique_filename,
        "original_filename": file.filename,
        "size_bytes": file_size,
        "message": "File uploaded successfully"
    }

@app.get("/files/{file_id}/download")
def download_file(file_id: int, _: bool = Depends(verify_api_key)):
    """Get presigned download URL"""
    s3 = get_s3_client()
    if not s3:
        raise HTTPException(status_code=503, detail="File storage not configured")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        file_data = dict_from_row(row)

    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': file_data['s3_key']},
            ExpiresIn=3600
        )
        return {
            "download_url": url,
            "filename": file_data['original_filename'],
            "content_type": file_data['content_type'],
            "expires_in": 3600
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")

@app.delete("/files/{file_id}")
def delete_file(file_id: int, _: bool = Depends(verify_api_key)):
    """Delete a file"""
    s3 = get_s3_client()
    if not s3:
        raise HTTPException(status_code=503, detail="File storage not configured")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        file_data = dict_from_row(row)

        try:
            s3.delete_object(Bucket=S3_BUCKET, Key=file_data['s3_key'])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete from storage: {str(e)}")

        conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        conn.commit()

    return {"message": f"File '{file_data['original_filename']}' deleted successfully"}

# ============== MCP DISCOVERY ==============

@app.get("/mcp/tools")
def mcp_tools():
    """MCP-compatible tool discovery"""
    return {
        "tools": [
            {"name": "memory_search", "description": "Search across all memory", "endpoint": "/search", "method": "GET"},
            {"name": "memory_query", "description": "Execute SQL query", "endpoint": "/execute", "method": "POST"},
            {"name": "memory_create_table", "description": "Create a new table", "endpoint": "/tables", "method": "POST"},
            {"name": "memory_insert", "description": "Insert a record", "endpoint": "/tables/{table_name}", "method": "POST"},
            {"name": "memory_list_tables", "description": "List all tables", "endpoint": "/tables", "method": "GET"},
            {"name": "memory_get_identity", "description": "Get owner identity", "endpoint": "/identity", "method": "GET"},
            {"name": "memory_get_people", "description": "List people", "endpoint": "/people", "method": "GET"},
            {"name": "memory_add_person", "description": "Add a person", "endpoint": "/people", "method": "POST"},
            {"name": "memory_upload_file", "description": "Upload a file", "endpoint": "/files", "method": "POST"},
            {"name": "memory_list_files", "description": "List files", "endpoint": "/files", "method": "GET"},
            {"name": "memory_download_file", "description": "Get download URL", "endpoint": "/files/{file_id}/download", "method": "GET"},
        ],
        "auth": "X-API-Key header required" if API_KEY else "No auth configured"
    }
