#!/usr/bin/env python3
"""
Plot simulation objective values (f) versus simulation ID from H_final.npy

To be run from the calling script directory, or called via plot().
"""

import glob
import os
import sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt


def plot(npy_file=None, run_name=None, output_dir=None):
    """Generate objective progress plot.

    Returns (output_path, summary_text) or (None, error_text).
    """
    matplotlib.use("Agg")

    if npy_file is None:
        npy_files = glob.glob("*.npy")
        if not npy_files:
            return None, "No .npy files found."
        npy_file = max(npy_files, key=os.path.getmtime)

    if run_name is None:
        run_name = os.path.splitext(os.path.basename(npy_file))[0]

    if output_dir is None:
        output_dir = os.path.dirname(npy_file) or "."

    # Load the structured array
    H = np.load(npy_file)

    # Filter data to only include completed simulations
    completed_mask = H['sim_ended'] == True
    H_filtered = H[completed_mask]

    # Create the plot
    plt.figure(figsize=(10, 6))
    plt.plot(H_filtered['sim_id'], H_filtered['f'], 'bo-', markersize=4, linewidth=1)
    plt.xlabel('Simulation ID')
    plt.ylabel('Objective Value (f)')
    plt.title(f'{run_name}: Objective Function Values vs Simulation ID')
    plt.grid(True, alpha=0.3)

    # Force integer ticks on x-axis
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(integer=True))

    # Add some statistics
    summary = f"{run_name} summary:\n  Number of simulations: {len(H_filtered)}"
    if len(H_filtered) > 0:
        cum_min = np.minimum.accumulate(H_filtered['f'])
        plt.plot(H_filtered['sim_id'], cum_min, 'r-', linewidth=2, alpha=0.8,
                 label=f'Cumulative min (best: {cum_min[-1]:.6f})')
        plt.legend()
        summary += f"\n  Best f value: {cum_min[-1]:.6f}"
    else:
        summary += "\n  No completed simulations found."

    plt.tight_layout()
    output_path = os.path.join(output_dir, f"{run_name}_f_progress.png")
    plt.savefig(output_path)
    plt.close()
    return output_path, summary


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_name = sys.argv[1]
    else:
        run_name = os.path.basename(os.getcwd())

    path, summary = plot(run_name=run_name)
    print(f"\n{summary}")
    if path:
        print(f"  Saved: {path}")
