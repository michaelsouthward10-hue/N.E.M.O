# N.E.M.O

**Narrative Engine for Mythological Organisation** is a Windows desktop companion for an Obsidian vault. N.E.M.O. searches your notes, answers questions with a local Ollama model, follows `[[wikilinks]]` to find relationships, and creates Markdown notes in your vault.

The 1.0 release is a usable desktop application. The source remains available so the project can continue to grow.

## Get started

1. Install [Ollama for Windows](https://ollama.com/download/windows), start it, and download the configured model. The default is `qwen3:8b`.
2. Download `NEMO-Windows-Portable.zip` from the [GitHub Releases page](https://github.com/michaelsouthward10-hue/N.E.M.O/releases), extract it, and open `NEMO.exe`. The Windows app and its shortcuts use the N.E.M.O. icon.
3. In N.E.M.O., choose your Obsidian vault and select **Reindex**. Reindex again after editing notes.
4. Ask questions, ask how two note topics are connected, or choose **New note** to write and save your own note. To have N.E.M.O. draft one from your vault, ask in chat with `new note: <title>`.

The installer does not require administrator access. The Ollama model is downloaded separately and is not bundled with N.E.M.O.

## What it does

- Searches indexed Markdown notes and shows the notes used as sources.
- Answers from matching note content with a locally running Ollama model.
- Finds paths between notes using Obsidian `[[wikilinks]]`.
- Drafts a Markdown note using relevant indexed notes, without overwriting an existing file.
- Keeps settings in `%APPDATA%\NEMO` and the private note index in `%LOCALAPPDATA%\NEMO`.
- Checks GitHub for a newer release and opens its download page when you choose to update.

When you ask a question or request an AI-drafted note, the relevant vault text and prompt are sent to your configured Ollama endpoint. With the default setup, Ollama runs on your own computer. Notes written with **New note** are saved directly to the vault and are not sent to Ollama. Reindexing parses Markdown locally and does not make Ollama requests. N.E.M.O. contacts GitHub to check for updates; it does not upload your vault or index. The index contains copies of your Markdown text and short local previews, so it is stored outside the application folder and excluded from this repository and release packages.

## Requirements and help

- Windows 10 or later (64-bit)
- Ollama running at the configured endpoint, with the selected model downloaded
- An Obsidian vault containing Markdown notes

If N.E.M.O. reports that Ollama is offline, start Ollama and check that its endpoint in `%APPDATA%\NEMO\settings.yaml` is reachable. If it reports a missing model, download the model named in that same settings file. If answers do not reflect recent edits, choose **Reindex**.

For bugs and feature ideas, open an issue in the [N.E.M.O. repository](https://github.com/michaelsouthward10-hue/N.E.M.O/issues). See [CHANGELOG.md](CHANGELOG.md) for release details and [ROADMAP.md](ROADMAP.md) for future project direction.

## Build from source

To build the Windows desktop app, install Python 3.10 or later and run `scripts\build_windows.ps1` from the project folder. The script creates `.nemo-release\NEMO` and `.nemo-release\NEMO-Windows-Portable.zip`. If Inno Setup is installed, it also creates a setup program in `.nemo-release\installer`.

The optional Windows packaging dependency is listed in `requirements-build.txt`; runtime dependencies are listed in `requirements.txt`. Build on Windows to produce the Windows application.
