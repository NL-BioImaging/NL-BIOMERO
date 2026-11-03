"""Plot reported Plate-scale comparisons; measurements remain in JSON."""
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.stats import t as student_t


def runtime_ci(run):
    """Student-t 95% CI half-width; adjusted totals need their own SD."""
    key = "adjusted_total_sd_min" if run["excluded_wait_stage"] else "total_sd_min"
    sd = run.get(key)
    if run["n"] < 2 or sd is None:
        return None
    return float(student_t.ppf(.975, run["n"] - 1)) * sd / math.sqrt(run["n"])


def runtime_difference_ci(full, remote):
    """Unpaired Welch CI for Remote minus Full, without assuming matched runs."""
    if any(r["n"] < 2 or r["excluded_wait_stage"]
           or r.get("total_sd_min") is None for r in (full, remote)):
        return None
    variances = [r["total_sd_min"] ** 2 / r["n"] for r in (full, remote)]
    variance = sum(variances)
    delta = remote["total_min"] - full["total_min"]
    if variance == 0:
        return delta, delta, delta
    df = variance ** 2 / sum(v ** 2 / (r["n"] - 1)
                             for v, r in zip(variances, (full, remote)))
    half = float(student_t.ppf(.975, df)) * math.sqrt(variance)
    return delta, delta - half, delta + half


def plot_campaign(data, output, png=False):
    plates = data["plates"]
    if not plates:
        raise ValueError("plates must not be empty")
    for plate in plates:
        for mode in ("full", "remote"):
            run = plate["runs"][mode]
            for key in ("stored_bytes", "total_min", "helper_execution_s"):
                value = run[key]
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or value < 0
                        or (value == 0 and key != "helper_execution_s")):
                    raise ValueError(f"{plate['label']}.{mode}.{key}: invalid measurement")
            if run["n"] < 1 or run["zarr_format"] not in (2, 3):
                raise ValueError("positive repetition count and Zarr format 2 or 3 required")
            for key in ("stored_sd_bytes", "total_sd_min", "adjusted_total_sd_min"):
                value = run.get(key)
                if value is not None and (isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value) or value < 0):
                    raise ValueError(f"{key} must be a finite, non-negative SD or null")
                if value is not None and run["n"] < 2:
                    raise ValueError("sample SD requires at least two observations")
            for value in run["stages_min"].values():
                if not math.isfinite(value) or value < 0:
                    raise ValueError("stage times must be finite and non-negative")
            excluded = run["excluded_wait_stage"]
            if excluded is not None and excluded not in run["stages_min"]:
                raise ValueError("excluded wait stage must name a measured stage")
            samples = run.get("total_samples_min", [])
            if samples and (len(samples) != run["n"]
                    or any(not math.isfinite(v) or v < 0 for v in samples)
                    or abs(sum(samples) / len(samples) - run["total_min"]) > .005):
                raise ValueError("runtime samples must match n and the reported mean")
            # The report rounds each independent stage to 0.01 minute.
            tolerance = (len(run["stages_min"]) + 1) * .005 + 1e-6
            if abs(sum(run["stages_min"].values()) - run["total_min"]) > tolerance:
                raise ValueError("reported stages do not reconcile with elapsed time")

    grey, purple = "#526171", "#7553a2"
    stage_colors = ["#9bbbcf", "#245b83", "#b58a24", "#40957b", "#d8dee5"]
    stage_names = ["Input preparation", "Analysis execution", "Remote shallower",
                   "Return / packaging / extraction", "Other work and waiting"]
    fig, axes = plt.subplots(2, len(plates), figsize=(12, 8.8), squeeze=False)
    max_saved = max(100 * (1 - p["runs"]["remote"]["stored_bytes"] /
                          p["runs"]["full"]["stored_bytes"]) for p in plates)
    fig.text(.075, .97, f"A  Result storage: up to {max_saved:.1f}% less retained Zarr data",
             fontsize=15, weight="bold", va="top")
    adjusted_labels = [p["label"].lower() for p in plates
                       if p["runs"]["full"]["excluded_wait_stage"]]
    time_heading = "B  Recorded elapsed time"
    if adjusted_labels:
        time_heading += f": {', '.join(adjusted_labels)} Full excludes the recovery wait"
    fig.text(.075, .535, time_heading,
             fontsize=14, weight="bold", va="top")

    for col, plate in enumerate(plates):
        runs = [plate["runs"][mode] for mode in ("full", "remote")]
        labels = [f"Full{' *' if runs[0]['recovered'] else ''}\nZarr v{runs[0]['zarr_format']}",
                  f"Remote shallow{' †' if runs[1]['source_metadata_repaired'] else ''}\nZarr v{runs[1]['zarr_format']}"]
        ax = axes[0, col]
        ax.set_title(f"{plate['label']}: {plate['images']:,} images\nn = {runs[0]['n']} / {runs[1]['n']} runs",
                     fontsize=12, pad=13)
        for x, (run, color) in enumerate(zip(runs, (grey, purple))):
            percent = 100 * run["stored_bytes"] / runs[0]["stored_bytes"]
            ax.bar(x, percent, width=.55, color=color, zorder=3)
            sd = run.get("stored_sd_bytes")
            sd_percent = 0 if sd is None else 100 * sd / runs[0]["stored_bytes"]
            if sd is not None:
                ax.errorbar(x, percent, yerr=sd_percent, fmt="none", ecolor="#172d40",
                            capsize=4, linewidth=1.2, zorder=4)
            ax.text(x, percent + sd_percent + 3, f"{percent:.1f}%\n{run['stored_bytes'] / 1e9:.3f} GB",
                    ha="center", va="bottom", fontsize=10)
        saved = 100 * (1 - runs[1]["stored_bytes"] / runs[0]["stored_bytes"])
        ax.text(.74, .8, f"{saved:.1f}% saved", transform=ax.transAxes,
                ha="center", fontsize=11, color=purple, weight="bold")
        storage_upper = max(100 * (r["stored_bytes"] + (r.get("stored_sd_bytes") or 0)) /
                            runs[0]["stored_bytes"] for r in runs)
        ax.set_ylim(0, max(128, storage_upper * 1.2))
        ax.set_ylabel("% of Full retained Zarr bytes" if col == 0 else "")
        ax.axhline(100, color=grey, lw=.8, ls="--", alpha=.6)

        ax = axes[1, col]
        totals = [r["total_min"] - r["stages_min"].get(r["excluded_wait_stage"], 0)
                  for r in runs]
        adjusted = any(r["excluded_wait_stage"] for r in runs)
        deviations = [runtime_ci(r) for r in runs]
        samples = [[v - r["stages_min"].get(r["excluded_wait_stage"], 0)
                    for v in r.get("total_samples_min", [])] for r in runs]
        ymax = max([t + (ci or 0) for t, ci in zip(totals, deviations)]
                   + [v for values in samples for v in values]) * 1.2
        for x, run in enumerate(runs):
            stages = run["stages_min"]
            prep = sum(stages[k] for k in ("input_compatibility", "canonical_preparation",
                                           "other_input_preparation_transfer"))
            selected = [prep, stages["analysis_execution"], stages["remote_shallower_execution"],
                        stages["result_return_packaging_extraction"]]
            selected.append(totals[x] - sum(selected))
            bottom = 0
            for minutes, color in zip(selected, stage_colors):
                ax.bar(x, minutes, bottom=bottom, width=.55, color=color, zorder=3)
                bottom += minutes
            ci = deviations[x]
            if ci is not None:
                ax.errorbar(x, bottom, yerr=ci, fmt="none", ecolor="#172d40",
                            capsize=4, linewidth=1.2, zorder=4)
            values = samples[x]
            offsets = [0 if len(values) == 1 else -.19 + .38 * j / (len(values) - 1)
                       for j in range(len(values))]
            ax.scatter([x + offset for offset in offsets], values, s=18,
                       facecolor="white", edgecolor="#172d40", linewidth=.9, zorder=5)
            caption = f"{totals[x]:.2f} min"
            if not adjusted:
                caption += f"\n{100 * totals[x] / totals[0]:.1f}% of Full"
            ax.text(x, bottom + (ci or 0) + ymax * .025, caption,
                    ha="center", va="bottom", fontsize=10)
            if run["recovered"]:
                return_top = sum(selected[:4])
                ax.annotate(f"Return interrupted\n({stages['result_return_packaging_extraction']:.2f} min recorded)",
                            xy=(x, return_top), xytext=(x, ymax * .35),
                            ha="center", fontsize=9, color="#24654f",
                            arrowprops={"arrowstyle": "->", "color": "#24654f"})
        difference = runtime_difference_ci(*runs)
        if difference is not None:
            delta, low, high = difference
            title = (f"Mean difference: {delta:+.2f} min\n"
                     f"95% CI [{low:+.1f}, {high:+.1f}] min")
        elif not adjusted:
            title = f"Observed difference: {totals[1] - totals[0]:+.2f} min"
        else:
            title = "* Recovery wait removed; other gaps retained"
        ax.set_title(title, fontsize=11, pad=12)
        lower = min(0, min(t - (ci or 0) for t, ci in zip(totals, deviations)))
        ax.set_ylim(lower * 1.15, ymax)
        ax.set_ylabel("Minutes (scale varies by Plate)" if col == 0 else "")
        for row in (0, 1):
            axis = axes[row, col]
            axis.set_xticks([0, 1], labels, fontsize=10)
            axis.set_xlim(-.6, 1.6)
            axis.spines[["top", "right"]].set_visible(False)
            axis.tick_params(axis="x", length=0, pad=8)
            axis.grid(axis="y", alpha=.15)
            axis.set_axisbelow(True)

    fig.legend(handles=[Patch(color=c, label=n) for c, n in zip(stage_colors, stage_names)],
               loc="lower center", bbox_to_anchor=(.5, .047), ncol=3,
               frameon=False, fontsize=10)
    repaired_labels = [p["label"].lower() for p in plates
                       if p["runs"]["remote"]["source_metadata_repaired"]]
    footnote = "A: mean ± SD. B: mean with 95% CI; dots are individual runs. "
    footnote += "Configurations differ in Zarr format. "
    if repaired_labels:
        footnote += f"† {', '.join(repaired_labels).capitalize()} shallow source provenance repaired. "
    fig.text(.075, .018, footnote + "Shared source excluded.", fontsize=9)
    fig.subplots_adjust(left=.075, right=.98, top=.86, bottom=.18,
                        hspace=.87, wspace=.3)
    fig.savefig(output, metadata={"Date": None, "Title": data["title"]})
    if png:
        fig.savefig(output.with_suffix(".png"), dpi=150)
    plt.close(fig)
