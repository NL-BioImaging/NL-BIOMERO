"""Regenerate the measured-results chart with matplotlib (authoring only).

Run: python docs/_figures/shallow_methods.py [--data measurements.json]
     [--output figure.svg] [--png]
Measurements live in data/shallow-846-image.json; see README.txt for its format.
"""
import argparse
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def load_measurements(path):
    data = json.loads(path.read_text(encoding="utf-8"))

    def number(value, name):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError(f"{name} must be a finite, non-negative number")

    if not isinstance(data["runs"], dict) or "full" not in data["runs"]:
        raise ValueError("runs must contain the Full reference configuration")
    for mode, run in data["runs"].items():
        if "zarr_format" in run and run["zarr_format"] not in (2, 3):
            raise ValueError(f"{mode}.zarr_format must be 2 or 3")
        if "label" in run and not isinstance(run["label"], str):
            raise ValueError(f"{mode}.label must be text")
        for key in ("stored_bytes", "return_copy_validation_s"):
            if run[key] is not None:
                number(run[key], f"{mode}.{key}")
        timing = run["timing"]
        if timing is None:
            continue
        for key in ("analysis_s", "total_s"):
            number(timing[key], f"{mode}.timing.{key}")
        for stage, seconds in timing["shallowing_stages_s"].items():
            number(seconds, f"{mode}.timing.shallowing_stages_s.{stage}")
        accounted = timing["analysis_s"] + sum(timing["shallowing_stages_s"].values())
        if accounted > timing["total_s"] + 1e-6:
            raise ValueError(f"{mode}: analysis + shallowing exceeds total time")
    for key in ("stored_bytes", "return_copy_validation_s"):
        value = data["runs"]["full"][key]
        if value is None or value <= 0:
            raise ValueError(f"full.{key} needs a positive measured baseline")
    return data


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data", type=Path, default=HERE / "data" / "shallow-846-image.json")
parser.add_argument("--output", type=Path,
                    default=HERE.parent / "_static" / "figures" / "shallow-results.svg")
parser.add_argument("--png", action="store_true", help="Also write a PNG beside the SVG")
args = parser.parse_args()
try:
    data = load_measurements(args.data)
except (OSError, ValueError, KeyError, TypeError) as exc:
    parser.error(f"Invalid measurement data: {exc}")
if args.output.suffix.lower() != ".svg":
    parser.error("--output must be an SVG filename")
args.output.parent.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans", "sans-serif"],
                     "font.size": 11, "svg.fonttype": "none",
                     "svg.hashsalt": "biomero-shallow-results",
                     "savefig.facecolor": "white"})
BLUE, GREEN, GREY = "#245b83", "#28765b", "#526171"

fig = plt.figure(figsize=(12, 8.3))
grid = fig.add_gridspec(2, 2, height_ratios=[1, 1.15])
axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])]
modes = list(data["runs"])
default_labels = {"full": "Full\n(no shallow)", "local": "Local\nshallow", "remote": "Remote\nshallow"}
labels = []
for mode in modes:
    run = data["runs"][mode]
    label = run.get("label", default_labels.get(mode, mode.replace("_", " ").title()))
    if "zarr_format" in run:
        label += f"\nZarr v{run['zarr_format']}"
    labels.append(label)
palette = {"full": GREY, "local": BLUE, "remote": GREEN}
colors = [palette.get(mode, GREY) for mode in modes]
mixed_formats = len({run["zarr_format"] for run in data["runs"].values() if "zarr_format" in run}) > 1
reference = data["runs"]["full"]
stored = [data["runs"][mode]["stored_bytes"] for mode in modes]
transfer = [data["runs"][mode]["return_copy_validation_s"] for mode in modes]


def relative(values, baseline):
    return [None if value is None else value / baseline * 100 for value in values]


storage_percent = relative(stored, reference["stored_bytes"])
transfer_percent = relative(transfer, reference["return_copy_validation_s"])
storage_saving = max((100 - value for mode, value in zip(modes, storage_percent)
                      if mode != "full" and value is not None), default=0)
remote_percent = transfer_percent[modes.index("remote")] if "remote" in modes else None
transfer_saving = None if remote_percent is None else 100 - remote_percent
storage_title = (f"A  Shallowing saves up to {storage_saving:.0f}% of result storage"
                 if storage_saving > 0 else "A  Stored result size relative to Full")
transfer_title = (f"B  Remote cuts return copy + validation time by {transfer_saving:.0f}%"
                  if transfer_saving is not None and transfer_saving > 0
                  else "B  Return copy + validation time relative to Full")
if mixed_formats:
    storage_title = (f"A  Configuration comparison: up to {storage_saving:.0f}% less storage"
                     if storage_saving > 0 else "A  Result storage by configuration")
    transfer_title = (f"B  Return copy + validation time: {transfer_saving:.0f}% lower"
                      if transfer_saving is not None and transfer_saving > 0
                      else "B  Return copy + validation time by configuration")
panels = [
    (storage_title, "% of full result bytes", storage_percent,
     [None if value is None else f"{value / 1e9:.2f} GB" for value in stored]),
    (transfer_title, "% of full-ZIP copy + validation time", transfer_percent,
     [None if value is None else f"{value:.1f} s" for value in transfer]),
]
for ax, (title, ylabel, values, absolute) in zip(axes, panels):
    ymax = max(value for value in values if value is not None) * 1.25
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
    ax.set_xticks(range(len(modes)), labels, fontsize=11)
    ax.set(xlim=(-.6, len(modes)-.4), ylim=(0, ymax))
    ax.axhline(100, color=GREY, linestyle="--", linewidth=.9, alpha=.65)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", length=0, pad=9)
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
ax = fig.add_subplot(grid[1, :])
stage_colors = [BLUE, "#a57918", "#cdd9e2"]
stage_names = ["Analysis job", "Shallowing / validation", "Other work, I/O and waiting"]
timings = [data["runs"][mode]["timing"] for mode in modes]
reference_order = [modes.index("full")] + [i for i, mode in enumerate(modes) if mode != "full"]
time_reference = next((i for i in reference_order
                       if timings[i] is not None and timings[i]["total_s"] > 0), None)
ymax = max((timing["total_s"] / 60 for timing in timings if timing is not None), default=1)
ymax = max(ymax * 1.25, 1)
legend_added = False
for x, timing in enumerate(timings):
    if timing is None:
        ax.text(x, ymax * .4, "Not measured", ha="center", va="center", color=GREY,
                fontsize=12, style="italic")
        continue
    total, analysis = timing["total_s"], timing["analysis_s"]
    shallow = sum(timing["shallowing_stages_s"].values())
    stages = [analysis, shallow, total - analysis - shallow]
    bottom = 0
    for j, (seconds, color, name) in enumerate(zip(stages, stage_colors, stage_names)):
        minutes = seconds / 60
        ax.bar(x, minutes, bottom=bottom, width=.56, color=color,
               label=name if not legend_added else None, zorder=3)
        if minutes > 0:
            ax.text(x, bottom + minutes / 2, f"{minutes:.1f} min", ha="center", va="center",
                    color="white" if j < 2 else "#17354a", fontsize=9 if minutes < 20 else 11)
        bottom += minutes
    legend_added = True
    caption = f"{bottom:.1f} min total"
    if time_reference is not None:
        baseline = timings[time_reference]["total_s"]
        caption += f"\n{total / baseline * 100:.1f}% of {labels[time_reference].splitlines()[0]}"
    ax.text(x, bottom + ymax * .015, caption,
            ha="center", va="bottom", fontsize=11, linespacing=1.3)
time_title = ("C  Researcher wait by configuration and stage" if mixed_formats
              else "C  Shallowing adds a processing stage to researcher waiting time")
ax.set_title(time_title, loc="left",
             fontsize=13, weight="bold", pad=45)
ax.set_ylabel("Minutes from submission to DONE", fontsize=11)
ax.set_xticks(range(len(modes)), labels, fontsize=11)
ax.set(xlim=(-.6, len(modes)-.4), ylim=(0, ymax))
if legend_added:
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=3,
              frameon=False, fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="x", length=0, pad=9)
ax.grid(axis="y", alpha=.15)
ax.set_axisbelow(True)
fig.subplots_adjust(left=.085, right=.975, bottom=.09, top=.94, hspace=.62, wspace=.30)
fig.savefig(args.output, metadata={"Date": None, "Title": data.get("title", "Shallow Zarr comparison")})
if args.png:
    fig.savefig(args.output.with_suffix(".png"), dpi=150)
plt.close(fig)
