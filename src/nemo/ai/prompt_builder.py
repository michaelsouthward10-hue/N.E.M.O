


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
    
    def build_prompt(self, question, context, history):
        conversation = ""

        for item in history:
            conversation += (
                f"{item['role'].capitalize()}: "
                f"{item['message']}\n"
            )

        prompt = f"""
You are NEMO.

You are an expert on the user's mythology vault.

Answer ONLY using the supplied notes.

If the conversation references previous questions,
use the conversation history to understand pronouns
such as he, she, they, it, him and her.

Conversation:

{conversation}

Knowledge:

{context}

Question:

{question}

Answer naturally.

Do not invent lore.

If the answer is not present in the notes,
say you don't know.
"""
        return prompt