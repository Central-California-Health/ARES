import os
from dotenv import load_dotenv
from database.connection import Database

load_dotenv()

db = Database()
papers = db.fetch_papers(limit=1)

if papers:
    p = papers[0]
    print(f"Title: {p['title']}")
    print(f"Authors: {p['authors']} (Type: {type(p['authors'])})")
    print(f"Published At: {p['published_at']} (Type: {type(p['published_at'])})")
else:
    print("No papers found.")
db.close()
