def build_context(question, notes):

    context = ""

    for note in notes:

        context += f"""
==========================
TITLE:
{note["title"]}

SUMMARY:
{note.get("summary", "")}

CONTENT:
{note["text"]}
==========================

"""

    prompt = f"""
You are NEMO.

You are an AI archivist for a fantasy universe.

Answer ONLY using the information below.

If the answer cannot be found in the provided notes,
reply:

"I couldn't find that information in the vault."

Do not invent lore.

Context:

{context}

Question:

{question}

Answer:
"""

    return prompt