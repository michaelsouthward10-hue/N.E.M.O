from pathlib import Path
import re

from nemo.ai.prompt_builder import PromptBuilder
from nemo.memory.conversation import ConversationMemory
from nemo.search.search_engine import SearchEngine
from nemo.services.router import QuestionRouter


class NemoChat:

    def __init__(self, ai, router=None, vault_path=None):
        
        self.ai = ai
        self.search = SearchEngine()
        self.prompt_builder = PromptBuilder()
        self.memory = ConversationMemory()
        self.router = router or QuestionRouter()
        self.vault_path = Path(vault_path) if vault_path else None
    
    def ask(self, question):

        self.memory.add("user", question)

        note_request = self._note_request(question)
        if note_request is not None:
            return self._create_note(note_request)

        route = self.router.route(question)
        if route == "relationship":
            result = self.router.handle(question)
            path = result.get("result")
            if path:
                answer = " → ".join(path)
            else:
                answer = result.get(
                    "message",
                    "I couldn't find a connection between those notes in your vault."
                )
            self.memory.add("assistant", answer)
            return {"answer": answer, "sources": path or []}

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

    @staticmethod
    def _note_request(question):
        match = re.match(
            r"\s*(?:/note|new note|create note)\s*:?[ \t]*(.+?)\s*$",
            question,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _create_note(self, request):
        if self.vault_path is None:
            from nemo.core.config import load_settings

            self.vault_path = Path(load_settings()["vault"]["path"])

        if not self.vault_path.is_dir():
            return {
                "answer": f"I couldn't find the configured Obsidian vault: {self.vault_path}",
                "sources": [],
            }

        title = request.strip().removesuffix(".md").strip()
        safe_name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "-", title).strip(" .")
        if re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", safe_name, re.IGNORECASE):
            safe_name = f"_{safe_name}"
        safe_name = safe_name[:180].rstrip(" .")
        if not safe_name:
            return {"answer": "Please give the new note a title.", "sources": []}

        target = self.vault_path / f"{safe_name}.md"
        if target.exists():
            return {
                "answer": f"A note named '{safe_name}' already exists, so I left it unchanged.",
                "sources": [],
            }

        matches_by_title = {}
        for term in re.findall(r"[\w'-]+", request):
            term = term.lower().removesuffix("'s")
            if len(term) < 3:
                continue
            for note in self.search.search_by_text(term):
                matches_by_title.setdefault(note["title"], note)
        matches = list(matches_by_title.values())[:3]
        context = self.prompt_builder.build_context(matches)
        prompt = (
            "You are NEMO, writing a new Obsidian Markdown note for the user.\n"
            "Use the supplied vault notes as the source of truth. If they do not "
            "contain enough information, say so clearly and do not invent facts.\n"
            "Return only the note body in Markdown, without a title heading.\n\n"
            f"Requested note: {request}\n\n"
            f"Relevant vault notes:\n{context}"
        )
        body = self.ai.answer(prompt).strip()
        target.write_text(f"# {safe_name}\n\n{body}\n", encoding="utf-8")
        answer = f"Created the note '{safe_name}' in your Obsidian vault."
        self.memory.add("assistant", answer)
        return {"answer": answer, "sources": [str(target)]}
