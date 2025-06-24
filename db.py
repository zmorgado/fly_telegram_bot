import sqlite3
from contextlib import contextmanager

DB_FILE = "flights.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                price INTEGER,
                return_date TEXT,
                return_price INTEGER,
                totalPrice INTEGER,
                destination TEXT,
                webLink TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

def save_flight(flight):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO flights (date, price, return_date, return_price, totalPrice, destination, webLink)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                flight.get("date"),
                flight.get("price"),
                flight.get("return_date"),
                flight.get("return_price"),
                flight.get("totalPrice"),
                flight.get("destination"),
                flight.get("webLink")
            )
        )
        conn.commit()
