"""Render T08 validation comparison and untouched-test calibration diagnostics."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a new plot path')
    result = json.loads(args.results.read_text())
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    figure, axes = plt.subplots(1, 2, figsize=(12, 5.5), gridspec_kw={'width_ratios': [1.15, 1]})
    names = sorted(result['validation'], key=lambda n: result['validation'][n]['log_loss'], reverse=True)
    values = [result['validation'][n]['log_loss'] for n in names]
    colors = ['#167e81' if n == result['winner'] else '#aac4d5' for n in names]
    axes[0].barh(names, values, color=colors)
    for i, value in enumerate(values):
        axes[0].text(value+.008, i, f'{value:.3f}', va='center', fontsize=9)
    axes[0].set(xlim=(0, .79), xlabel='Log loss (lower is better)', title='Selection on validation · 255 samples')
    axes[1].plot([0, 1], [0, 1], '--', color='#999999', lw=1)
    for name, color in zip(result['test'], ('#167e81', '#bf7334', '#687887')):
        bins = [r for r in result['test'][name]['calibration']['bins'] if r['count']]
        axes[1].plot([r['mean_score'] for r in bins], [r['observed_event_rate'] for r in bins],
                     'o-', color=color, label=name, markersize=5)
    axes[1].set(xlim=(0, 1), ylim=(0, 1), xlabel='Mean score in fixed bin',
                ylabel='Observed synthetic event fraction', title='Test diagnostics · 255 samples / 135 clusters')
    axes[1].legend(loc='upper left', frameon=False, fontsize=9)
    axes[1].grid(alpha=.2)
    figure.suptitle('T08 · expanded synthetic forecast experiments', fontsize=16, x=.03, ha='left')
    figure.text(.03, .02, 'Seed 20261108. Winner fixed before test scoring. Five calibration bins; no calibration fitted. Synthetic evidence only.',
                fontsize=9, color='#555555')
    figure.tight_layout(rect=(0, .05, 1, .94))
    figure.savefig(args.out, dpi=180)
    plt.close(figure)


if __name__ == '__main__':
    main()
