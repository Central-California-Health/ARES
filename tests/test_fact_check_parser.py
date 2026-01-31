
def parse_response(verification_response):
    status = "UNKNOWN"
    evidence_lines = []
    parsing_evidence = False

    for line in verification_response.split('\n'):
        clean_line = line.strip()
        if clean_line.startswith("Status:"):
            status_part = clean_line.split(":", 1)[1].strip().upper()
            # Remove brackets and punctuation
            status = status_part.replace('[', '').replace(']', '').replace('.', '')
            parsing_evidence = False
        elif clean_line.startswith("Evidence:"):
            parsing_evidence = True
            content = clean_line.split(":", 1)[1].strip()
            if content:
                evidence_lines.append(content)
        elif parsing_evidence:
            evidence_lines.append(clean_line)
    
    evidence_text = "\n".join(evidence_lines).strip()
    return status, evidence_text

def test_multiline_evidence():
    response = """Status: [VERIFIED]
Evidence: [
  - \"Quote 1 is here.\"
  - \"Quote 2 is here.\"
]"""
    
    status, evidence = parse_response(response)
    print(f"Status: {status}")
    print(f"Evidence Length: {len(evidence)}")
    print(f"Evidence Content: {evidence!r}")
    
    assert status == "VERIFIED"
    assert len(evidence) > 10
    assert "Quote 1 is here" in evidence
    assert "Quote 2 is here" in evidence

def test_singleline_evidence():
    response = """Status: VERIFIED
Evidence: \"Single line quote.\" """
    
    status, evidence = parse_response(response)
    print(f"\nStatus: {status}")
    print(f"Evidence Length: {len(evidence)}")
    print(f"Evidence Content: {evidence!r}")

    assert status == "VERIFIED"
    assert "Single line quote" in evidence

if __name__ == "__main__":
    test_multiline_evidence()
    test_singleline_evidence()
    print("\nAll tests passed!")
