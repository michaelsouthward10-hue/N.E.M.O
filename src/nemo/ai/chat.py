from pathlib import Path
import re
import threading

from nemo.ai.prompt_builder import PromptBuilder
from nemo.memory.conversation import ConversationMemory
from nemo.search.search_engine import SearchEngine
from nemo.services.router import QuestionRouter
from nemo.parsers.entity_resolver import EntityResolver
from nemo.services.relationship_service import RelationshipService
from nemo.ai.ollama_client import GenerationCancelled
from nemo.core.storage import vault_key
from nemo.search.ranking import terms, passages
from nemo.search.semantic import SemanticSearch


class NemoChat:

    def __init__(self, ai, router=None, vault_path=None, recall_all=False):
        
        self.ai = ai
        self.recall_all = recall_all
        self.search = SearchEngine(vault_path or "")
        self.prompt_builder = PromptBuilder()
        self.memory = ConversationMemory.for_vault(vault_path)
        self.router = router or self._make_router()
        self.vault_path = Path(vault_path) if vault_path else None
        self.semantic = self._make_semantic(vault_path)

    def _make_router(self):
        return QuestionRouter(relationship_service=RelationshipService(resolver=EntityResolver(self.search)))

    def _make_semantic(self, vault_path):
        if not vault_path or not getattr(self.ai, "embedding_model", ""):
            return None
        from nemo.core.paths import DATA_DIR
        return SemanticSearch(DATA_DIR / "semantic" / f"{vault_key(vault_path)}.sqlite3", self.ai)

    def refresh_index(self):
        self.search = SearchEngine(self.vault_path or "")
        self.router = self._make_router()
    
    def set_vault(self, vault_path):
        self.vault_path = Path(vault_path) if vault_path else None
        self.memory = ConversationMemory.for_vault(vault_path)
        self.refresh_index()
        self.semantic = self._make_semantic(vault_path)

    def _conversation_context(self, question):
        return "\n".join(f"{item['role']}: {item['message']}" for item in self.memory.recall(question))

    def ask(self, question, mode="Ask", on_token=None, cancel_event=None):
        cancel_event = cancel_event or threading.Event()
        self.memory.add("user", question)
        try:
            result = self._ask(question, mode, on_token, cancel_event)
        except GenerationCancelled as error:
            result = {"answer": (error.partial + "\n\n[Stopped]").strip(), "sources": [], "stopped": True}
        except Exception as error:
            partial = getattr(error, "partial", "")
            self.memory.add("assistant", partial + f"\n\n[Failed: {error}]", status="failed")
            raise
        self.memory.add("assistant", result["answer"], result.get("evidence", result.get("sources", [])),
                        status="stopped" if result.get("stopped") else "complete")
        return result

    def _prepare_question(self, question, cancel_event):
        history = self.memory.recent(8, complete_only=True)[:-1]
        planning_budget = int(getattr(self.ai, "context_tokens", 8192))
        context = {"history": [{"role": item["role"], "message": item["message"][:min(800, planning_budget // 12)]} for item in history],
                   "pins": "\n".join(item["content"] for item in self.memory.pins()[-8:])[:min(2000, planning_budget // 4)],
                   "summary": self.memory.summary()["summary"][:min(2000, planning_budget // 4)]}
        if hasattr(self.ai, "plan_question"):
            try:
                return self.ai.plan_question(question, context, cancel_event)
            except GenerationCancelled:
                raise GenerationCancelled() from None
            except Exception:
                pass  # A planning failure must not prevent direct note search.
        resolved = question
        if re.search(r"\b(he|she|they|him|her|it|its|that|those)\b", question, re.IGNORECASE):
            sources = next((item["sources"] for item in reversed(history) if item.get("sources")), [])
            subjects = list(dict.fromkeys(item.get("title", "") if isinstance(item, dict) else str(item) for item in sources))
            if len(subjects) == 1:
                resolved += " " + subjects[0]
            elif len(subjects) > 1:
                return {"resolved_question": question, "search_terms": [], "clarification": "Which character or topic do you mean? " + ", ".join(subjects[:4])}
            elif history:
                previous = next((item["message"] for item in reversed(history) if item["role"] == "user"), "")
                resolved += " " + previous[:200]
        return {"resolved_question": resolved, "search_terms": [], "clarification": ""}

    def _generate(self, prompt, on_token, cancel_event):
        if cancel_event.is_set():
            raise GenerationCancelled()
        if hasattr(self.ai, "plan_question"):
            return self.ai.answer(prompt, on_token=on_token, cancel_event=cancel_event)
        answer = self.ai.answer(prompt)
        if cancel_event.is_set():
            raise GenerationCancelled()
        if on_token:
            on_token(answer)
        return answer

    def _retrieve(self, query, expansions, cancel_event):
        budget = max(4000, int(getattr(self.ai, "context_tokens", 8192)) * 2)
        if hasattr(self.search, "retrieve"):
            evidence = self.search.retrieve(query, expansions, max_chars=budget * 3 // 5,
                                            semantic=self.semantic, cancel_event=cancel_event)
        else:
            evidence = []
            for note in self.search.search_by_text(query):
                for passage in passages(note, note["title"]):
                    passage["id"] = f"S{len(evidence) + 1}"
                    evidence.append(passage)
        memory = self.memory.context(query, budget=budget // 3, expansions=expansions,
                                     semantic=self.semantic, cancel_event=cancel_event,
                                     all_conversations=self.recall_all)
        if self.vault_path:
            for item in evidence:
                item["vault"] = str(self.vault_path.resolve()).casefold()
        return evidence, memory

    def _ask(self, question, mode="Ask", on_token=None, cancel_event=None):

        note_request = self._note_request(question)
        if note_request is not None:
            return self._create_note(note_request, on_token, cancel_event)

        if mode == "Find connections":
            relationship_question = f"How are {question} connected?"
            result = self.router.handle(relationship_question)
            path = result.get("result")
            answer = " → ".join(path) if path else result.get(
                "message",
                "I couldn't find a connection between those notes in your vault.",
            )
            return {"answer": answer, "sources": path or []}

        route = self.router.route(question) if mode == "Ask" else "general"
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
            return {"answer": answer, "sources": path or []}

        if hasattr(self.ai, "summarize_conversation"):
            try:
                self.memory.summarize(self.ai, cancel_event)
            except GenerationCancelled:
                raise GenerationCancelled() from None
            except Exception:
                pass  # Raw messages remain available if summarizing temporarily fails.
        plan = self._prepare_question(question, cancel_event)
        if plan.get("clarification"):
            return {"answer": plan["clarification"], "sources": []}
        query = (
            plan["resolved_question"]
            .replace("Who is", "")
            .replace("who is", "")
            .replace("What is", "")
            .replace("what is", "")
            .replace("Tell me about", "")
            .replace("tell me about", "")
            .replace("?", "")
            .strip()
        )

        evidence, memory = self._retrieve(query, plan["search_terms"], cancel_event)
        if mode == "Summarize topic" and not evidence:
            return {"answer": f"I couldn't find any notes about '{question}' to summarize.", "sources": []}
        prompt = self.prompt_builder.build_prompt(question, evidence, memory, mode)
        answer = self._generate(prompt, on_token, cancel_event)
        answer, cited, warnings = self.prompt_builder.check_citations(answer, evidence)
        for item in evidence:
            item["cited"] = item["id"] in cited
        if getattr(self.search, "retrieval_warning", ""):
            warnings.append(self.search.retrieval_warning)
        if memory.get("omitted_pins"):
            warnings.append(f"{memory['omitted_pins']} pinned items did not fit into this reply's context. Shorten pins or increase the context size in AI settings to include more.")
        return {"answer": answer, "sources": list(dict.fromkeys(item["path"] for item in evidence)),
                "evidence": evidence, "cited": cited, "warnings": warnings}

    @staticmethod
    def _note_request(question):
        match = re.match(
            r"\s*(?:/note|new note|create note)\s*:?[ \t]*(.+?)\s*$",
            question,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _create_note(self, request, on_token=None, cancel_event=None):
        title = request.strip().removesuffix(".md").strip()
        destination, error = self._note_destination(title)
        if error:
            return error
        safe_name, target = destination
        if target.exists():
            return {
                "answer": f"A note named '{safe_name}' already exists, so I left it unchanged.",
                "sources": [],
            }

        plan = self._prepare_question(request, cancel_event)
        if plan.get("clarification"):
            return {"answer": plan["clarification"], "sources": []}
        evidence, memory = self._retrieve(plan["resolved_question"], plan["search_terms"], cancel_event)
        prompt = self.prompt_builder.build_prompt(request, evidence, memory, "Draft note")
        body = self._generate(prompt, on_token, cancel_event).strip()
        body, _, warnings = self.prompt_builder.check_citations(body, evidence)
        if cancel_event and cancel_event.is_set():
            raise GenerationCancelled()
        if not body:
            return {"answer": "The model returned an empty draft, so no note was saved.", "sources": []}
        references = ""
        if evidence:
            references = "\n\n## Source passages\n" + "\n".join(
                f"- [{item['id']}] [[{item['path'].removesuffix('.md')}]] (lines {item['start_line']}-{item['end_line']})" for item in evidence)
        try:
            with target.open("x", encoding="utf-8") as file:
                file.write(f"# {safe_name}\n\n{body}{references}\n")
        except FileExistsError:
            return {"answer": f"A note named '{safe_name}' already exists, so I left it unchanged.", "sources": []}
        answer = f"Created the note '{safe_name}' in your Obsidian vault."
        return {"answer": answer, "sources": [str(target)], "evidence": evidence, "warnings": warnings}

    def save_note(self, title, body):
        """Save user-written Markdown as a new note without overwriting files."""
        destination, error = self._note_destination(title)
        if error:
            return error
        safe_name, target = destination
        if target.exists():
            return {
                "answer": f"A note named '{safe_name}' already exists, so I left it unchanged.",
                "sources": [],
            }

        content = body.strip()
        if not content:
            return {"answer": "Write some content for the note first.", "sources": []}

        try:
            with target.open("x", encoding="utf-8") as file:
                file.write(f"# {safe_name}\n\n{content}\n")
        except FileExistsError:
            return {"answer": f"A note named '{safe_name}' already exists, so I left it unchanged.", "sources": []}
        answer = f"Created the note '{safe_name}' in your Obsidian vault."
        self.memory.add("assistant", answer, [str(target)])
        return {"answer": answer, "sources": [str(target)]}

    def _note_destination(self, title):
        if self.vault_path is None:
            from nemo.core.config import load_settings

            configured_vault = load_settings().get("vault", {}).get("path", "")
            self.vault_path = Path(configured_vault) if configured_vault else None

        if self.vault_path is None or not self.vault_path.is_dir():
            return None, {
                "answer": f"I couldn't find the configured Obsidian vault: {self.vault_path or '(not selected)'}",
                "sources": [],
            }

        safe_name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "-", title).strip(" .")
        if re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", safe_name, re.IGNORECASE):
            safe_name = f"_{safe_name}"
        safe_name = safe_name[:180].rstrip(" .")
        if not safe_name:
            return None, {"answer": "Please give the new note a title.", "sources": []}

        return (safe_name, self.vault_path / f"{safe_name}.md"), None
