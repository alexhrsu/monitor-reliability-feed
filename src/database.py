"""
Database models and setup for the Monitor Reliability Feed.

We use SQLite for simplicity - easy to run locally, no setup required.
Can migrate to PostgreSQL later if needed.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# Database file location
DB_PATH = Path(__file__).parent.parent / "data" / "reliability.db"


def get_connection():
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


def init_database():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Products table - the things we're tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            brand TEXT,
            category TEXT NOT NULL,
            subcategory TEXT,
            release_date TEXT,
            specs_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Reliability scores - calculated scores for each product
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reliability_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            grade TEXT,
            confidence TEXT,
            data_points INTEGER DEFAULT 0,
            trend TEXT,
            trend_delta INTEGER,
            trend_period TEXT,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    # Issues - specific problems reported for products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT CHECK(severity IN ('critical', 'high', 'medium', 'low')),
            frequency TEXT CHECK(frequency IN ('very_common', 'common', 'uncommon', 'rare')),
            affected_percentage REAL,
            status TEXT CHECK(status IN ('unresolved', 'partially_resolved', 'resolved', 'ongoing')),
            first_reported TEXT,
            last_reported TEXT,
            mention_count INTEGER DEFAULT 0,
            workaround TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    # Positives - good things reported about products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positives (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            title TEXT NOT NULL,
            frequency TEXT,
            mention_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    # Source data - raw data from each source (Reddit, iFixit, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS source_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_url TEXT,
            raw_data TEXT,
            sentiment TEXT,
            extracted_issues TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    # Issue sources - links issues to their data sources
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issue_sources (
            issue_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_count INTEGER DEFAULT 0,
            PRIMARY KEY (issue_id, source_type),
            FOREIGN KEY (issue_id) REFERENCES issues(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def add_product(product_id: str, name: str, brand: str, category: str, 
                subcategory: str = None, specs: dict = None):
    """Add a new product to track."""
    import json
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO products (id, name, brand, category, subcategory, specs_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (product_id, name, brand, category, subcategory, 
          json.dumps(specs) if specs else None, datetime.utcnow().isoformat()))
    
    conn.commit()
    conn.close()


def get_product(product_id: str) -> dict:
    """Get a product by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_all_products(category: str = None) -> list:
    """Get all products, optionally filtered by category."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if category:
        cursor.execute("SELECT * FROM products WHERE category = ?", (category,))
    else:
        cursor.execute("SELECT * FROM products")
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


if __name__ == "__main__":
    # Run this file directly to initialize the database
    init_database()
    print("Database ready!")
