// Bootstrap only. Run automatically against an empty MongoDB dev volume.
const target = db.getSiblingDB('aegis');
const identifier = {bsonType: 'int', minimum: 1};
const numeric = {bsonType: ['double', 'int', 'long', 'decimal']};
const nonempty = {bsonType: 'string', minLength: 1};
const timestamp = {bsonType: 'date'};
// Extensions preserve provenance and support idempotent cross-database retries.
const common = {
  _id: {bsonType: 'objectId'},
  source: {enum: ['mock', 'synthetic', 'field', 'bench', 'legacy', 'user_uploaded']},
  ingest_key: nonempty,
  provenance: {bsonType: 'object'},
};
const definitions = {
  telemetry_readings: {
    required: ['device_id','field_id','timestamp','received_at','source','ingest_key'],
    properties: {
      ...common, device_id: identifier, field_id: identifier, timestamp, received_at: timestamp,
      temperature_c: {...numeric, minimum: -50, maximum: 60},
      air_humidity_pct: {...numeric, minimum: 0, maximum: 100},
      leaf_wet: {bsonType: 'bool'},
      soil_moisture_pct: {...numeric, minimum: 0, maximum: 100},
      soil_ph: {...numeric, minimum: 0, maximum: 14},
      battery_voltage: {...numeric, minimum: 0},
      quality_flags: {bsonType: 'array', uniqueItems: true, items: nonempty},
    },
    indexes: [
      [{device_id: 1, timestamp: -1}, {name: 'device_time'}],
      [{field_id: 1, timestamp: -1}, {name: 'field_time'}],
    ],
  },
  sensor_raw_events: {
    required: ['device_uid','topic_or_endpoint','received_at','payload','parse_status','source','ingest_key'],
    properties: {
      ...common, device_uid: nonempty, topic_or_endpoint: nonempty, received_at: timestamp,
      payload: {bsonType: 'object'}, parse_status: {enum: ['parsed','partial','rejected']},
      validation_errors: {bsonType: 'array', items: nonempty},
    },
    indexes: [[{device_uid: 1, received_at: -1}, {name: 'sender_received'}]],
  },
  ai_inference_logs: {
    required: ['inference_type','model_version_id','request_payload','result_payload','created_at','source','ingest_key'],
    properties: {
      ...common, inference_type: {enum: ['disease_detection','risk_prediction']},
      model_version_id: identifier, user_id: identifier, field_id: identifier, crop_cycle_id: identifier,
      request_payload: {bsonType: 'object'}, result_payload: {bsonType: 'object'},
      latency_ms: {bsonType: 'int', minimum: 0}, created_at: timestamp,
    },
    indexes: [
      [{model_version_id: 1, created_at: -1}, {name: 'model_created'}],
      [{inference_type: 1, created_at: -1}, {name: 'type_created'}],
    ],
  },
};
for (const [name, definition] of Object.entries(definitions)) {
  target.createCollection(name, {
    validator: {$jsonSchema: {
      bsonType: 'object', required: definition.required,
      additionalProperties: false, properties: definition.properties,
    }},
    validationLevel: 'strict', validationAction: 'error',
  });
  target.getCollection(name).createIndex({ingest_key: 1}, {name: 'unique_ingest_key', unique: true});
  for (const [keys, options] of definition.indexes) {
    target.getCollection(name).createIndex(keys, options);
  }
}
const applicationPassword = process.env.AEGIS_MONGO_PASSWORD;
if (!applicationPassword) throw new Error('AEGIS_MONGO_PASSWORD is required');
target.createUser({user: 'aegis_app', pwd: applicationPassword, roles: [{role: 'readWrite', db: 'aegis'}]});
