-- Example Schema for the papers table
-- You do not need to run this if your table already exists, 
-- but ensure your DB structure matches the queries in src/database/connection.py

CREATE TABLE IF NOT EXISTS papers (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT,
    publication_date DATE,
    abstract TEXT,
    full_text TEXT,
    url TEXT,
    topic TEXT -- e.g., 'hypertension'
);

-- Optional: Table to store agent outputs/meta-analysis
CREATE TABLE IF NOT EXISTS research_insights (
    id SERIAL PRIMARY KEY,
    agent_name TEXT,
    paper_id INTEGER REFERENCES papers(id),
    insight TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
