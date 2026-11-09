"""Plot the largest model-logit contributions from a stored synthetic forecast."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--explanation', type=Path, required=True)
    cli.add_argument('--out', type=Path, required=True)
    args = cli.parse_args()
    if args.out.exists():
        cli.error('Choose a new output path')
    data = json.loads(args.explanation.read_text())
    terms = sorted(data['terms'], key=lambda t: abs(t['contribution_logit']), reverse=True)[:12]
    terms.reverse()
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    figure, (axis, info) = plt.subplots(1, 2, figsize=(11.5, 5.9), gridspec_kw={'width_ratios': [2.1, 1]})
    values = [t['contribution_logit'] for t in terms]
    axis.barh([t['feature'] for t in terms], values, color=['#b8633b' if v > 0 else '#167e81' for v in values])
    axis.axvline(0, color='#777777', linewidth=.7)
    axis.set_xlabel('Contribution to model logit')
    axis.set_title('12 largest contributions by absolute value', fontsize=11)
    axis.grid(axis='x', alpha=.15)
    info.axis('off')
    info.text(0, .92, data['model_version'], fontsize=12, weight='bold', transform=info.transAxes)
    info.text(0, .79, f"Stored score: {data['score']:.6f}\nReconstructed: {data['reconstructed_score']:.6f}",
              fontsize=11, transform=info.transAxes, linespacing=1.7)
    info.text(0, .56, f"Intercept: {data['intercept']:+.6f}\nAll-term sum: {data['sum_contributions']:+.6f}\nLogit: {data['logit']:+.6f}",
              fontsize=10, transform=info.transAxes, linespacing=1.7)
    info.text(0, .27, f"score = sigmoid(intercept\n             + sum of all {len(data['terms'])} terms)\n\nPositive raises the model score.\nNegative lowers the model score.",
              fontsize=9, transform=info.transAxes, linespacing=1.5)
    figure.suptitle('T11 · explanation of a frozen forecast snapshot', fontsize=15, x=.035, ha='left')
    figure.text(.035, .025, 'Synthetic, uncalibrated model score. Contributions are not disease causes. Remaining terms are omitted from the bar chart.', fontsize=9)
    figure.tight_layout(rect=(0, .06, 1, .95))
    figure.savefig(args.out, dpi=180)
    plt.close(figure)


if __name__ == '__main__':
    main()
