#!/usr/bin/env python
"""Test RAG helper function in isolation."""

import sys

sys.path.insert(0, "src")

# Initialize RAG database first
import qe_tax_rag as qe

qe.init()
print("RAG database initialized")

# Import after RAG initialization
from quickexpense.core.config import get_settings  # noqa: E402
from quickexpense.services.agents.cra_rules_agent import CRArulesAgent  # noqa: E402

# Initialize agent
settings = get_settings()
agent = CRArulesAgent(settings=settings)

# Test cases
test_cases = [
    ("Client lunch meeting", "meals", "Tim Hortons"),
    ("Office printer paper", "supplies", "Staples"),
    ("Hotel accommodation", "travel", "Marriott"),
]

print("Testing RAG context retrieval...\n")
for desc, cat, vendor in test_cases:
    print(f"Test: {desc} ({vendor})")
    context = agent._get_rag_context(desc, cat, vendor)  # noqa: SLF001
    print(f"Context length: {len(context)} chars")
    assert (  # noqa: S101
        "Citation ID" in context or "No specific CRA" in context
    ), f"Expected 'Citation ID' or 'No specific CRA' in context, got: {context[:100]}"
    print("✅ Pass\n")

print("All tests passed!")
