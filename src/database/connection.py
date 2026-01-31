import os
import json
import datetime
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any
from contextlib import contextmanager

class Database:
    def __init__(self):
        self.pool = None
        self.demo_mode = False
        self.demo_data = []
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
            print("Falling back to DEMO MODE (loading demo_papers.jsonl)...")
            self.demo_mode = True
            self._load_demo_data()

    def _load_demo_data(self):
        try:
            if os.path.exists("demo_papers.jsonl"):
                with open("demo_papers.jsonl", "r") as f:
                    for line in f:
                        if line.strip():
                            self.demo_data.append(json.loads(line))
                print(f"Loaded {len(self.demo_data)} papers from demo_papers.jsonl")
            else:
                print("Warning: demo_papers.jsonl not found.")
        except Exception as e:
            print(f"Error loading demo data: {e}")

    @contextmanager
    def get_conn(self):
        if self.pool:
            conn = self.pool.getconn()
            try:
                yield conn
            finally:
                self.pool.putconn(conn)
        else:
            # Should not be called if checks are in place, but for safety:
            yield None

    def create_tables(self):
        """Creates necessary tables for storing agent outputs."""
        if self.demo_mode:
            return

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
        if self.demo_mode:
            print("[Demo Mode] Reset tables ignored.")
            return

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
        if self.demo_mode:
            # print(f"[Demo Mode] Skipping memory save for {agent_name}")
            return

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
        if self.demo_mode:
            return []

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
        if self.demo_mode:
            return

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
        if self.demo_mode:
            return

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
        Fetches papers from the database or demo file.
        Strictly filters for keywords in title, abstract, or summary.
        """
        if self.demo_mode:
            return self._fetch_papers_demo(limit, offset, keywords)

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

    def _fetch_papers_demo(self, limit: int = 10, offset: int = 0, keywords: List[str] = None) -> List[Dict[str, Any]]:
        """
        In-memory implementation of fetch_papers for demo mode.
        """
        filtered_data = self.demo_data
        
        # 1. Blocklist Filter (Howaldt)
        filtered_data = [
            p for p in filtered_data 
            if "Howaldt" not in str(p.get('authors', ''))
        ]
        
        # 2. Keyword Filter
        if keywords:
            cleaned_keywords = [k.lower().strip() for k in keywords if k.strip()]
            if cleaned_keywords:
                matched_papers = []
                for paper in filtered_data:
                    # Construct searchable text
                    text = (
                        str(paper.get('title', '')) + " " + 
                        str(paper.get('abstract', '')) + " " + 
                        str(paper.get('description', ''))
                    ).lower()
                    
                    # OR Logic: Match any keyword
                    if any(k in text for k in cleaned_keywords):
                        matched_papers.append(paper)
                filtered_data = matched_papers

        # 3. Pagination
        # Note: demo_data is assumed to be already sorted by date desc from export
        start = offset
        end = offset + limit
        
        # Slice safely
        if start >= len(filtered_data):
            return []
            
        return filtered_data[start:end]

    def fetch_insights_with_details(self, agent_name: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetches insights joined with the original paper details.
        Useful for second-pass agents to review specific claims/quotes against the source text.
        """
        if self.demo_mode:
            # Demo mode currently does not support insights retrieval as we don't save them
            return []

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