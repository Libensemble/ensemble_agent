#!/usr/bin/env python3

"""
Plot f by optimization run and identify mininum f for each run.

Random points are shown in grey - circled if start optimization runs.

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
    """Generate optimization runs plot.

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

    # Remove last element (incomplete) from each run
    index_sets = {
        key: [i for i in indices if H['sim_ended'][i]]
        for key, indices in index_sets_raw.items()
    }

    # Start the main figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot all optimization runs
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

    # Add labels, title, and legend to the main plot
    ax.set_xlabel('Simulation ID', fontsize=label_font)
    ax.set_ylabel('f value', fontsize=label_font)
    ax.set_title(f'{run_name}: f values by optimization runs', fontsize=title_font)
    ax.legend(ncol=2)
    ax.grid(True)

    # Save the plot
    output_path = os.path.join(output_dir, f"{run_name}_opt_runs.png")
    plt.savefig(output_path)
    plt.close(fig)
    return output_path, f"{len(index_sets)} optimization runs plotted."


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_name = sys.argv[1]
    else:
        run_name = os.path.basename(os.getcwd())

    path, summary = plot(run_name=run_name)
    print(f"\n{summary}")
    if path:
        print(f"  Saved: {path}")
