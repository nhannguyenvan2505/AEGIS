"""Render fixed-bin calibration diagnostics from a T07 evaluation JSON."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a new chart output path')
    result = json.loads(args.evaluation.read_text(encoding='utf-8'))
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True)
    for axis, partition in zip(axes, ('validation', 'test')):
        axis.plot([0, 1], [0, 1], color='#999999', linestyle='--', linewidth=1, label='Ideal calibration')
        for name, color, label, marker in [('baseline', '#23689b', 'Logistic Regression', 'o'),
                                          ('dummy', '#b46c20', 'Dummy train prior', 's')]:
            bins = result['partitions'][partition]['models'][name]['calibration']['bins']
            for row in bins:
                if row['count']:
                    axis.scatter(row['mean_score'], row['observed_event_rate'],
                                 s=35+row['count']*9, color=color, marker=marker, alpha=.85)
                    axis.annotate(f"n={row['count']}", (row['mean_score'], row['observed_event_rate']),
                                  xytext=(6, 7), textcoords='offset points', fontsize=9, color=color)
            axis.scatter([], [], color=color, marker=marker, label=label)
        axis.set(xlim=(-.04, 1.06), ylim=(-.05, 1.12), xlabel='Mean score in bin',
                 title=f'{partition.capitalize()} · 34 samples · 18 clusters')
        axis.grid(alpha=.18)
        axis.legend(loc='upper left', frameon=False, fontsize=9)
    axes[0].set_ylabel('Observed synthetic event fraction')
    figure.suptitle('FM-02 calibration diagnostics', fontsize=16, x=.07, ha='left')
    figure.text(.07, .015, 'Five fixed score bins. Marker area follows sample count. Historical synthetic data.', fontsize=9, color='#555555')
    figure.tight_layout(rect=(0, .05, 1, .95))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.out, dpi=180)
    plt.close(figure)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
