from pathlib import Path
import re


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

        reading_time = max(1, words // 200)

        return {
            "title": self.file.stem,
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