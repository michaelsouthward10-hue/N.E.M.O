from nemo.search.search_engine import SearchEngine
from nemo.ai.prompt_builder import PromptBuilder
from nemo.memory.conversation import ConversationMemory


class NemoChat:

    def __init__(self, ai):
        
        self.ai = ai
        self.search = SearchEngine()
        self.prompt_builder = PromptBuilder()
        self.memory = ConversationMemory()
    
    def ask(self, question):

        self.memory.add("user", question)

        query = (
            question
            .replace("Who is", "")
            .replace("who is", "")
            .replace("What is", "")
            .replace("what is", "")
            .replace("Tell me about", "")
            .replace("tell me about", "")
            .replace("?", "")
            .strip()
        )

        print("SEARCH QUERY:", query)

        results = self.search.search_by_text(query)

        if not results:
            return {
                "answer": "I couldn't find anything in your vault about that.",
                "sources": []
             }

        context = self.prompt_builder.build_context(results[:3])

        prompt = self.prompt_builder.build_prompt(question, context, self.memory.recent())

        answer = self.ai.answer(prompt)

        self.memory.add("assistant", answer)

        print("\nConversation Memory")

        for item in self.memory.recent():
            print(item)

        return {
            "answer": answer,
            "sources": [
                note["title"]
                for note in results[:3]
            ]
        }