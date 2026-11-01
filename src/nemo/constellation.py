"""Interactive constellation view for linked notes in an Obsidian vault."""

from math import cos, pi, sin
import tkinter as tk
from tkinter import ttk


BACKGROUND = "#101923"
SURFACE = "#182633"
TEXT = "#f1eee4"
MUTED = "#9aa9ad"
ACCENT = "#d6b46a"
SEA_GLASS = "#76b8ad"
OUTER_STAR = "#46636d"
EDGE = "#354650"
MAX_VISIBLE_NOTES = 120
NOTES_PER_RING = 18


class ConstellationWindow:
    def __init__(self, parent, index, open_note):
        self.index = index
        self.open_note = open_note
        self.note_titles = sorted(
            {note.get("title", key) for key, note in index.items()},
            key=str.casefold,
        )
        self.title_lookup = {title.casefold(): title for title in self.note_titles}
        self.edges, self.neighbors = self._build_edges()

        self.window = tk.Toplevel(parent)
        self.window.title("N.E.M.O — Your Constellation")
        self.window.geometry("900x650")
        self.window.minsize(680, 500)
        self.window.configure(bg=BACKGROUND)
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)

        header = ttk.Frame(self.window, padding=(20, 16, 20, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="YOUR CONSTELLATION",
            style="Kicker.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Follow the links between notes",
            style="Title.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        controls = ttk.Frame(header)
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Label(controls, text="Center on", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self.center_var = tk.StringVar(value=self._starting_note())
        self.center_picker = ttk.Combobox(
            controls,
            textvariable=self.center_var,
            values=self.note_titles,
            width=32,
        )
        self.center_picker.pack(side="left", padx=(0, 12))
        self.center_picker.bind("<<ComboboxSelected>>", lambda _event: self.render())
        self.center_picker.bind("<Return>", self._center_from_entry)

        ttk.Label(controls, text="Reach", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self.depth_var = tk.StringVar(value="2 links")
        depth_picker = ttk.Combobox(
            controls,
            textvariable=self.depth_var,
            values=("1 link", "2 links"),
            width=9,
            state="readonly",
        )
        depth_picker.pack(side="left", padx=(0, 12))
        depth_picker.bind("<<ComboboxSelected>>", lambda _event: self.render())
        ttk.Button(controls, text="Open note", command=self._open_center).pack(side="right")

        canvas_frame = ttk.Frame(self.window, style="Surface.TFrame", padding=1)
        canvas_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 8))
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            canvas_frame,
            bg=SURFACE,
            highlightthickness=0,
            xscrollincrement=40,
            yscrollincrement=40,
        )
        x_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        self.hint_var = tk.StringVar()
        footer = ttk.Frame(self.window, padding=(20, 2, 20, 14))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.hint_var, style="Muted.TLabel").pack(side="left")
        self._add_legend(footer)
        self.render()

    def _starting_note(self):
        if not self.note_titles:
            return ""
        return max(self.note_titles, key=lambda title: len(self.neighbors.get(title, ())))

    def _build_edges(self):
        path_by_title = {
            note.get("title", key).casefold(): note.get("path", "").replace("\\", "/").casefold()
            for key, note in self.index.items()
        }
        edges = set()
        neighbors = {title: set() for title in self.note_titles}

        for key, note in self.index.items():
            source = note.get("title", key)
            if source not in neighbors:
                continue
            for raw_link in note.get("links", []):
                target = raw_link.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
                target_key = target.casefold().removesuffix(".md")
                target_title = self.title_lookup.get(target_key)
                if target_title is None:
                    target_title = self.title_lookup.get(target.rsplit("/", 1)[-1].casefold().removesuffix(".md"))
                if target_title is None:
                    normalized_path = target_key
                    target_title = next(
                        (title for title, indexed_path in path_by_title.items() if indexed_path.casefold().removesuffix(".md") == normalized_path),
                        None,
                    )
                    if target_title is not None:
                        target_title = self.title_lookup.get(target_title)
                if target_title is None or target_title == source:
                    continue
                edges.add((source, target_title))
                neighbors[source].add(target_title)
                neighbors[target_title].add(source)

        return edges, neighbors

    def _center_from_entry(self, _event):
        self.render()
        return "break"

    def _open_center(self):
        title = self._selected_title()
        if title:
            self.open_note(title)

    def _selected_title(self):
        typed = self.center_var.get().strip()
        return self.title_lookup.get(typed.casefold())

    def _add_legend(self, parent):
        legend = ttk.Frame(parent)
        legend.pack(side="right")
        self._legend_dot(legend, ACCENT, "Center")
        self._legend_dot(legend, SEA_GLASS, "Linked")
        self._legend_dot(legend, OUTER_STAR, "Further")

    @staticmethod
    def _legend_dot(parent, color, label):
        dot = tk.Canvas(parent, width=12, height=12, bg=BACKGROUND, highlightthickness=0)
        dot.create_oval(2, 2, 10, 10, fill=color, outline=color)
        dot.pack(side="left", padx=(10, 4))
        ttk.Label(parent, text=label, style="Muted.TLabel").pack(side="left")

    def _visible_levels(self, center, depth):
        levels = {center: 0}
        frontier = [center]
        truncated = False
        for distance in range(1, depth + 1):
            next_frontier = sorted(
                {
                    neighbor
                    for note in frontier
                    for neighbor in self.neighbors.get(note, ())
                    if neighbor not in levels
                },
                key=str.casefold,
            )
            remaining = MAX_VISIBLE_NOTES - len(levels)
            if len(next_frontier) > remaining:
                next_frontier = next_frontier[:remaining]
                truncated = True
            for note in next_frontier:
                levels[note] = distance
            frontier = next_frontier
            if not frontier or len(levels) >= MAX_VISIBLE_NOTES:
                if distance < depth and frontier:
                    truncated = True
                break
        return levels, truncated

    def _layout_nodes(self, levels):
        ring_titles = {
            level: sorted((title for title, value in levels.items() if value == level), key=str.casefold)
            for level in range(1, max(levels.values(), default=0) + 1)
        }
        radius = 230
        for level, titles in ring_titles.items():
            bands = [titles[i:i + NOTES_PER_RING] for i in range(0, len(titles), NOTES_PER_RING)]
            for band_index, band in enumerate(bands):
                ring_radius = radius + band_index * 210
                for index, title in enumerate(band):
                    angle = (2 * pi * index / len(band)) - pi / 2 + (band_index % 2) * pi / len(band)
                    self._positions[title] = (
                        self._center_x + cos(angle) * ring_radius,
                        self._center_y + sin(angle) * ring_radius,
                    )
            if bands:
                radius += len(bands) * 210 + 180
        return radius

    def render(self):
        if not self.note_titles:
            return
        center = self._selected_title()
        if not center:
            self.hint_var.set("Choose a note from your vault to center the map.")
            return

        depth = 1 if self.depth_var.get().startswith("1") else 2
        levels, truncated = self._visible_levels(center, depth)
        self.canvas.delete("all")
        self._layout_dimensions(levels)
        self.canvas.configure(scrollregion=(0, 0, self._world_width, self._world_height))

        for source, target in sorted(self.edges, key=lambda edge: (edge[0].casefold(), edge[1].casefold())):
            if source not in levels or target not in levels:
                continue
            x1, y1 = self._positions[source]
            x2, y2 = self._positions[target]
            dx, dy = x2 - x1, y2 - y1
            length = max((dx * dx + dy * dy) ** 0.5, 1)
            start_x = x1 + dx * 18 / length
            start_y = y1 + dy * 18 / length
            end_x = x2 - dx * 22 / length
            end_y = y2 - dy * 22 / length
            color = "#8f805d" if source == center or target == center else EDGE
            self.canvas.create_line(
                start_x,
                start_y,
                end_x,
                end_y,
                fill=color,
                width=2 if source == center or target == center else 1,
                arrow=tk.LAST,
                arrowshape=(8, 10, 4),
            )

        for title, level in levels.items():
            x, y = self._positions[title]
            color = ACCENT if level == 0 else SEA_GLASS if level == 1 else OUTER_STAR
            outline = "#f1d894" if level == 0 else "#a4d2c8" if level == 1 else "#78909a"
            tag = f"star-{len(self.canvas.find_all())}"
            self.canvas.create_oval(
                x - 17,
                y - 17,
                x + 17,
                y + 17,
                fill=color,
                outline=outline,
                width=2,
                tags=(tag,),
            )
            self.canvas.create_text(
                x,
                y + 29,
                text=self._short_title(title),
                fill=TEXT,
                font=("Segoe UI", 9, "bold" if level == 0 else "normal"),
                tags=(tag,),
            )
            self.canvas.tag_bind(tag, "<Button-1>", lambda _event, note=title: self._select_note(note))
            self.canvas.tag_bind(tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

        self.canvas.update_idletasks()
        x_fraction = (self._center_x - self.canvas.winfo_width() / 2) / self._world_width
        y_fraction = (self._center_y - self.canvas.winfo_height() / 2) / self._world_height
        self.canvas.xview_moveto(max(0, x_fraction))
        self.canvas.yview_moveto(max(0, y_fraction))
        self.hint_var.set(
            f"{len(levels) - 1} linked notes shown · click a star to recenter, then Open note to open it in Obsidian"
            + (" · map limited to the closest 120 notes" if truncated else "")
        )

    def _layout_dimensions(self, levels):
        self._positions = {}
        viewport_width = 820
        viewport_height = 520
        self._world_width = viewport_width
        self._world_height = viewport_height
        self._center_x = viewport_width / 2
        self._center_y = viewport_height / 2
        self._positions = {title: (self._center_x, self._center_y) for title, level in levels.items() if level == 0}

        radius = self._layout_nodes(levels)
        self._world_width = max(viewport_width, radius * 2)
        self._world_height = max(viewport_height, radius * 2)
        shift_x = (self._world_width - viewport_width) / 2
        shift_y = (self._world_height - viewport_height) / 2
        self._positions = {title: (x + shift_x, y + shift_y) for title, (x, y) in self._positions.items()}
        self._center_x += shift_x
        self._center_y += shift_y
        return radius

    def _select_note(self, title):
        self.center_var.set(title)
        self.render()

    @staticmethod
    def _short_title(title):
        return title if len(title) <= 22 else f"{title[:19]}…"
