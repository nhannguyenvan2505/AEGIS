"""Opportunity/event metrics with abstention, unresolved outcomes and group CIs."""
import math
import numpy as np
from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score,average_precision_score


def metrics(rows,scores,threshold):
    if len(rows)!=len(scores): raise ValueError('Row/score count mismatch')
    values=[float(s) for s in scores if s is not None]
    if any(not math.isfinite(s) or not 0<=s<=1 for s in values): raise ValueError('Invalid probability')
    known=[i for i,r in enumerate(rows) if r['synthetic_y'] is not None]
    scored=[i for i in known if scores[i] is not None]
    y=np.array([rows[i]['synthetic_y'] for i in scored],dtype=int)
    p=np.array([scores[i] for i in scored],dtype=float)
    alerts=[i for i,s in enumerate(scores) if s is not None and s>=threshold]
    positive=[i for i in known if rows[i]['synthetic_y']==1]
    tp=sum(i in alerts for i in positive); fp=sum(i in alerts for i in known if rows[i]['synthetic_y']==0)
    observable_days=len(known)*3
    bins=[]
    for j in range(10):
        mask=(p>=j/10)&(p<((j+1)/10) if j<9 else p<=1)
        bins.append(dict(lower=j/10,upper=(j+1)/10,count=int(mask.sum()),
            predicted_mean=float(p[mask].mean()) if mask.any() else None,
            observed_fraction=float(y[mask].mean()) if mask.any() else None))
    ece=sum(b['count']*abs(b['predicted_mean']-b['observed_fraction']) for b in bins if b['count'])/len(y) if len(y) else None
    leads=[]
    from datetime import datetime
    for i in positive:
        interval=rows[i]['observed_event_interval']
        if i in alerts and interval:
            issue=datetime.fromisoformat(rows[i]['issued_at'])
            leads.append(((datetime.fromisoformat(interval['lower_open'])-issue).total_seconds()/3600,
                          (datetime.fromisoformat(interval['upper_closed'])-issue).total_seconds()/3600))
    return dict(opportunities=len(rows),scored_opportunities=len(values),feature_coverage=len(values)/len(rows) if rows else None,
        abstentions=len(rows)-len(values),decisive_outcomes=len(known),unresolved_outcomes=len(rows)-len(known),
        decisive_scored=len(scored),positive_events=len(positive),true_alerts=tp,false_alerts=fp,
        alerts_with_unresolved_outcome=sum(i not in known for i in alerts),
        event_recall_including_abstentions=tp/len(positive) if positive else None,
        decisive_alert_precision=tp/(tp+fp) if tp+fp else None,
        observable_unit_days=observable_days,false_alerts_per_100_observable_unit_days=fp/observable_days*100 if observable_days else None,
        brier=float(brier_score_loss(y,p)) if len(y) else None,
        log_loss=float(log_loss(y,np.clip(p,1e-12,1-1e-12),labels=[0,1])) if len(y) else None,
        roc_auc=float(roc_auc_score(y,p)) if len(set(y))==2 else None,
        average_precision=float(average_precision_score(y,p)) if len(set(y))==2 else None,
        calibration_bins=bins,ece_10_equal_width=ece,
        lead_interval_lower_median_hours=float(np.median([x[0] for x in leads])) if leads else None,
        lead_interval_upper_median_hours=float(np.median([x[1] for x in leads])) if leads else None,
        lead_interval_count=len(leads),threshold=float(threshold))


def select_threshold(rows,scores,grid,minimum_recall):
    options=[metrics(rows,scores,t) for t in grid]
    feasible=[m for m in options if m['event_recall_including_abstentions'] is not None
              and m['event_recall_including_abstentions']>=minimum_recall]
    def false_rate(m): return m['false_alerts_per_100_observable_unit_days'] if m['false_alerts_per_100_observable_unit_days'] is not None else float('inf')
    chosen=min(feasible,key=lambda m:(false_rate(m),-(m['decisive_alert_precision'] or 0),-m['threshold'])) if feasible else min(
        options,key=lambda m:(-(m['event_recall_including_abstentions'] or 0),false_rate(m),-m['threshold']))
    return dict(threshold=chosen['threshold'],recall_constraint_met=bool(feasible),selection_metrics=chosen,grid_size=len(grid))


def paired_bootstrap(rows,methods,thresholds,replicates,seed,selected):
    rng=np.random.default_rng(seed); by_seed={}
    for i,r in enumerate(rows): by_seed.setdefault(r['replicate_seed'],{}).setdefault(r['component_id'],[]).append(i)
    keys=('brier','log_loss','event_recall_including_abstentions','false_alerts_per_100_observable_unit_days','feature_coverage')
    samples={name:{k:[] for k in keys} for name in methods}; deltas={k:[] for k in ('brier','log_loss')}
    for _ in range(replicates):
        ids=[]
        for groups in by_seed.values():
            names=sorted(groups)
            for idx in rng.integers(0,len(names),len(names)): ids.extend(groups[names[int(idx)]])
        results={name:metrics([rows[i] for i in ids],[scores[i] for i in ids],thresholds[name]) for name,scores in methods.items()}
        for name,m in results.items():
            for k in keys:
                if m[k] is not None: samples[name][k].append(m[k])
        for k in deltas:
            if results[selected][k] is not None and results['prior'][k] is not None:
                deltas[k].append(results[selected][k]-results['prior'][k])
    def interval(v):
        return dict(lower=float(np.quantile(v,.025)),upper=float(np.quantile(v,.975)),valid_replicates=len(v)) if v else dict(lower=None,upper=None,valid_replicates=0)
    return dict(method='paired_dependency_group_bootstrap_within_seed_percentile_95',replicates=replicates,
        intervals={name:{k:interval(v) for k,v in values.items()} for name,values in samples.items()},
        selected_minus_prior={k:interval(v) for k,v in deltas.items()})
