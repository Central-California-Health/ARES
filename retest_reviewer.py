import os
from dotenv import load_dotenv
from src.agents.llm import LLM
from src.agents.meta_reviewer import MetaReviewerAgent

load_dotenv()

def run_test():
    llm = LLM()
    reviewer = MetaReviewerAgent(llm)
    reviewer.run_review(source_file="living_meta_analysis.md")

if __name__ == "__main__":
    run_test()
