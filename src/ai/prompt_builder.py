class PromptBuilder:

    def build_context(self, notes):
        context = ""

        for note in notes:
            context += f"""
Title:
{note["title"]}

Summary:
{note["summary"]}

Content:
{note["text"]}

----------------------
"""

        return context
    
    def build_prompt(self, question, context):

        return f"""
You are NEMO.

Answer ONLY using the supplied context.

If the answer is not present, say you don't know.

Context:

{context}

Question:

{question}

Answer:
"""