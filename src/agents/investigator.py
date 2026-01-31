import datetime
import json
from typing import List
from .llm import LLM
from database.connection import Database

class InvestigatorAgent:
    def __init__(self, db: Database, llm: LLM):
        self.db = db
        self.llm = llm
        self.name = "The Investigator"

    def _load_prompt(self, filename: str, **kwargs) -> str:
        try:
            with open(f"prompts/{filename}", "r") as f:
                template = f.read()
            return template.format(**kwargs)
        except Exception as e:
            print(f"Error loading prompt {filename}: {e}")
            return ""

    def run_investigation(self, target_agent: str = "Dr. Analysis", limit: int = 5):
        print(f"[{self.name}] Fetching recent insights from {target_agent} for deep-dive...")
        
        # 1. Fetch data (Insights + Original Paper Link)
        records = self.db.fetch_insights_with_details(agent_name=target_agent, limit=limit)
        
        if not records:
            print(f"[{self.name}] No records found for {target_agent}.")
            return

        report_entries = []

        for row in records:
            print(f"\n[{self.name}] Investigating Paper: {row['title'][:50]}...")
            
            # Format Quotes
            quotes_list = row.get('quotes', [])
            if not quotes_list:
                quotes_str = "No specific quotes recorded."
            else:
                quotes_str = "\n".join([f'- "{q}"' for q in quotes_list])

            # Prepare Full Text from Sections
            full_text = ""
            sections_data = row.get('sections')
            
            if sections_data and isinstance(sections_data, dict) and 'sections' in sections_data:
                try:
                    for section in sections_data['sections']:
                        header = section.get('header', 'Unknown Section')
                        body = section.get('body', '')
                        full_text += f"## {header}\n{body}\n\n"
                except Exception as e:
                    print(f"Error parsing sections for {row['title']}: {e}")
                    full_text = row['abstract']
            else:
                full_text = f"Abstract: {row['abstract']}"

            # Limit text length to avoid token limits (rough safeguard)
            if len(full_text) > 50000:
                 full_text = full_text[:50000] + "\n...[TRUNCATED]"

            # 2. Construct Prompt
            prompt = self._load_prompt(
                "deep_dive.txt",
                agent_name=row['agent_name'],
                insight=row['insight'],
                quotes=quotes_str,
                title=row['title'],
                authors=str(row['authors']),
                date=str(row['published_at']),
                full_text=full_text
            )

            # 3. Generate Analysis
            analysis = self.llm.generate(prompt, system_message="You are a meticulous research auditor.")
            
            # 4. Save/Log
            entry = f"## Investigation of: {row['title']}\n\n**Original Insight:** {row['insight']}\n\n**Investigator's Report:**\n{analysis}\n\n---\n"
            report_entries.append(entry)
            print(f"[{self.name}] > Analysis Complete.")

            # Optional: Save back to DB as a 'refined_report'
            self.db.save_report(self.name, "deep_dive", analysis)

        return report_entries
