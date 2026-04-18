"""
Local Database Utilities for Bharat Bricks
SQLite Replacement for Databricks Delta Tables
"""

import sqlite3
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Database path
DB_PATH = Path("data/complaints.db")
DB_PATH.parent.mkdir(exist_ok=True, parents=True)

def get_connection():
    """Get SQLite connection with row factory"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database schema - run this once on setup"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Complaints table (main table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            complaint_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT,
            sub_category TEXT,
            latitude REAL,
            longitude REAL,
            pincode TEXT,
            city TEXT,
            state TEXT,
            media_urls TEXT,  -- JSON array stored as text
            status TEXT DEFAULT 'submitted',
            priority TEXT DEFAULT 'medium',
            assigned_body_id TEXT,
            assigned_officer_id TEXT,
            ai_category TEXT,
            ai_priority TEXT,
            ai_est_resolution_hours INTEGER DEFAULT 72,
            duplicate_of TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            closed_at TIMESTAMP
        )
    """)
    
    # Governing bodies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS governing_bodies (
            body_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            body_type TEXT,
            jurisdiction_level TEXT,
            parent_body_id TEXT,
            state TEXT,
            city TEXT,
            pincode TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            head_officer_name TEXT,
            head_officer_designation TEXT,
            categories TEXT,  -- JSON array stored as text
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Public votes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS public_votes (
            vote_id TEXT PRIMARY KEY,
            complaint_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            vote_type TEXT NOT NULL,  -- 'support', 'against', etc.
            target_type TEXT,
            target_id TEXT,
            location_radius REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id)
        )
    """)
    
    # Create indexes for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_votes_complaint ON public_votes(complaint_id)")
    
    conn.commit()
    conn.close()
    
    print("✅ Database initialized successfully at:", DB_PATH.absolute())
    print("📊 Tables created: complaints, governing_bodies, public_votes")

def insert_complaint(complaint_data: tuple):
    """Insert a new complaint"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        INSERT INTO complaints (
            complaint_id, user_id, title, description, category, sub_category,
            latitude, longitude, pincode, city, state, media_urls, status,
            priority, assigned_body_id, assigned_officer_id, ai_category,
            ai_priority, ai_est_resolution_hours, duplicate_of
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    cursor.execute(query, complaint_data)
    conn.commit()
    conn.close()

def update_complaint_status(complaint_id: str, new_status: str):
    """Update complaint status"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE complaints 
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE complaint_id = ?
    """, (new_status, complaint_id))
    
    conn.commit()
    conn.close()

def query_complaints(limit: int = 100, status: Optional[str] = None) -> pd.DataFrame:
    """Query complaints with vote counts"""
    conn = get_connection()
    
    base_query = """
        SELECT 
            c.*,
            COALESCE(COUNT(v.vote_id), 0) as support_count
        FROM complaints c
        LEFT JOIN public_votes v 
            ON c.complaint_id = v.complaint_id AND v.vote_type = 'support'
    """
    
    if status:
        base_query += f" WHERE c.status = '{status}'"
    
    base_query += """
        GROUP BY c.complaint_id
        ORDER BY c.created_at DESC
        LIMIT ?
    """
    
    df = pd.read_sql_query(base_query, conn, params=(limit,))
    conn.close()
    
    return df

def get_complaint_by_id(complaint_id: str) -> Optional[Dict[str, Any]]:
    """Get a single complaint by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.*,
            COALESCE(COUNT(v.vote_id), 0) as support_count
        FROM complaints c
        LEFT JOIN public_votes v 
            ON c.complaint_id = v.complaint_id AND v.vote_type = 'support'
        WHERE c.complaint_id = ?
        GROUP BY c.complaint_id
    """, (complaint_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def insert_vote(vote_id: str, complaint_id: str, user_id: str, vote_type: str = "support"):
    """Insert a support vote"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if user already voted
    cursor.execute("""
        SELECT COUNT(*) FROM public_votes 
        WHERE complaint_id = ? AND user_id = ?
    """, (complaint_id, user_id))
    
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False  # Already voted
    
    # Insert vote
    cursor.execute("""
        INSERT INTO public_votes (vote_id, complaint_id, user_id, vote_type, target_type, target_id)
        VALUES (?, ?, ?, ?, 'complaint', ?)
    """, (vote_id, complaint_id, user_id, vote_type, complaint_id))
    
    conn.commit()
    conn.close()
    return True

def get_statistics() -> Dict[str, Any]:
    """Get system statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total complaints
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total = cursor.fetchone()[0]
    
    # By status
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM complaints 
        GROUP BY status 
        ORDER BY count DESC
    """)
    status_counts = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Top supported complaints
    cursor.execute("""
        SELECT c.complaint_id, c.title, COUNT(v.vote_id) as votes
        FROM complaints c
        LEFT JOIN public_votes v ON c.complaint_id = v.complaint_id
        GROUP BY c.complaint_id
        ORDER BY votes DESC
        LIMIT 5
    """)
    top_supported = [{"id": row[0], "title": row[1], "votes": row[2]} for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_complaints": total,
        "status_counts": status_counts,
        "top_supported": top_supported
    }

def seed_governing_bodies():
    """Seed some sample governing bodies"""
    conn = get_connection()
    cursor = conn.cursor()
    
    bodies = [
        ("GB001", "Municipal Corporation Bhopal", "municipal", "city", None, "Madhya Pradesh", "Bhopal", 
         "462001", "mun@bhopal.gov.in", "0755-1234567", "Mr. Commissioner", "Commissioner",
         json.dumps(["Roads & Infrastructure", "Water Supply", "Garbage Collection"])),
        
        ("GB002", "Public Works Department (PWD)", "government", "state", None, "Madhya Pradesh", None,
         None, "pwd@mp.gov.in", "0755-9876543", "Mr. Chief Engineer", "Chief Engineer",
         json.dumps(["Roads & Infrastructure", "Bridges"])),
        
        ("GB003", "Water Supply Department", "government", "state", None, "Madhya Pradesh", None,
         None, "water@mp.gov.in", "0755-5555555", "Mr. Director", "Director",
         json.dumps(["Water Supply", "Sanitation"])),
    ]
    
    for body in bodies:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO governing_bodies (
                    body_id, name, body_type, jurisdiction_level, parent_body_id,
                    state, city, pincode, contact_email, contact_phone,
                    head_officer_name, head_officer_designation, categories
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, body)
        except sqlite3.IntegrityError:
            pass  # Already exists
    
    conn.commit()
    conn.close()
    print("✅ Seeded governing bodies")

if __name__ == "__main__":
    print("🔧 Setting up local database...")
    init_database()
    seed_governing_bodies()
    print("\n✨ Setup complete! Database ready at:", DB_PATH.absolute())
