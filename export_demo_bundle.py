import os
import json
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Custom JSON Encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)

def export_demo_data():
    load_dotenv()
    
    # Connection Parameters
    host = os.getenv("DB_HOST", "localhost")
    dbname = os.getenv("DB_NAME", "hypertension_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "password")
    port = os.getenv("DB_PORT", "5432")

    print(f"Connecting to DB: {dbname} at {host}:{port} as {user}...")

    try:
        conn = psycopg2.connect(
            host=host,
            database=dbname,
            user=user,
            password=password,
            port=port
        )
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return

    query = """
        SELECT 
            c.id, 
            c.title,
            c.authors,
            c.published_at,
            c.doi,
            c.journal,
            c.source_url as url,
            COALESCE(c.description, c.summary, 'No abstract available') as abstract,
            c.sections,
            c.content_type
        FROM contents c
        WHERE c.content_type = 'research_article'
        ORDER BY c.published_at DESC NULLS LAST
        LIMIT 20
    """

    output_file = "demo_papers.jsonl"
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
            
            print(f"Fetched {len(rows)} papers.")
            
            with open(output_file, "w", encoding="utf-8") as f:
                for row in rows:
                    # Ensure UUIDs or other non-serializable types are handled if necessary
                    # ID might be UUID in DB but psycopg2 usually handles it as string or object.
                    # We'll rely on the encoder for dates.
                    
                    # Ensure 'authors' is JSON-serializable if it's a string from DB (psycopg2 might return dict if it's JSONB)
                    # If it's text/varchar, it stays string.
                    
                    json_line = json.dumps(row, cls=DateTimeEncoder)
                    f.write(json_line + "\n")
                    
            print(f"Successfully exported to {output_file}")
            
    except Exception as e:
        print(f"Error executing export: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    export_demo_data()
