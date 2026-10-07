


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

        if context.strip():
            guidance = (
                "Use the supplied vault notes as the source of truth for questions "
                "about the user's vault. If the notes do not contain the answer, "
                "say so clearly and do not invent vault facts. You may still answer "
                "general questions using your broader knowledge."
            )
        else:
            guidance = (
                "No matching vault notes were found. Answer the user's question "
                "using your broader knowledge, and be clear when you are unsure."
            )

        prompt = f"""
You are NEMO, a helpful conversational assistant for the user's mythology vault.

{guidance}

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

"""
        return prompt
