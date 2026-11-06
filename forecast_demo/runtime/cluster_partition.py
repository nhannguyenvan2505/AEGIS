"""Explicit cluster guard around the existing temporal splitter. Never fits a model."""
import argparse
import json
from pathlib import Path

from pipeline import digest, identifier, load, partition, stamp

INPUT_SCHEMA = 'aegis-cluster-partition-input-v1'
REGISTRY_SCHEMA = 'aegis-independence-registry-v1'
DIMENSIONS = {'logger', 'shared_environment', 'site', 'batch'}
MANDATORY = {'logger', 'shared_environment'}
UNKNOWN = {'unknown', 'unset', 'pending', 'none', 'null', 'n/a'}


class ClusterConflict(ValueError):
    def __init__(self, conflicts):
        super().__init__('Related observation units are assigned to different partitions')
        self.conflicts = conflicts


def alias(value):
    identifier(value)
    if value != value.strip() or value.casefold() in UNKNOWN:
        raise ValueError('Registry identifiers must be explicit, trimmed, non-placeholder aliases')
    return value


def audit_groups(plan, registry):
    """Check the entire declared registry, including unassigned bridge units.

    Same plot across seasons, shared logger and shared environment are always
    grouped. Site/batch grouping is an explicit evaluation-policy choice.
    IDs and references are declarations, not independently verified evidence.
    """
    # Preserve existing group ownership, chronological bounds and purge guards.
    partition([], plan)
    if not isinstance(registry, dict) or set(registry) != {'schema_version', 'dimensions', 'units'}:
        raise ValueError('Invalid independence registry envelope')
    if registry['schema_version'] != REGISTRY_SCHEMA:
        raise ValueError('Unsupported independence registry schema')
    dims = registry['dimensions']
    if not isinstance(dims, list) or any(type(d) is not str for d in dims):
        raise ValueError('Registry dimensions must be an explicit string list')
    if len(set(dims)) != len(dims) or not MANDATORY <= set(dims) <= DIMENSIONS:
        raise ValueError('Unique logger/shared_environment dimensions required; site/batch are optional')
    if not isinstance(registry['units'], list) or not registry['units']:
        raise ValueError('Nonempty unit registry required')
    units = {}
    for unit in registry['units']:
        if not isinstance(unit, dict) or set(unit) != {'plot_id', 'season_id', 'clusters', 'evidence_reference'}:
            raise ValueError('Invalid registry unit fields')
        key = (alias(unit['plot_id']), alias(unit['season_id']))
        if key in units:
            raise ValueError('Duplicate registry plot-season unit')
        alias(unit['evidence_reference'])
        clusters = unit['clusters']
        if not isinstance(clusters, dict) or set(clusters) != set(dims):
            raise ValueError('Every unit must declare every selected cluster dimension')
        for values in clusters.values():
            if not isinstance(values, list) or not values:
                raise ValueError('Unknown/empty cluster membership is not independence')
            for value in values:
                alias(value)
            if len(set(values)) != len(values):
                raise ValueError('Duplicate cluster alias in one dimension')
        units[key] = unit
    assignments = {}
    for name, groups in plan['groups'].items():
        for group in groups:
            key = tuple(group)
            if key not in units:
                raise ValueError('Every planned plot-season requires registry metadata')
            assignments[key] = name

    parent = {key: key for key in units}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    members = {}
    for key in sorted(units):
        # Grouping by plot is derived from its identity, never a caller alias.
        tokens = [('plot', key[0])]
        for dimension in sorted(dims):
            tokens.extend((dimension, value) for value in sorted(units[key]['clusters'][dimension]))
        for token in tokens:
            members.setdefault(token, []).append(key)
    links = []
    for (dimension, cluster), keys in sorted(members.items()):
        for other in keys[1:]:
            union(keys[0], other)
        if len(keys) > 1:
            links.append(dict(dimension=dimension, cluster_alias=cluster, units=[list(k) for k in keys]))
    components = {}
    for key in sorted(units):
        components.setdefault(find(key), []).append(key)
    component_links = {}
    for link in links:
        component_links.setdefault(find(tuple(link['units'][0])), []).append(link)
    result = []
    for root, keys in components.items():
        splits = sorted({assignments[k] for k in keys if k in assignments})
        result.append(dict(component_id=digest([list(k) for k in keys]),
                           units=[list(k) for k in keys], partitions=splits,
                           links=component_links.get(root, []),
                           assigned_units=sum(k in assignments for k in keys)))
    conflicts = [c for c in result if len(c['partitions']) > 1]
    if conflicts:
        raise ClusterConflict(conflicts)
    return dict(schema_version='aegis-cluster-audit-v1', dimensions=sorted(dims),
                automatic_grouping=['same_plot_across_seasons'],
                components=result, shared_links=links, registry_units=len(units),
                planned_units=len(assignments), registry_sha256=digest(registry),
                plan_sha256=digest(plan), grouping_valid=True,
                provenance_status='declared_mapping_not_independently_verified')


def _partition_with_clusters(payload):
    if not isinstance(payload, dict) or set(payload) != {'schema_version', 'source', 'rows', 'plan', 'registry'}:
        raise ValueError('Invalid cluster partition input envelope')
    if payload['schema_version'] != INPUT_SCHEMA or payload['source'] not in ('synthetic', 'field_observed'):
        raise ValueError('Unsupported schema/source; controlled experiments are not enabled')
    audit = audit_groups(payload['plan'], payload['registry'])
    if not isinstance(payload['rows'], list):
        raise ValueError('Rows must be a list')
    registered = {tuple(k) for c in audit['components'] for k in c['units']}
    seen = set()
    for row in payload['rows']:
        if not isinstance(row, dict):
            raise ValueError('Dataset rows must be objects')
        key = (alias(row['plot_id']), alias(row['season_id']))
        if key not in registered:
            raise ValueError('Every row requires registry metadata, including rejected/unassigned rows')
        issued = stamp(row['issued_at'])
        if (key, issued) in seen:
            raise ValueError('Duplicate unit/issue row, including equivalent UTC timestamps')
        seen.add((key, issued))
        if type(row['structurally_eligible_field_row']) is not bool:
            raise ValueError('Structural eligibility must be boolean, not research approval')
        if stamp(row['feature_window_start']) > issued:
            raise ValueError('Feature window cannot start after issue time')
        if not isinstance(row['label'], dict):
            raise ValueError('Rows require the temporal splitter label metadata')
        if row['label']['label_available_at'] is not None:
            stamp(row['label']['label_available_at'])
    result = partition(payload['rows'], payload['plan'])
    return dict(schema_version='aegis-cluster-partition-v1', source=payload['source'],
                **result, grouping_audit=audit, input_sha256=digest(payload),
                training_approved=False, expert_labels_approved=False,
                limits=['Structural partition check only; not data/label provenance or permission approval',
                        'Missing or deliberately false registry relationships cannot be independently detected',
                        'Same aliases must identify shared entities across the full declared cohort',
                        'No automatic assignment, model fitting or disease metrics',
                        'Source synthetic and structural fixture rows never establish field performance'])


def partition_with_clusters(payload):
    try:
        return _partition_with_clusters(payload)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('Malformed cluster partition input') from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.input.resolve() == args.output.resolve() or args.output.exists():
        p.error('Choose a new output; historical inputs/results are preserved')
    try:
        result = partition_with_clusters(load(args.input))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    except ClusterConflict as exc:
        p.exit(2, json.dumps(dict(error='cross_partition_cluster', conflicts=exc.conflicts))+'\n')
    except (ValueError, OSError, RecursionError) as exc:
        p.exit(2, 'Cluster partition rejected: '+str(exc)+'\n')
    print(json.dumps(dict(counts={k: len(v) for k, v in result['partitions'].items()},
                          rejected=len(result['rejected']), training_performed=False)))


if __name__ == '__main__':
    main()
