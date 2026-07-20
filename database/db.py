import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "regwatch.db")


def get_connection():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn


def execute(conn, query, params=()):
    cur = conn.execute(query, params)
    conn.commit()
    return cur


def fetchall(conn, query, params=()):
    return conn.execute(query, params).fetchall()


def fetchone(conn, query, params=()):
    return conn.execute(query, params).fetchone()
