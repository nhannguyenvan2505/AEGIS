"""Static scientific summary of the frozen multi-seed raw acceptance run."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--acceptance', type=Path, required=True)
    cli.add_argument('--out', type=Path, required=True)
    args = cli.parse_args()
    if args.out.exists():
        cli.error('Choose a new output path')
    data = json.loads(args.acceptance.read_text())
    seeds = data['seeds']
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    figure, axes = plt.subplots(1, 2, figsize=(11.5, 5.1))
    x = np.arange(len(seeds))
    for offset, case, color, label in [(-.25, 'complete', '#167e81', 'Complete raw'),
                                     (0, 'one_slot_missing_every_hour', '#739db8', '5/6 slots per hour'),
                                     (.25, None, '#be996b', 'Dummy train prior')]:
        values = [s['metrics'][case]['candidate']['log_loss'] if case else s['metrics']['complete']['dummy']['log_loss'] for s in seeds]
        axes[0].bar(x+offset, values, width=.23, color=color, label=label)
    axes[0].set(ylabel='Test log loss (lower is better)', ylim=(0, .8), title='Quality across five independent RNG seeds')
    axes[0].legend(loc='lower left', frameon=False, fontsize=9)
    for case, color, marker, label in [('complete', '#167e81', 'o', 'Complete raw'),
                                      ('one_slot_missing_every_hour', '#739db8', 's', '5/6 slots per hour')]:
        axes[1].plot(x, [s['metrics'][case]['candidate']['roc_auc'] for s in seeds], marker=marker, color=color, label=label)
    axes[1].axhline(.65, linestyle='--', color='#be996b', label='Frozen minimum AUC')
    axes[1].set(ylabel='Test ROC AUC', ylim=(.5, 1), title='Fixed C=0.01; no test-based tuning')
    axes[1].legend(loc='lower left', frameon=False, fontsize=9)
    for axis in axes:
        axis.set_xticks(x, [str(s['seed'])[-4:] for s in seeds])
        axis.set_xlabel('Seed suffix (2026xxxx) · 255 test samples per seed')
        axis.grid(axis='y', alpha=.15)
    figure.suptitle('T09 · actual raw adapter → weather features → model', fontsize=15, x=.04, ha='left')
    total = sum(v['trials'] for s in seeds for v in s['stress'].values())
    figure.text(.04, .02, f'{total} stress checks. Synthetic point observations; no field validation. Acceptance: '+('PASS' if data['passed'] else 'FAIL'), fontsize=9)
    figure.tight_layout(rect=(0, .05, 1, .94))
    figure.savefig(args.out, dpi=180)
    plt.close(figure)


if __name__ == '__main__':
    main()
