# Changelog

## 1.0.1 — Chat improvements

- Added a dedicated bottom chat bar that stays visible in compact and maximized windows.
- Let the assistant answer general questions when no matching vault notes are found.

## 1.0.0 — Desktop release

N.E.M.O. is now delivered as a Windows desktop application with a portable download and optional installer.

- Added a chat window for asking questions about an Obsidian vault.
- Added vault selection and reindexing from the app.
- Added relationship answers that follow Obsidian wikilinks.
- Added note drafting that writes Markdown into the selected vault and preserves existing files.
- Added a connection check for Ollama and the configured model.
- Added GitHub release update checks.
- Made reindexing local and showed note-by-note progress instead of waiting for a model request for each note.
- Moved application settings and the private search index to the user's Windows profile when running the packaged app.
- Kept the vault index out of Git and the distributable application.

## Earlier releases

Versions 0.1 through 0.9.1 developed the project structure, vault indexing, local model integration, search, conversation context, and the relationship graph. See the repository history for those changes.
