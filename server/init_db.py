"""
Initialize the Personal-OS SQLite database schema
Run this on first deployment or to reset the database
"""

import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/memory.db")

def init_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Core identity table
    c.execute('''
    CREATE TABLE IF NOT EXISTS identity (
        id INTEGER PRIMARY KEY,
        key TEXT UNIQUE NOT NULL,
        value TEXT,
        category TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # People table
    c.execute('''
    CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        relationship TEXT,
        organization TEXT,
        role TEXT,
        email TEXT,
        phone TEXT,
        linkedin TEXT,
        twitter TEXT,
        website TEXT,
        location TEXT,
        how_we_met TEXT,
        notes TEXT,
        tags TEXT,
        importance INTEGER DEFAULT 3,
        last_contact DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Projects table
    c.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'active',
        category TEXT,
        tech_stack TEXT,
        github_url TEXT,
        website_url TEXT,
        start_date DATE,
        end_date DATE,
        notes TEXT,
        tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # People-Projects relationship
    c.execute('''
    CREATE TABLE IF NOT EXISTS people_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER,
        project_id INTEGER,
        role TEXT,
        notes TEXT,
        FOREIGN KEY (person_id) REFERENCES people(id),
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )
    ''')

    # Interactions/meetings log
    c.execute('''
    CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER,
        type TEXT,
        date DATE,
        summary TEXT,
        notes TEXT,
        follow_up TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (person_id) REFERENCES people(id)
    )
    ''')

    # Goals table
    c.execute('''
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT,
        status TEXT DEFAULT 'active',
        priority INTEGER DEFAULT 3,
        target_date DATE,
        completed_date DATE,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Skills table
    c.execute('''
    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        proficiency INTEGER,
        notes TEXT
    )
    ''')

    # Education table
    c.execute('''
    CREATE TABLE IF NOT EXISTS education (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institution TEXT NOT NULL,
        degree TEXT,
        field TEXT,
        start_year INTEGER,
        end_year INTEGER,
        achievements TEXT,
        notes TEXT
    )
    ''')

    # Work experience table
    c.execute('''
    CREATE TABLE IF NOT EXISTS work_experience (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        role TEXT,
        location TEXT,
        start_date DATE,
        end_date DATE,
        description TEXT,
        achievements TEXT,
        notes TEXT
    )
    ''')

    # Notes table
    c.execute('''
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        category TEXT,
        tags TEXT,
        related_person_id INTEGER,
        related_project_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (related_person_id) REFERENCES people(id),
        FOREIGN KEY (related_project_id) REFERENCES projects(id)
    )
    ''')

    # Files table - metadata for files stored in S3/Tigris
    c.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        content_type TEXT,
        size_bytes INTEGER,
        s3_key TEXT NOT NULL,
        category TEXT,
        tags TEXT,
        description TEXT,
        related_person_id INTEGER,
        related_project_id INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (related_person_id) REFERENCES people(id),
        FOREIGN KEY (related_project_id) REFERENCES projects(id)
    )
    ''')

    # Create indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_people_name ON people(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_people_relationship ON people(relationship)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_projects_category ON projects(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_interactions_date ON interactions(date)')

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_database()
