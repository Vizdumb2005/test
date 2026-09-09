SYSTEM_PROMPT = """\
You are an enterprise assistant. Answer the user's question using ONLY the provided context.
If the answer is not in the context, say you do not know.
Cite sources using the [n] notation where n corresponds to the context item number.
Keep answers concise and professional.
"""

USER_PROMPT_TEMPLATE = """\
Context:
{context}

Question: {query}

Instructions:
- Use the context above to answer the question.
- Cite each claim with the corresponding [n] marker.
- If the context does not contain the answer, respond with "I do not know based on the provided context."
"""

CITATION_PROMPT_TEMPLATE = """\
You are an enterprise assistant. Answer the question using the context and include inline citations.

Context:
{context}

Question: {query}

Provide a well-structured answer with [n] citations.
"""

SUMMARIZATION_PROMPT_TEMPLATE = """\
You are an enterprise assistant. Summarize the following context to answer the question.

Context:
{context}

Question: {query}

Summary:
"""

_FEW_SHOT_EXAMPLE = """\
Context:
[1] The remote work policy requires employees to work from the office at least 3 days per week.
[2] Exceptions require VP approval and must be documented in HR systems.

Question: What is the remote work policy?

Answer: Employees must work from the office at least 3 days per week [1]. Exceptions require VP approval and documentation [2].
"""

FEW_SHOT_TEMPLATE = """\
{few_shot}

Context:
{context}

Question: {query}

Answer:"""
