import psycopg2
import pandas as pd
from psycopg2 import sql, extras
import os

# Load environment variables
host = os.getenv("HOST")
port = os.getenv("PORT")
database = os.getenv("DATABASE")
user = os.getenv("DB_USER")
password = os.getenv("PASSWORD")

def connect_to_db(host, port, database, user, password):
    try:
        conn = psycopg2.connect(
            host=host, port=port, database=database, user=user, password=password
        )
        print("Connection successful")
        return conn
    except Exception as error:
        print(f"Error: {error}")
        return None

def create_tables(conn):
    """Create tables in PostgreSQL database"""
    commands = (
        """
        CREATE TABLE IF NOT EXISTS Comments (
            id SERIAL PRIMARY KEY,
            website_id VARCHAR(255),
            specific_url TEXT,
            comment TEXT,
            comment_level INTEGER,
            UNIQUE (specific_url, comment)  -- Add unique constraint
        )
        """,
    )
    
    try:
        cur = conn.cursor()
        # Execute each command
        for command in commands:
            cur.execute(command)
        cur.close()
        conn.commit()
        print("Table created or verified successfully")
    except Exception as error:
        print(f"Error: {error}")
        conn.rollback()
    finally:
        if cur is not None:
            cur.close()

def upsert_comments(conn, dataframe):
    """
    Inserts or updates comments in the database.
    """
    try:
        cur = conn.cursor()
        columns = list(dataframe.columns)
        values = [tuple(x) for x in dataframe.to_numpy()]
        
        insert_sql = sql.SQL(
            """
            INSERT INTO Comments ({}) 
            VALUES %s 
            ON CONFLICT (comment_id) DO NOTHING
            """
        ).format(sql.SQL(", ").join(map(sql.Identifier, columns)))
        
        extras.execute_values(cur, insert_sql, values)
        conn.commit()
        cur.close()
        print("Upsert operation completed successfully")
    except Exception as error:
        print(f"Error: {error}")

def query_db(conn, query, params=None):
    """
    Executes a query and returns the result as a DataFrame.
    """
    try:
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        cur.close()
        return pd.DataFrame(rows, columns=colnames)
    except Exception as error:
        print(f"Error: {error}")
        return None

# Establish connection and ensure table exists

if __name__ == "__main__":
    conn = connect_to_db(host, port, database, user, password)
    if conn:
        print("connected to postgres")
    else:
        print("failed to connect")
