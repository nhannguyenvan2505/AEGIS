"""Static synthetic T17 comparison, calibration and paired uncertainty figure."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    p=argparse.ArgumentParser(); p.add_argument('--report',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); r=json.loads(args.report.read_text(encoding='utf-8')); names=['prior','logistic','hist_gradient_boosting','fm03_frozen']
    labels=['Train prevalence','LR + sigmoid (selected)','HGB + sigmoid','Frozen FM03']
    colors=['#8796aa','#2277b7','#b38235','#7155a2']; fig,axes=plt.subplots(1,3,figsize=(15,4.5),layout='constrained')
    ax=axes[0]; x=np.arange(4); ax.bar(x,[r['aggregate_test'][n]['brier'] for n in names],color=colors)
    bounds=[r['confidence_intervals']['intervals'][n]['brier'] for n in names]
    points=np.array([r['aggregate_test'][n]['brier'] for n in names])
    ax.errorbar(x,points,yerr=np.array([[points[i]-b['lower'] for i,b in enumerate(bounds)],
        [b['upper']-points[i] for i,b in enumerate(bounds)]]),fmt='none',ecolor='#182333',capsize=4)
    ax.set_xticks(x,['Prior','LR','HGB','FM03']); ax.set_ylabel('Brier loss (lower is better)'); ax.set_title('Holdout + group bootstrap 95% CI')
    ax=axes[1]; ax.plot([0,1],[0,1],color='#aaaaaa',linestyle='--')
    for name,label,color in zip(names,labels,colors):
        bins=[b for b in r['aggregate_test'][name]['calibration_bins'] if b['count']]
        ax.plot([b['predicted_mean'] for b in bins],[b['observed_fraction'] for b in bins],'.-',color=color,label=label)
    ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mean predicted score',ylabel='Observed event fraction',title='Calibration (decisive scored outcomes)')
    ax.legend(fontsize=7,loc='upper left')
    ax=axes[2]
    keys=['brier','log_loss']; deltas=r['confidence_intervals']['selected_minus_prior']
    point=[r['aggregate_test'][r['selected']][k]-r['aggregate_test']['prior'][k] for k in keys]
    ax.errorbar(point,[1,0],xerr=np.array([[point[i]-deltas[k]['lower'] for i,k in enumerate(keys)],
        [deltas[k]['upper']-point[i] for i,k in enumerate(keys)]]),fmt='o',color=colors[1],capsize=5)
    ax.axvline(0,color='#bd4b41',linestyle='--'); ax.set_yticks([1,0],['Delta Brier','Delta log loss'])
    ax.set(xlabel='Selected LR minus prior (negative favors LR)',title='Both intervals cross zero',ylim=(-.6,1.6))
    for ax in axes: ax.grid(axis='y',alpha=.15); ax.spines[['top','right']].set_visible(False)
    fig.suptitle('T17 synthetic experiment | 144 holdout opportunities | candidate NOT qualified',fontsize=13)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists(): raise ValueError('Choose a new output')
    fig.savefig(args.out,dpi=170); plt.close(fig)


if __name__=='__main__': main()
