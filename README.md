# N.E.M.O

**Narrative Engine for Mythological Organisation** is a Windows desktop companion for an Obsidian vault. N.E.M.O. searches your notes, answers questions with a local Ollama model, follows `[[wikilinks]]` to find relationships, and creates Markdown notes in your vault.

N.E.M.O. is a Windows desktop application. The source remains available so the project can continue to grow.

## Get started

1. Install [Ollama for Windows](https://ollama.com/download/windows), start it, and download the configured model. The default is `qwen3:8b`.
2. Download `NEMO-Windows-Portable.zip` from the [GitHub Releases page](https://github.com/michaelsouthward10-hue/N.E.M.O/releases), extract it, and open `NEMO.exe`. The Windows app and its shortcuts use the N.E.M.O. icon.
3. In N.E.M.O., choose your Obsidian vault and select **Reindex**. A progress bar shows the scanned note count, and **Reindex complete** appears when the index has been saved. Later note changes are indexed automatically by default; Reindex forces a full refresh.
4. Ask questions, use an Oracle mode to explore your notes, or choose **New note** to write and save your own note. To have N.E.M.O. draft one from your vault, ask in chat with `new note: <title>`.

The installer does not require administrator access. The Ollama model is downloaded separately and is not bundled with N.E.M.O.

## What it does

- Searches indexed Markdown notes and opens answer sources in Obsidian when clicked.
- Answers from ranked passages across notes with a locally running Ollama model, resolves follow-up questions, and expands search terms to find related wording.
- Follows relevant outgoing links and backlinks and gathers more than three notes when useful, within the model's context budget.
- Shows numbered source passages with note paths and line ranges. Click a citation or source link to inspect the saved excerpt and open the current note in Obsidian.
- Saves named conversations locally, restores recent messages after restarting, and retrieves relevant older discussion. Use **Chat log** to search, browse, export or delete conversations.
- Summarizes older discussion while retaining every original message, and offers user-pinned facts, decisions and ideas.
- Streams replies and provides a **Stop** button. Interrupted replies stay marked as incomplete and are excluded from later AI recall.
- Detects note additions, edits, renames and deletions automatically, reuses unchanged notes, and saves a separate index for each vault. Notes with the same filename remain distinct.
- Finds paths between notes using Obsidian `[[wikilinks]]`.
- Explores linked notes in a constellation map and opens selected notes in Obsidian.
- Offers Oracle modes to find connections, summarize a topic, and develop an idea with vault context.
- Drafts a Markdown note using relevant indexed notes, without overwriting an existing file.
- Keeps settings in `%APPDATA%\NEMO` and the private note index in `%LOCALAPPDATA%\NEMO`.
- Checks GitHub for a newer release and opens its download page when you choose to update.

When you ask a question, summarize a topic, develop an idea, or request an AI-drafted note, relevant vault text, selected conversation excerpts, summaries, pinned context and your prompt are sent to your configured Ollama endpoint. Search planning and conversation summaries also use that endpoint. If you enable embedding search, note passages and saved discussion are sent there to create local search vectors. The **Find connections** mode and constellation map use the local index without making model requests. With the default setup, Ollama runs on your own computer. Notes written with **New note** are saved directly to the vault and are not sent to Ollama. Manual and automatic note indexing parse Markdown locally without model requests. N.E.M.O. contacts GitHub to check for updates; it does not upload your vault, chat logs or indexes. Private data is stored outside the packaged application and excluded from this repository and release packages.

## Requirements and help

- Windows 10 or later (64-bit)
- Ollama running at the configured endpoint, with the selected model downloaded
- An Obsidian vault containing Markdown notes

If N.E.M.O. reports that Ollama is offline, open Ollama and retry. Choose **More → AI and indexing settings** to change the endpoint, conversation model, context size, automatic indexing or optional embedding model. Download any selected model in Ollama separately. If answers do not reflect recent edits, choose **Reindex**. Settings are also stored in `%APPDATA%\NEMO\settings.yaml`.

For bugs and feature ideas, open an issue in the [N.E.M.O. repository](https://github.com/michaelsouthward10-hue/N.E.M.O/issues). See [CHANGELOG.md](CHANGELOG.md) for release details and [ROADMAP.md](ROADMAP.md) for future project direction.

## Build from source

To build the Windows desktop app, install Python 3.10 or later and run `scripts\build_windows.ps1` from the project folder. The script creates `.nemo-release\NEMO` and `.nemo-release\NEMO-Windows-Portable.zip`. If Inno Setup is installed, it also creates a setup program in `.nemo-release\installer`.

The optional Windows packaging dependency is listed in `requirements-build.txt`; runtime dependencies are listed in `requirements.txt`. Build on Windows to produce the Windows application.

## Saved conversations

Chat logs have no message-count cap and are stored outside the vault in the application data directory, under `conversations` (normally `%LOCALAPPDATA%\NEMO\conversations` for the packaged app; `data/conversations` when running from this source checkout). Each vault path has its own SQLite log. Moving or renaming a vault starts a separate history. Earlier conversations from versions without saved history cannot be recovered.

Use **New chat** and the conversation picker to keep separate discussions. **Rename** gives a conversation a meaningful name. Chat logs from version 1.0.8 migrate into the main conversation automatically.

For each answer, N.E.M.O searches saved discussion with topic words and model-generated related terms, combines older exchanges with recent turns, and includes the conversation's summary and pinned context. Optional embedding search can retrieve paraphrases with no exact word overlap. By default recall stays within the current conversation. Enable **Allow recall from other conversations in this vault** in AI settings to retrieve other chats, labeled by conversation name. Vaults always remain separate.

Choose **Pinned** to record your own facts, decisions or ideas. Pins are user assertions, not automatically verified lore; current notes and new corrections may conflict with older decisions. Long pin lists may exceed the selected context size, in which case the answer reports omitted items. Summaries are AI-generated and may omit details; original messages remain searchable. The model has a finite context window, so each request contains selected excerpts rather than the entire archive. Retrieval and citations help review answers but do not guarantee every claim is correct.

The desktop restores the latest 40 messages. **Chat log** pages through the full archive, searches the current conversation or all conversations in this vault, opens a selected conversation, and exports the active chat as Markdown or JSON. Export includes source snapshots and pinned context. Deleting the active conversation removes its messages, summary and pins; export first if you want a copy. Timestamps in chat history and exports are UTC. Logs have no automatic retention limit.

## Search and index storage

Each vault has its own index under `vaults/<vault-id>/index.json` in the application data directory. Indexes use vault-relative paths, so identical filenames in different folders do not overwrite each other. Automatic indexing checks for changes about every ten seconds by default and only reparses changed files. A canceled scan or a failed save leaves the previous index intact; unreadable entries retain their last readable version for retry. If automatic indexing encounters an unrecoverable error, click **Reindex** to rebuild and resume it.

Upgrading from 1.0.8 rebuilds the previous shared note index into a separate index for the selected vault. The original shared file is left alone. Moving a vault gives it a new index and history identity.

Embedding search is optional. Set an embedding model you have already downloaded in Ollama, such as an embedding-capable model of your choice, in AI settings. No model is downloaded automatically. The first search builds a local cache and can take longer; subsequent searches reuse cached vectors. If the embedding model is unavailable, N.E.M.O reports that it fell back to word ranking and model-assisted question expansion. Word ranking, follow-up resolution, summaries and pinned context work without a separate embedding model.
