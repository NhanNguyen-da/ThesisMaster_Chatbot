# Opens PostgreSQL connections from DATABASE_URL.
import psycopg

from app.config import DATABASE_URL


def get_connection():
    # Open a new connection; the caller closes it.
    return psycopg.connect(DATABASE_URL)
