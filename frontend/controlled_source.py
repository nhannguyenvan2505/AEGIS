"""Versioned, declared raw-only context. Never establishes rights or expertise."""
SOURCE = 'controlled_experiment'
CONTEXT_SCHEMA = 'aegis-controlled-experiment-context-v1'
METADATA_SCHEMA = 'aegis-controlled-environment-metadata-v1'
EXPORT_SCHEMA = 'aegis-raw-telemetry-export-v2'
POLICY = dict(raw_only=True, rule_input_approved=False, disease_labels_approved=False,
              field_evaluation_approved=False, training_approved=False)
SOURCES = ('synthetic', 'field_observed', SOURCE)


def context(value):
    required = {'schema_version', 'setting', 'unit_alias', 'batch_alias',
                'shared_environment_cluster_alias', 'control_level', 'control_description',
                'uncontrolled_factors', 'setup_reference', 'source_dossier_reference',
                'collection_permission_reference'}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError('Controlled context requires the exact versioned provenance fields')
    if value['schema_version'] != CONTEXT_SCHEMA or value['setting'] not in ('pot', 'tray'):
        raise ValueError('Unsupported controlled context schema or setting')
    if value['control_level'] not in ('observational_setup', 'partially_controlled', 'controlled'):
        raise ValueError('Declare the actual control level')
    result = dict(value)
    for key in ('unit_alias', 'batch_alias', 'shared_environment_cluster_alias', 'control_description',
                'setup_reference', 'source_dossier_reference', 'collection_permission_reference'):
        text = value[key]
        limit = 120 if key.endswith('alias') else 500
        if not isinstance(text, str) or not text.strip() or len(text) > limit:
            raise ValueError('Nonempty bounded provenance text required: '+key)
        result[key] = text.strip()
    factors = value['uncontrolled_factors']
    if not isinstance(factors, list) or len(factors) > 20 or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in factors):
        raise ValueError('Uncontrolled factors must be up to 20 nonempty descriptions')
    result['uncontrolled_factors'] = [x.strip() for x in factors]
    return result


def validate_metadata(metadata):
    """Reject schema/source confusion, including a resealed source-only relabel."""
    if not isinstance(metadata, dict):
        raise ValueError('Raw metadata must be an object')
    source = metadata.get('source')
    if source not in SOURCES:
        raise ValueError('Unsupported declared source')
    if source == SOURCE:
        required = {'name', 'source', 'method', 'instrument', 'reference', 'nominal_interval_seconds',
                    'measurement_semantics', 'units', 'provenance', 'calibration_verified',
                    'schema_version', 'experiment_context', 'source_policy'}
        if set(metadata) != required:
            raise ValueError('Controlled metadata has missing or unknown fields')
        if metadata.get('schema_version') != METADATA_SCHEMA:
            raise ValueError('Controlled source requires versioned metadata')
        if context(metadata.get('experiment_context')) != metadata['experiment_context']:
            raise ValueError('Controlled context must use canonical stored values')
        if metadata.get('source_policy') != POLICY or any(type(x) is not bool for x in metadata['source_policy'].values()):
            raise ValueError('Controlled raw policy cannot approve downstream use')
    elif any(key in metadata for key in ('experiment_context', 'source_policy', 'schema_version')):
        raise ValueError('Legacy source cannot carry controlled metadata')
    return source


def validate_export(bundle):
    source = validate_metadata(bundle['metadata'])
    expected = EXPORT_SCHEMA if source == SOURCE else 'aegis-raw-telemetry-export-v1'
    if bundle.get('schema_version') != expected:
        raise ValueError('Raw export schema does not match declared source')
    if source == SOURCE:
        if bundle.get('source_policy') != POLICY or any(type(x) is not bool for x in bundle['source_policy'].values()):
            raise ValueError('Controlled export must remain raw-only and unapproved')
    elif 'source_policy' in bundle:
        raise ValueError('Controlled export policy on legacy source')
    return source
