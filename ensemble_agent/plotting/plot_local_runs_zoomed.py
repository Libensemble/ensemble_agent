#!/usr/bin/env python3

"""
Plot f by optimization run with a zoomed panel focused on the minima region.

Two-panel version of plot_local_runs for cases where f has high variance,
making minima indistinguishable on a full-range y-axis.

Top panel: full range for context.
Bottom panel: y-axis auto-clipped around flagged local minima.

To be run from the calling script directory, or called via plot().
"""

import glob
import os
import pickle
import sys

import numpy as np
import matplotlib
from matplotlib import pyplot as plt


def plot(npy_file=None, pickle_file=None, run_name=None, output_dir=None):
    """Generate zoomed optimization runs plot.

    Returns (output_path, summary_text) or (None, error_text).
    """
    matplotlib.use("Agg")

    if npy_file is None:
        npy_files = glob.glob("*.npy")
        if not npy_files:
            return None, "No .npy files found."
        npy_file = max(npy_files, key=os.path.getmtime)

    if pickle_file is None:
        pickle_files = glob.glob("*.pickle")
        if not pickle_files:
            return None, "No .pickle files found."
        pickle_file = max(pickle_files, key=os.path.getctime)

    if run_name is None:
        run_name = os.path.splitext(os.path.basename(npy_file))[0]

    if output_dir is None:
        output_dir = os.path.dirname(npy_file) or "."

    title_font = 14
    label_font = 14

    plt.rcParams.update({'font.size': 12})

    H = np.load(npy_file)

    with open(pickle_file, "rb") as f:
        persis_info = pickle.load(f)

    # run_order may be at top level or nested under a worker key
    if "run_order" in persis_info:
        index_sets_raw = persis_info["run_order"]
    else:
        index_sets_raw = None
        for v in persis_info.values():
            if isinstance(v, dict) and "run_order" in v:
                index_sets_raw = v["run_order"]
                break
        if index_sets_raw is None:
            return None, "No run_order found in pickle file."

    # Remove incomplete points from each run
    index_sets = {
        key: [i for i in indices if H['sim_ended'][i]]
        for key, indices in index_sets_raw.items()
    }

    # Determine zoom range from flagged local minima
    local_min_mask = H['local_min']
    if not np.any(local_min_mask):
        return None, "No local minima flagged — zoomed plot not applicable."

    min_f_vals = H['f'][local_min_mask]
    f_lo = np.min(min_f_vals)
    f_hi = np.max(min_f_vals)
    f_range = f_hi - f_lo if f_hi > f_lo else abs(f_lo) * 0.5
    padding = f_range * 0.3
    zoom_lo = f_lo - padding
    zoom_hi = f_hi + padding

    # Create two-panel figure
    fig, (ax_full, ax_zoom) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

    for ax in (ax_full, ax_zoom):
        _plot_runs(ax, H, index_sets)

    # Full range panel
    ax_full.set_ylabel('f value', fontsize=label_font)
    ax_full.set_title(f'{run_name}: f values by optimization runs', fontsize=title_font)
    ax_full.legend(ncol=2, fontsize=9)
    ax_full.grid(True)

    # Zoomed panel
    ax_zoom.set_ylim(zoom_lo, zoom_hi)
    ax_zoom.set_xlabel('Simulation ID', fontsize=label_font)
    ax_zoom.set_ylabel('f value (zoomed)', fontsize=label_font)
    ax_zoom.set_title('Zoomed to minima region', fontsize=title_font)
    ax_zoom.grid(True)

    plt.tight_layout()
    output_path = os.path.join(output_dir, f"{run_name}_opt_runs_zoomed.png")
    plt.savefig(output_path)
    plt.close(fig)
    return output_path, f"{len(index_sets)} optimization runs plotted (zoomed to f in [{zoom_lo:.4f}, {zoom_hi:.4f}])."


def _plot_runs(ax, H, index_sets):
    """Plot optimization runs and random points on a given axes."""
    for key, indices in index_sets.items():
        f_values = H['f'][indices]
        line = ax.plot(indices, f_values, marker='o', label=f'Opt run {key}', zorder=2)
        run_color = line[0].get_color()

        min_index = indices[np.argmin(f_values)]
        min_f_value = np.min(f_values)
        ax.scatter(min_index, min_f_value, color='red', edgecolor='black', s=50, zorder=3)

        if not H['local_pt'][indices[0]]:
            ax.scatter(indices[0], f_values[0], facecolors='lightgrey', edgecolors=run_color, s=80, linewidths=2, zorder=4)

    ax.scatter([], [], color='red', edgecolor='black', s=50, label='Best value of opt run')
    ax.scatter(np.where(H['sim_ended'])[0], H['f'][H['sim_ended']], color='lightgrey', label='Random points', zorder=1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_name = sys.argv[1]
    else:
        run_name = os.path.basename(os.getcwd())

    path, summary = plot(run_name=run_name)
    print(f"\n{summary}")
    if path:
        print(f"  Saved: {path}")
