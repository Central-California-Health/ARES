import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any
from contextlib import contextmanager

class Database:
    def __init__(self):
        self.pool = None
        self.connect()

    def connect(self):
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=int(os.getenv("DB_MAX_CONN", "50")),
                host=os.getenv("DB_HOST", "localhost"),
                database=os.getenv("DB_NAME", "hypertension_db"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "password"),
                port=os.getenv("DB_PORT", "5432")
            )
            print("Connected to the database (Threaded Pool).")
            self.create_tables()
        except Exception as e:
            print(f"Error connecting to database: {e}")

    @contextmanager
    def get_conn(self):
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    def create_tables(self):
        """Creates necessary tables for storing agent outputs."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS agent_insights (
                id SERIAL PRIMARY KEY,
                agent_name TEXT,
                paper_id TEXT, 
                insight TEXT,
                themes TEXT[],
                quotes TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_reports (
                id SERIAL PRIMARY KEY,
                agent_name TEXT,
                report_type TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_memories (
                id SERIAL PRIMARY KEY,
                agent_name TEXT,
                description TEXT,
                importance FLOAT,
                embedding FLOAT[], 
                created_at TIMESTAMP,
                last_accessed TIMESTAMP
            );
            """
        ]
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    for q in queries:
                        cur.execute(q)
                conn.commit()
        except Exception as e:
            print(f"Error creating tables: {e}")

    def reset_tables(self):
        """Drops all agent tables and recreates them."""
        print("Warning: Resetting database tables (Deleting all agent data)...")
        queries = [
            "DROP TABLE IF EXISTS agent_insights;",
            "DROP TABLE IF EXISTS agent_reports;",
            "DROP TABLE IF EXISTS agent_memories;"
        ]
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    for q in queries:
                        cur.execute(q)
                conn.commit()
            print("Tables dropped successfully.")
            self.create_tables()
        except Exception as e:
            print(f"Error resetting tables: {e}")

    def save_memory(self, agent_name: str, description: str, importance: float, embedding: List[float], created_at: Any, last_accessed: Any):
        query = """
            INSERT INTO agent_memories 
            (agent_name, description, importance, embedding, created_at, last_accessed)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (agent_name, description, importance, embedding, created_at, last_accessed))
                conn.commit()
        except Exception as e:
            print(f"Error saving memory: {e}")

    def load_memories(self, agent_name: str) -> List[Dict[str, Any]]:
        query = "SELECT description, importance, embedding, created_at, last_accessed FROM agent_memories WHERE agent_name = %s"
        try:
            with self.get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (agent_name,))
                    return cur.fetchall()
        except Exception as e:
            print(f"Error loading memories: {e}")
            return []

    def save_insight(self, agent_name: str, paper_id: str, insight: str, themes: List[str] = None, quotes: List[str] = None):
        if themes is None:
            themes = []
        if quotes is None:
            quotes = []
        query = "INSERT INTO agent_insights (agent_name, paper_id, insight, themes, quotes) VALUES (%s, %s, %s, %s, %s)"
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (agent_name, paper_id, insight, themes, quotes))
                conn.commit()
        except Exception as e:
            print(f"Error saving insight: {e}")

    def save_report(self, agent_name: str, report_type: str, content: str):
        query = "INSERT INTO agent_reports (agent_name, report_type, content) VALUES (%s, %s, %s)"
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (agent_name, report_type, content))
                conn.commit()
        except Exception as e:
            print(f"Error saving report: {e}")

    def fetch_papers(self, limit: int = 10, offset: int = 0, keywords: List[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches papers from the database.
        Strictly filters for keywords in title, abstract, or summary.
        """
        if not self.pool:
            return []
        
        # Keyword Logic
        keyword_clause = ""
        params = []
        
        if keywords:
            conditions = []
            for k in keywords:
                # Check Title, Description, Summary, and Keywords array
                conditions.append("""
                    (c.title ILIKE %s 
                     OR COALESCE(c.description, '') ILIKE %s 
                     OR COALESCE(c.summary, '') ILIKE %s 
                     OR %s = ANY(c.keywords))
                """)
                pattern = f"%{k}%"
                params.extend([pattern, pattern, pattern, k])
            
            keyword_clause = "AND (" + " OR ".join(conditions) + ")"
        
        # --- BLOCKLIST FILTER ---
        # Exclude known corrupt author entries
        # We use a parameter for the pattern to avoid confusing psycopg2's placeholder parsing
        blocklist_clause = "AND c.authors::text NOT ILIKE %s"
        params.append('%Howaldt%')

        params.extend([limit, offset])

        query = f"""
            SELECT 
                c.id, 
                c.title,
                c.authors,
                c.published_at,
                c.doi,
                c.journal,
                c.source_url as url,
                COALESCE(c.description, c.summary, 'No abstract available') as abstract
            FROM contents c
            WHERE 
                c.content_type = 'research_article'
                {keyword_clause}
                {blocklist_clause}
            ORDER BY c.published_at DESC NULLS LAST
            LIMIT %s OFFSET %s
        """
        try:
            with self.get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, tuple(params))
                    return cur.fetchall()
        except Exception as e:
            print(f"Error fetching papers: {e}")
            return []

    def fetch_insights_with_details(self, agent_name: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetches insights joined with the original paper details.
        Useful for second-pass agents to review specific claims/quotes against the source text.
        """
        if not self.pool:
            return []

        params = []
        agent_clause = ""
        if agent_name:
            agent_clause = "AND ai.agent_name = %s"
            params.append(agent_name)
        
        params.append(limit)

        query = f"""
            SELECT 
                ai.id as insight_id,
                ai.agent_name,
                ai.insight,
                ai.themes,
                ai.quotes,
                ai.created_at as insight_date,
                c.id as paper_id,
                c.title,
                c.authors,
                c.published_at,
                c.source_url as url,
                c.sections,
                COALESCE(c.description, c.summary, 'No abstract') as abstract
            FROM agent_insights ai
            JOIN contents c ON ai.paper_id = CAST(c.id AS TEXT)
            WHERE 1=1
            {agent_clause}
            ORDER BY ai.created_at DESC
            LIMIT %s
        """
        try:
            with self.get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, tuple(params))
                    return cur.fetchall()
        except Exception as e:
            print(f"Error fetching insights with details: {e}")
            return []

    def close(self):
        if self.pool:
            self.pool.closeall()
