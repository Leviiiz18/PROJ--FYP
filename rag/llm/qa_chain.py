from llm.openrouter_llm import call_openrouter

def build_answer(context: str, question: str) -> str:
    prompt = f"""
You are a document-grounded assistant.

Rules:
- Answer ONLY using the provided context.
- If the answer is not found, say:
  "Not found in the uploaded documents."

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""
    return call_openrouter(prompt)
