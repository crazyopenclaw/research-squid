"""
Agent implementations — the researchers of the institute.

Each agent is a LangGraph node function that:
1. Reads context from the knowledge graph and RAG
2. Reasons via LLM calls
3. Writes artifacts back to the graph
4. Returns updated state
"""
