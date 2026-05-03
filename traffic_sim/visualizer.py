"""
Visualizer: produces animated GIF/MP4 and statistics charts.

Improvement #9 — cleaner visualisation:
  • Road arrows are coloured by utilisation (blue → yellow → red) and
    their line-width grows with queue length — congestion is immediately
    visible without reading any numbers.
  • Road ID labels are removed (too cluttered for 30 roads).
  • Each sink node shows a live absorbed-vehicle count.
  • Each source node shows its current waiting-queue depth.
  • Road arrow patches are updated in-place each frame (blit=True) for
    fast GIF rendering.
"""
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.cm as cm
from matplotlib.animation import FuncAnimation, PillowWriter, FFMpegWriter
import numpy as np


# Blue (empty) → Yellow (half) → Red (congested)
_UTIL_CMAP = cm.RdYlBu_r


def _util_color(util: float):
    """Return an RGBA colour for road utilisation in [0, 1]."""
    return _UTIL_CMAP(max(0.0, min(1.0, util)))


class Visualizer:
    def __init__(self, engine, node_positions: dict, node_types: dict,
                 dest_colors: dict, title: str = "Traffic Simulator"):
        self.engine = engine
        self.node_pos = node_positions
        self.node_types = node_types
        self.dest_colors = dest_colors
        self.title = title

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _road_endpoints(self, road):
        """Return ((x0,y0), (x1,y1), perp_x, perp_y) for a road."""
        x0, y0 = self.node_pos[road.start]
        x1, y1 = self.node_pos[road.end]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L == 0:
            return (x0, y0), (x1, y1), 0.0, 0.0
        px, py = -dy / L * 0.07, dx / L * 0.07
        return (x0, y0), (x1, y1), px, py

    def _vehicle_xy(self, v_info: dict):
        road = self.engine.roads.get(v_info["road"])
        if road is None or road.start not in self.node_pos or road.end not in self.node_pos:
            return None, None
        (x0, y0), (x1, y1), px, py = self._road_endpoints(road)
        p = v_info["progress"]
        x = x0 + (x1 - x0) * p + px
        y = y0 + (y1 - y0) * p + py
        if v_info.get("in_queue"):
            dx, dy = x1 - x0, y1 - y0
            L = math.hypot(dx, dy)
            if L > 0:
                qp = v_info.get("queue_pos", 0)
                x -= dx / L * 0.05 * qp
                y -= dy / L * 0.05 * qp
        return x, y

    # ------------------------------------------------------------------
    # Static background (nodes only — roads are dynamic)
    # ------------------------------------------------------------------

    def _draw_nodes(self, ax):
        for node_id, (x, y) in self.node_pos.items():
            ntype = self.node_types.get(node_id, "junction")
            if ntype == "source":
                marker, color, size, zo = "D", "#00ff88", 160, 5
            elif ntype == "sink":
                marker, color, size, zo = "s", "#ff4466", 160, 5
            else:
                marker, color, size, zo = "o", "#d0d0ff", 110, 5
            ax.scatter([x], [y], s=size, c=color, marker=marker,
                       zorder=zo, edgecolors="white", linewidths=0.8)
            ax.text(x, y + 0.13, node_id, fontsize=7, color="white",
                    ha="center", va="bottom", fontweight="bold", zorder=6,
                    path_effects=[pe.withStroke(linewidth=2, foreground="black")])

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def animate(self, output_path: str = "simulation.gif",
                fps: int = 8, skip: int = 1):
        frames = self.engine.frames[::skip]

        fig, (ax_net, ax_stats) = plt.subplots(
            1, 2, figsize=(15, 7),
            gridspec_kw={"width_ratios": [2, 1]}
        )
        fig.patch.set_facecolor("#0d0d1f")
        for ax in (ax_net, ax_stats):
            ax.set_facecolor("#1a1a2e")
            for spine in ax.spines.values():
                spine.set_color("#334466")

        # Network bounds
        all_x = [p[0] for p in self.node_pos.values()]
        all_y = [p[1] for p in self.node_pos.values()]
        pad = 0.45
        ax_net.set_xlim(min(all_x) - pad, max(all_x) + pad)
        ax_net.set_ylim(min(all_y) - pad, max(all_y) + pad)
        ax_net.set_aspect("equal")
        ax_net.tick_params(colors="#6688aa")
        ax_net.set_title(self.title, color="white", fontsize=11, fontweight="bold")

        # ── Road arrow patches (colour/width updated each frame) ──────
        road_patches = {}
        for road_id, road in self.engine.roads.items():
            if road.start not in self.node_pos or road.end not in self.node_pos:
                continue
            (x0, y0), (x1, y1), px, py = self._road_endpoints(road)
            ann = ax_net.annotate(
                "",
                xy=(x1 + px, y1 + py),
                xytext=(x0 + px, y0 + py),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color=_util_color(0.0),
                    lw=1.4,
                    mutation_scale=11,
                    alpha=0.55,
                ),
                annotation_clip=False,
                zorder=3,
            )
            road_patches[road_id] = ann.arrow_patch

        # ── Static nodes ──────────────────────────────────────────────
        self._draw_nodes(ax_net)

        # ── Per-sink absorbed count (updated each frame) ───────────────
        sink_texts = {}
        for sid in self.engine.sinks:
            if sid not in self.node_pos:
                continue
            x, y = self.node_pos[sid]
            txt = ax_net.text(
                x, y - 0.28, "↓0",
                fontsize=8, color="#ffaaaa", ha="center", va="top",
                fontweight="bold", zorder=7,
                path_effects=[pe.withStroke(linewidth=2, foreground="black")]
            )
            sink_texts[sid] = txt

        # ── Per-source waiting-queue count (updated each frame) ────────
        src_texts = {}
        for src_id, src in self.engine.sources.items():
            node_id = src.node_id
            if node_id not in self.node_pos:
                continue
            x, y = self.node_pos[node_id]
            txt = ax_net.text(
                x, y + 0.38, "q:0",
                fontsize=7, color="#aaffcc", ha="center", va="bottom",
                zorder=7,
                path_effects=[pe.withStroke(linewidth=1, foreground="black")]
            )
            src_texts[src_id] = txt

        # ── Vehicle scatter ───────────────────────────────────────────
        veh_scatter = ax_net.scatter([], [], s=26, zorder=10,
                                      linewidths=0.4, edgecolors="white")

        # ── Legend ───────────────────────────────────────────────────
        legend_patches = [
            mpatches.Patch(color="#00ff88", label="Source"),
            mpatches.Patch(color="#ff4466", label="Sink"),
            mpatches.Patch(color="#d0d0ff", label="Junction"),
        ]
        for label, col in self.dest_colors.items():
            legend_patches.append(mpatches.Patch(color=col, label=label))
        # Road utilisation key
        for util, lbl in ((0.0, "Road: empty"), (0.5, "Road: 50%"), (1.0, "Road: full")):
            legend_patches.append(
                mpatches.Patch(facecolor=_util_color(util),
                               edgecolor="white", linewidth=0.5, label=lbl)
            )
        ax_net.legend(handles=legend_patches, loc="lower left",
                      facecolor="#1a1a2e", edgecolor="#334466",
                      labelcolor="white", fontsize=6.5, ncol=1)

        # ── Stats panel ───────────────────────────────────────────────
        max_step = max(f["step"] for f in frames) if frames else 1
        ax_stats.set_xlim(0, max_step)
        q_max = max(max(self.engine._queue_per_step or [1]), 1) * 1.2
        ax_stats.set_ylim(0, q_max)
        ax_stats.set_xlabel("Time Step", color="#99aacc", fontsize=8)
        ax_stats.set_ylabel("Count", color="#99aacc", fontsize=8)
        ax_stats.tick_params(colors="#6688aa", labelsize=7)
        ax_stats.set_title("Live Statistics", color="white", fontsize=9)
        ax_stats.grid(alpha=0.2, color="#334466")

        queue_line, = ax_stats.plot([], [], color="#ffaa00", lw=1.5, label="Total Queue")
        absorb_line, = ax_stats.plot([], [], color="#00ccff", lw=1.5, label="Absorbed")
        waiting_line, = ax_stats.plot([], [], color="#88ff88", lw=1.0,
                                       linestyle="--", label="Src Waiting")
        ax_stats.legend(facecolor="#1a1a2e", edgecolor="#334466",
                        labelcolor="white", fontsize=7)

        step_text = ax_net.text(
            0.02, 0.97, "", transform=ax_net.transAxes,
            color="white", fontsize=8.5, va="top", fontfamily="monospace"
        )

        q_hist, a_hist, w_hist, s_hist = [], [], [], []

        def update(frame_idx):
            frame = frames[frame_idx]
            step = frame["step"]
            road_occ = frame.get("road_occupancy", frame.get("road_queues", {}))

            # Update road arrow colours / widths by utilisation
            for road_id, patch in road_patches.items():
                road = self.engine.roads.get(road_id)
                if road is None:
                    continue
                occ  = road_occ.get(road_id, 0)
                util = min(1.0, occ / max(road.capacity, 1))
                patch.set_color(_util_color(util))
                patch.set_linewidth(1.2 + util * 3.2)
                patch.set_alpha(0.45 + util * 0.55)

            # Update vehicle positions
            xs_v, ys_v, colors_v = [], [], []
            for v in frame["vehicles"]:
                x, y = self._vehicle_xy(v)
                if x is not None:
                    xs_v.append(x)
                    ys_v.append(y)
                    colors_v.append(v["color"])
            if xs_v:
                veh_scatter.set_offsets(np.column_stack([xs_v, ys_v]))
                veh_scatter.set_facecolor(colors_v)
            else:
                veh_scatter.set_offsets(np.empty((0, 2)))

            # Update per-sink counts
            per_sink = frame.get("per_sink_absorbed", {})
            for sid, txt in sink_texts.items():
                txt.set_text(f"↓{per_sink.get(sid, 0)}")

            # Update per-source waiting counts
            total_waiting = 0
            for src_id, txt in src_texts.items():
                src = self.engine.sources.get(src_id)
                wc = src.waiting_count if src else 0
                total_waiting += wc
                txt.set_text(f"q:{wc}")

            # Stats lines
            qi = min(step, len(self.engine._queue_per_step) - 1)
            q = self.engine._queue_per_step[qi] if self.engine._queue_per_step else 0
            a = frame["total_absorbed"]
            q_hist.append(q); a_hist.append(a)
            w_hist.append(total_waiting); s_hist.append(step)
            queue_line.set_data(s_hist, q_hist)
            absorb_line.set_data(s_hist, a_hist)
            waiting_line.set_data(s_hist, w_hist)
            ax_stats.set_ylim(0, max(q_hist + a_hist + w_hist + [1]) * 1.15)

            step_text.set_text(
                f"Step: {step:4d}  Active: {frame['active_count']:3d}  "
                f"Absorbed: {a:4d}  Waiting: {total_waiting:3d}"
            )
            return (*road_patches.values(), veh_scatter,
                    *sink_texts.values(), *src_texts.values(),
                    queue_line, absorb_line, waiting_line, step_text)

        anim = FuncAnimation(fig, update, frames=len(frames),
                              interval=1000 // fps, blit=True)
        plt.tight_layout()

        if output_path.endswith(".mp4"):
            try:
                anim.save(output_path, writer=FFMpegWriter(fps=fps))
            except Exception:
                gif_path = output_path.replace(".mp4", ".gif")
                print(f"ffmpeg unavailable, saving as {gif_path}")
                anim.save(gif_path, writer=PillowWriter(fps=fps))
                output_path = gif_path
        else:
            anim.save(output_path, writer=PillowWriter(fps=fps))

        plt.close(fig)
        print(f"Animation saved → {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Statistics figure
    # ------------------------------------------------------------------

    def plot_statistics(self, stats: dict, output_path: str = "statistics.png"):
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.patch.set_facecolor("#0d0d1f")
        fig.suptitle(f"{self.title} — Statistics", color="white",
                     fontsize=13, fontweight="bold")

        panel  = dict(facecolor="#1a1a2e")
        ticks  = dict(colors="#6688aa", labelsize=8)
        xlabel = dict(color="#99aacc", fontsize=9)

        steps = range(len(stats["throughput_per_step"]))

        ax = axes[0][0]
        ax.set(**panel); ax.tick_params(**ticks)
        ax.plot(steps, stats["throughput_per_step"], color="#00ccff", lw=1.2)
        ax.fill_between(steps, stats["throughput_per_step"], alpha=0.15, color="#00ccff")
        ax.set_title("Throughput (vehicles absorbed / step)", color="white", fontsize=9)
        ax.set_xlabel("Step", **xlabel); ax.grid(alpha=0.2, color="#334466")
        for sp in ax.spines.values(): sp.set_color("#334466")

        ax = axes[0][1]
        ax.set(**panel); ax.tick_params(**ticks)
        ax.plot(steps, stats["queue_per_step"], color="#ffaa00", lw=1.2)
        ax.fill_between(steps, stats["queue_per_step"], alpha=0.15, color="#ffaa00")
        ax.set_title("Total Queue Length (all roads)", color="white", fontsize=9)
        ax.set_xlabel("Step", **xlabel); ax.grid(alpha=0.2, color="#334466")
        for sp in ax.spines.values(): sp.set_color("#334466")

        # Per-junction bar chart (cleaner than per-road for 30 roads)
        ax = axes[1][0]
        ax.set(**panel); ax.tick_params(**ticks)
        jids   = list(stats["per_junction"].keys())
        jpassed = [stats["per_junction"][j]["vehicles_passed"] for j in jids]
        jways  = [stats["per_junction"][j]["ways"] for j in jids]
        colors = ["#5577ff" if w <= 3 else "#aa44ff" for w in jways]
        ax.bar(jids, jpassed, color=colors, edgecolor="#334466")
        ax.set_title("Vehicles forwarded per Junction", color="white", fontsize=9)
        ax.set_xlabel("Junction", **xlabel)
        for sp in ax.spines.values(): sp.set_color("#334466")
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)

        ax = axes[1][1]
        ax.set(**panel); ax.axis("off")
        gen  = stats.get("total_generated", stats["total_spawned"])
        wait = stats.get("vehicles_waiting", 0)
        summary = (
            f"Simulation Steps :  {stats['total_steps']}\n"
            f"Vehicles Generated: {gen}\n"
            f"Vehicles Spawned :  {stats['total_spawned']}\n"
            f"Vehicles Absorbed:  {stats['total_absorbed']}\n"
            f"Still in Network :  {stats['vehicles_in_network']}\n"
            f"Src Queue (end)  :  {wait}\n\n"
            f"Avg Travel Time  :  {stats['avg_travel_time']:.1f} steps\n"
            f"Min Travel Time  :  {stats['min_travel_time']} steps\n"
            f"Max Travel Time  :  {stats['max_travel_time']} steps\n\n"
            f"Avg Queue Length :  {stats['avg_queue_length']:.2f}\n"
            f"Peak Queue       :  {stats['peak_queue_length']}\n\n"
            "Per Sink:\n"
        )
        for sid, s in stats["per_sink"].items():
            summary += f"  {sid}: {s['absorbed']} absorbed, avg={s['avg_travel_time']:.1f}\n"

        ax.text(0.05, 0.95, summary, transform=ax.transAxes,
                color="white", fontsize=8.5, va="top", fontfamily="monospace",
                bbox=dict(boxstyle="round", facecolor="#0d1f33", edgecolor="#334466"))
        ax.set_title("Summary", color="white", fontsize=9)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0d0d1f")
        plt.close(fig)
        print(f"Statistics saved → {output_path}")
