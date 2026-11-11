from pathlib import Path
import re
import yaml


class MarkdownParser:

    def __init__(self, file):
        self.file = Path(file)

    def read(self):
        return self.file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    def parse(self):

        text = self.read()

        words = len(text.split())

        headings = []

        for line in text.splitlines():
            if line.startswith("#"):
                headings.append(line.lstrip("# ").strip())

        tags = re.findall(r"#([\w/-]+)", text)

        links = re.findall(r"\[\[(.*?)\]\]", text)

        metadata = {}
        if text.startswith("---\n") or text.startswith("---\r\n"):
            parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
            if len(parts) >= 3:
                try:
                    value = yaml.safe_load(parts[1])
                    metadata = value if isinstance(value, dict) else {}
                except yaml.YAMLError:
                    pass
        aliases = metadata.get("aliases", metadata.get("alias", []))
        if isinstance(aliases, str):
            aliases = [aliases]
        aliases = [item for item in aliases if isinstance(item, str)] if isinstance(aliases, list) else []
        extra_tags = metadata.get("tags", [])
        if isinstance(extra_tags, str):
            extra_tags = extra_tags.split()
        if isinstance(extra_tags, list):
            tags = sorted(set(tags) | {item for item in extra_tags if isinstance(item, str)})

        reading_time = max(1, words // 200)

        return {
            "title": self.file.stem,
            "aliases": aliases,
            "text": text,
            "word_count": words,
            "headings": headings,
            "tags": tags,
            "links": links,
            "reading_time": reading_time
        }

if __name__ == "__main__":
    test_file = r"D:\Obsidian\The Legend Of The Archangel\Abilities\Bolt of Wicked Wrath.md"

    parser = MarkdownParser(test_file)

    print(parser.parse())
