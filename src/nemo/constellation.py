"""Interactive constellation view for linked notes in an Obsidian vault."""

from math import cos, pi, sin
import random
import time
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
STAR_DUST = ("#263743", "#354652", "#465660", "#5f7075")
STAR_GLOW = ("#5b543f", "#8b7546", "#c5a75e", "#f1d894")
SEA_GLOW = ("#365b5a", "#4d817b", "#72b7aa", "#b3e4d7")
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
        self.window.protocol("WM_DELETE_WINDOW", self._close)
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)
        self._twinkles = []
        self._pulse_edges = []
        self._animation_frame = 0
        self._animation_after = None

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
        self.canvas.bind("<Control-MouseWheel>", self._zoom_from_wheel)
        self.canvas.bind("<ButtonPress-2>", self._start_pan)
        self.canvas.bind("<B2-Motion>", self._pan)
        self.canvas.bind("<ButtonRelease-2>", self._end_pan)
        self.canvas.bind("<Enter>", lambda _event: self.canvas.focus_set())
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        self.hint_var = tk.StringVar()
        footer = ttk.Frame(self.window, padding=(20, 2, 20, 14))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.hint_var, style="Muted.TLabel", wraplength=390, justify="left").pack(side="left")
        zoom_controls = ttk.Frame(footer)
        zoom_controls.pack(side="right", padx=(10, 10))
        ttk.Label(zoom_controls, text="Zoom", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        ttk.Button(zoom_controls, text="−", width=3, command=lambda: self._change_zoom(0.85)).pack(side="left")
        self.zoom_var = tk.StringVar(value="100%")
        ttk.Label(zoom_controls, textvariable=self.zoom_var, style="Muted.TLabel", width=5, anchor="center").pack(side="left", padx=3)
        ttk.Button(zoom_controls, text="+", width=3, command=lambda: self._change_zoom(1.18)).pack(side="left")
        ttk.Button(zoom_controls, text="Reset", command=self._reset_zoom).pack(side="left", padx=(5, 0))
        self.zoom_level = 1.0
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
        self._twinkles = []
        self._pulse_edges = []
        self._layout_dimensions(levels)
        self.canvas.configure(scrollregion=(0, 0, self._world_width, self._world_height))
        self._draw_starfield()

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
            if source == center or target == center:
                halo = self.canvas.create_oval(
                    start_x - 5, start_y - 5, start_x + 5, start_y + 5,
                    fill="", outline="#8e805a", width=2,
                )
                spark = self.canvas.create_oval(
                    start_x - 2, start_y - 2, start_x + 2, start_y + 2,
                    fill="#f1d894", outline="",
                )
                phase = (len(self._pulse_edges) * 0.618) % 1
                self._pulse_edges.append((halo, spark, start_x, start_y, end_x, end_y, phase))

        for title, level in levels.items():
            x, y = self._positions[title]
            color = ACCENT if level == 0 else SEA_GLASS if level == 1 else OUTER_STAR
            outline = "#f1d894" if level == 0 else "#a4d2c8" if level == 1 else "#78909a"
            tag = f"star-{len(self.canvas.find_all())}"
            halo_color = STAR_GLOW if level == 0 else SEA_GLOW
            halo = self.canvas.create_oval(
                x - 24, y - 24, x + 24, y + 24,
                fill="", outline=halo_color[0], width=2 if level == 0 else 1,
                tags=(tag,),
            )
            self._twinkles.append((halo, level * 0.9, halo_color, "outline"))
            self.canvas.create_oval(
                x - 19, y - 19, x + 19, y + 19,
                fill="", outline="#65716d" if level == 2 else "#7e8d81", width=1,
                tags=(tag,),
            )
            self.canvas.create_polygon(
                *self._star_points(x, y, 17 if level == 0 else 14, 5 if level == 0 else 4),
                fill=color,
                outline=outline,
                width=1.5,
                tags=(tag,),
            )
            self.canvas.create_oval(
                x - 3, y - 3, x + 3, y + 3,
                fill="#fff2c5" if level == 0 else "#d9fff1",
                outline="",
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
        self._apply_canvas_zoom()
        self.hint_var.set(
            f"{len(levels) - 1} linked notes shown · click a star to recenter · middle-drag to pan · Ctrl+scroll to zoom"
            + " · Open note opens the center in Obsidian"
            + (" · map limited to the closest 120 notes" if truncated else "")
        )
        self._schedule_animation()

    def _draw_starfield(self):
        rng = random.Random(73)
        area = self._world_width * self._world_height
        star_count = max(90, min(260, area // 6500))
        for _ in range(star_count):
            x = rng.uniform(8, self._world_width - 8)
            y = rng.uniform(8, self._world_height - 8)
            radius = rng.choice((0.8, 1.0, 1.2, 1.5))
            color = rng.choice(STAR_DUST[:3])
            self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=color, outline="", tags=("star-dust",),
            )

        for _ in range(max(12, star_count // 12)):
            x = rng.uniform(18, self._world_width - 18)
            y = rng.uniform(18, self._world_height - 18)
            radius = rng.choice((1.3, 1.7, 2.1))
            dot = self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=STAR_DUST[1], outline="", tags=("twinkle",),
            )
            self._twinkles.append((dot, rng.uniform(0, 2 * pi), STAR_DUST, "fill"))
            if radius > 1.5:
                ray = self.canvas.create_line(
                    x - radius * 2, y, x + radius * 2, y,
                    fill=STAR_DUST[0], width=1, tags=("twinkle",),
                )
                self._twinkles.append((ray, rng.uniform(0, 2 * pi), STAR_DUST, "fill"))

    @staticmethod
    def _star_points(x, y, outer_radius, inner_radius, points=8):
        coordinates = []
        for index in range(points * 2):
            angle = -pi / 2 + index * pi / points
            radius = outer_radius if index % 2 == 0 else inner_radius
            coordinates.extend((x + cos(angle) * radius, y + sin(angle) * radius))
        return coordinates

    def _schedule_animation(self):
        if self._animation_after is None and self.window.winfo_exists():
            self._animation_after = self.window.after(100, self._animate)

    def _animate(self):
        self._animation_after = None
        if not self.window.winfo_exists():
            return
        now = time.monotonic()
        for item, phase, palette, option in self._twinkles:
            shimmer = (sin(now * 1.35 + phase) + 1) / 2
            shade = min(len(palette) - 1, int(shimmer * len(palette)))
            try:
                self.canvas.itemconfigure(item, **{option: palette[shade]})
            except tk.TclError:
                continue
        for halo, spark, x1, y1, x2, y2, phase in self._pulse_edges:
            progress = (now * 0.22 + phase) % 1
            x = (x1 + (x2 - x1) * progress) * self.zoom_level
            y = (y1 + (y2 - y1) * progress) * self.zoom_level
            self.canvas.coords(halo, x - 5, y - 5, x + 5, y + 5)
            self.canvas.coords(spark, x - 2, y - 2, x + 2, y + 2)
        self._animation_frame += 1
        self._schedule_animation()

    def _close(self):
        if self._animation_after is not None:
            self.window.after_cancel(self._animation_after)
            self._animation_after = None
        self.window.destroy()

    def _change_zoom(self, factor):
        self.zoom_level = min(2.0, max(0.55, self.zoom_level * factor))
        self.render()

    def _reset_zoom(self):
        self.zoom_level = 1.0
        self.render()

    def _zoom_from_wheel(self, event):
        self._change_zoom(1.12 if event.delta > 0 else 0.89)
        return "break"

    def _start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.configure(cursor="fleur")

    def _pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _end_pan(self, _event):
        self.canvas.configure(cursor="")

    def _apply_canvas_zoom(self):
        self.canvas.scale("all", 0, 0, self.zoom_level, self.zoom_level)
        bbox = self.canvas.bbox("all")
        width = max(self.canvas.winfo_width(), int(self._world_width * self.zoom_level))
        height = max(self.canvas.winfo_height(), int(self._world_height * self.zoom_level))
        if bbox:
            width = max(width, bbox[2])
            height = max(height, bbox[3])
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self.zoom_var.set(f"{round(self.zoom_level * 100)}%")
        self._scroll_width = width
        self._scroll_height = height
        self._center_map_view()
        self.canvas.after(80, self._center_map_view)

    def _center_map_view(self):
        if not self.canvas.winfo_exists():
            return
        width = getattr(self, "_scroll_width", self._world_width)
        height = getattr(self, "_scroll_height", self._world_height)
        center_x = self._center_x * self.zoom_level
        center_y = self._center_y * self.zoom_level
        self.canvas.xview_moveto(max(0, (center_x - self.canvas.winfo_width() / 2) / width))
        self.canvas.yview_moveto(max(0, (center_y - self.canvas.winfo_height() / 2) / height))

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

