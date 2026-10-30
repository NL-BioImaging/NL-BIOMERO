"""Regenerate the measured-results chart with matplotlib (authoring only).

Run: python docs/_figures/shallow_methods.py [--png]
Storage and reference diagrams are Mermaid sources in docs/_diagrams/.
"""
from pathlib import Path
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "_static" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans", "sans-serif"],
                     "font.size": 11, "svg.fonttype": "none",
                     "savefig.facecolor": "white"})
BLUE, GREEN, GREY = "#245b83", "#28765b", "#526171"

fig = plt.figure(figsize=(12, 8.3))
grid = fig.add_gridspec(2, 2, height_ratios=[1, 1.15])
axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])]
# Historical matched 846-image observations. Full bytes were measured before
# pruning; no separate no-shallow end-to-end run was timed at this scale.
# Exact source values are preserved in the archived measurement sheet.
labels = ["Full\n(no shallow)", "Local\nshallow", "Remote\nshallow"]
colors = [GREY, BLUE, GREEN]
full_bytes = 7_726_998_765
full_transfer_s, remote_transfer_s = 80.983, 11.109
local_stage_s = 4089.186 + 2337.594
remote_stage_s = 868 + 63.492
local_analysis_s, remote_analysis_s = 3318, 3271
local_total_s, remote_total_s = 19099.602, 18226.039
panels = [
    ("A  Shallowing saves up to 75% of result storage", "% of full result bytes",
     [100, 1_898_421_322 / full_bytes * 100, 1_913_445_569 / full_bytes * 100],
     ["7.73 GB", "1.90 GB", "1.91 GB"], 125),
    ("B  Remote cuts return copy + validation time by 86%", "% of full-ZIP copy + validation time",
     [100, 100, remote_transfer_s / full_transfer_s * 100],
     ["81.0 s", "81.0 s", "11.1 s"], 125),
]
for ax, (title, ylabel, values, absolute, ymax) in zip(axes, panels):
    for i, (value, color, caption) in enumerate(zip(values, colors, absolute)):
        if value is None:
            ax.text(i, 50, "Not\nmeasured", ha="center", va="center", color=GREY,
                    fontsize=12, style="italic", linespacing=1.4)
            continue
        ax.bar(i, value, color=color, width=.56, zorder=3)
        if value == 0:
            ax.plot(i, 0, marker="_", markersize=22, color=color,
                    markeredgewidth=2, clip_on=False, zorder=4)
        percent = f"{value:.0f}%" if value in (0, 100) else f"{value:.1f}%"
        ax.text(i, value + ymax * .025, percent + "\n" + caption,
                ha="center", va="bottom", fontsize=11, linespacing=1.3,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2})
    ax.set_title(title, loc="left", fontsize=11, weight="bold", pad=16)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_xticks(range(3), labels, fontsize=11)
    ax.set(xlim=(-.6, 2.6), ylim=(0, ymax))
    ax.axhline(100, color=GREY, linestyle="--", linewidth=.9, alpha=.65)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", length=0, pad=9)
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
ax = fig.add_subplot(grid[1, :])
stage_colors = [BLUE, "#a57918", "#cdd9e2"]
stage_names = ["Analysis job", "Shallowing / validation", "Other work, I/O and waiting"]
for x, total, analysis, shallow in [
        (1, local_total_s, local_analysis_s, local_stage_s),
        (2, remote_total_s, remote_analysis_s, remote_stage_s)]:
    stages = [analysis, shallow, total - analysis - shallow]
    bottom = 0
    for j, (seconds, color, name) in enumerate(zip(stages, stage_colors, stage_names)):
        minutes = seconds / 60
        ax.bar(x, minutes, bottom=bottom, width=.56, color=color,
               label=name if x == 1 else None, zorder=3)
        ax.text(x, bottom + minutes / 2, f"{minutes:.1f} min", ha="center", va="center",
                color="white" if j < 2 else "#17354a", fontsize=9 if minutes < 20 else 11)
        bottom += minutes
    ax.text(x, bottom + 5, f"{bottom:.1f} min total\n{total / local_total_s * 100:.1f}% of Local",
            ha="center", va="bottom", fontsize=11, linespacing=1.3)
ax.text(0, 155, "Not measured", ha="center", va="center", color=GREY,
        fontsize=12, style="italic")
ax.set_title("C  Shallowing adds a processing stage to researcher waiting time", loc="left",
             fontsize=13, weight="bold", pad=18)
ax.set_ylabel("Minutes from submission to DONE", fontsize=11)
ax.set_xticks(range(3), labels, fontsize=11)
ax.set(xlim=(-.6, 2.6), ylim=(0, 395))
ax.legend(loc="upper left", ncol=1, frameon=False, fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="x", length=0, pad=9)
ax.grid(axis="y", alpha=.15)
ax.set_axisbelow(True)
fig.subplots_adjust(left=.085, right=.975, bottom=.09, top=.94, hspace=.62, wspace=.30)
fig.savefig(OUT / "shallow-results.svg", metadata={"Date": None})
if "--png" in sys.argv:
    fig.savefig(OUT / "shallow-results.png", dpi=150)
plt.close(fig)
