from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable

from stockfeet.path import PATH_STAGES, PathStage, path_complete


# Duolingo-ish learning path palette (green trail, not purple).
PATH_BG = "#122018"
DONE = "#58cc02"
DONE_RING = "#89e219"
CURRENT = "#ffc800"
CURRENT_RING = "#ffde7a"
AHEAD = "#3a4540"
AHEAD_FILL = "#2a3330"
SKIPPED = "#7a8f7a"
LABEL = "#e8f5e9"
MUTED = "#8aa396"
CONNECTOR = "#2f4a3a"


class PathMapView(tk.Frame):
    """Scrollable zigzag lesson path (Duolingo-style nodes)."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_select: Callable[[int], None],
        width: int = 300,
    ) -> None:
        super().__init__(master, background=PATH_BG)
        self.on_select = on_select
        self._stage_index = 0
        self._solved = 0
        self._skipped: set[str] = set()
        self._node_hits: list[tuple[int, float, float, float]] = []  # idx, cx, cy, r

        self.canvas = tk.Canvas(
            self,
            width=width,
            background=PATH_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        scroll = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _bind_wheel(self, _event: tk.Event | None = None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event: tk.Event | None = None) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def set_state(self, stage_index: int, solved: int, skipped_ids: list[str]) -> None:
        self._stage_index = stage_index
        self._solved = solved
        self._skipped = set(skipped_ids)
        self.redraw()
        self._scroll_to_current()

    def _scroll_to_current(self) -> None:
        if not self._node_hits:
            return
        cur = min(self._stage_index, len(PATH_STAGES) - 1)
        for idx, _cx, cy, _r in self._node_hits:
            if idx == cur:
                height = float(self.canvas["scrollregion"].split()[3]) if self.canvas["scrollregion"] else 1
                if height <= 1:
                    return
                frac = max(0.0, (cy - 120) / height)
                self.canvas.yview_moveto(frac)
                return

    def redraw(self) -> None:
        self.canvas.delete("all")
        self._node_hits.clear()
        w = max(int(self.canvas.winfo_width()), 280)
        n = len(PATH_STAGES)
        row_h = 108
        top = 36
        bottom_pad = 48
        height = top + n * row_h + bottom_pad
        self.canvas.configure(scrollregion=(0, 0, w, height))

        # Soft ground strip
        self.canvas.create_rectangle(0, 0, w, height, fill=PATH_BG, outline="")

        centers: list[tuple[float, float]] = []
        for i in range(n):
            # Zigzag like Duolingo units
            side = 1 if (i % 2 == 0) else -1
            cx = w * 0.5 + side * (w * 0.22)
            cy = top + i * row_h + 40
            centers.append((cx, cy))

        # Connectors behind nodes
        for i in range(n - 1):
            x1, y1 = centers[i]
            x2, y2 = centers[i + 1]
            color = DONE if i < self._stage_index else CONNECTOR
            width_line = 10 if i < self._stage_index else 7
            self.canvas.create_line(
                x1, y1, x2, y2, fill=color, width=width_line, capstyle=tk.ROUND, smooth=True
            )

        for i, stage in enumerate(PATH_STAGES):
            cx, cy = centers[i]
            self._draw_node(i, stage, cx, cy)

        if path_complete(self._stage_index):
            self.canvas.create_text(
                w / 2,
                top + n * row_h + 8,
                text="🏆 Path complete!",
                fill=CURRENT,
                font=("Segoe UI", 12, "bold"),
            )

    def _draw_node(self, index: int, stage: PathStage, cx: float, cy: float) -> None:
        r = 34
        skipped = stage.id in self._skipped and index >= self._stage_index
        if index < self._stage_index:
            fill, ring, label_fg = DONE, DONE_RING, "#0d1f0d"
            badge = "✓"
        elif index == self._stage_index and not path_complete(self._stage_index):
            fill, ring, label_fg = CURRENT, CURRENT_RING, "#3a2a00"
            badge = stage.icon
            self._draw_progress_ring(cx, cy, r + 8, self._solved / max(1, stage.needed))
        else:
            fill, ring, label_fg = AHEAD_FILL, AHEAD, MUTED
            badge = stage.icon
            if stage.id in self._skipped:
                fill, ring = "#3d4a3d", SKIPPED

        # Soft shadow
        self.canvas.create_oval(cx - r + 2, cy - r + 5, cx + r + 2, cy + r + 5, fill="#0a1410", outline="")
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=ring, width=4)
        self.canvas.create_text(cx, cy, text=badge, fill=label_fg, font=("Segoe UI", 16, "bold"))

        # Label under / beside
        side = 1 if (index % 2 == 0) else -1
        lx = cx + side * (r + 58)
        anchor = "w" if side > 0 else "e"
        title = stage.name
        if index == self._stage_index and not path_complete(self._stage_index):
            title = f"▶ {stage.name}"
        elif index < self._stage_index:
            title = f"{stage.name}"
        elif stage.id in self._skipped:
            title = f"{stage.name} (skipped)"

        self.canvas.create_text(
            lx,
            cy - 8,
            text=title,
            fill=LABEL if index <= self._stage_index else MUTED,
            font=("Segoe UI", 10, "bold"),
            anchor=anchor,
        )
        self.canvas.create_text(
            lx,
            cy + 10,
            text=f"~{stage.rating} · {stage.needed} puzzles",
            fill=MUTED,
            font=("Segoe UI", 8),
            anchor=anchor,
        )

        self._node_hits.append((index, cx, cy, r + 6))

    def _draw_progress_ring(self, cx: float, cy: float, radius: float, frac: float) -> None:
        frac = max(0.0, min(1.0, frac))
        # Full dim track
        self.canvas.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            outline="#5a5040",
            width=5,
        )
        if frac <= 0:
            return
        # Approximate arc with many small wedges via create_arc
        extent = -360 * frac  # tk arcs go counter-clockwise with negative for clock feel
        self.canvas.create_arc(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            start=90,
            extent=extent,
            style=tk.ARC,
            outline=CURRENT_RING,
            width=5,
        )

    def _on_click(self, event: tk.Event) -> None:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        for idx, cx, cy, r in self._node_hits:
            if math.hypot(x - cx, y - cy) <= r:
                self.on_select(idx)
                return
