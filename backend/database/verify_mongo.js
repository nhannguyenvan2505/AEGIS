// Passed over stdin by verify_databases.py. Wrap to make shell failures nonzero.
try {
  const names = ['telemetry_readings','sensor_raw_events','ai_inference_logs'];
  const created = [];
  function expectError(label, code, action) {
    try { action(); } catch (error) {
      if (error.code === code) { print('PASS ' + label); return; }
      throw error;
    }
    throw new Error(label + ': invalid document was accepted');
  }
  try {
    if (db.getCollectionNames().sort().join(',') !== names.slice().sort().join(',')) {
      throw new Error('Unexpected collection inventory');
    }
    for (const name of names) {
      const options = db.getCollectionInfos({name})[0].options;
      if (options.validationAction !== 'error' || options.validationLevel !== 'strict') {
        throw new Error(name + ': validator is not strict');
      }
      const indexes = db.getCollection(name).getIndexes();
      if (!indexes.some(i => i.name === 'unique_ingest_key' && i.unique)) throw new Error('Missing unique ingest index');
      const expectedIndexes = {
        telemetry_readings: ['device_time','field_time'],
        sensor_raw_events: ['sender_received'],
        ai_inference_logs: ['model_created','type_created'],
      };
      for (const index of expectedIndexes[name]) {
        if (!indexes.some(i => i.name === index)) throw new Error('Missing index ' + index);
      }
    }
    const now = new Date();
    const fixtures = {
      telemetry_readings: {device_id: NumberInt(1), field_id: NumberInt(1), timestamp: now, received_at: now, air_humidity_pct: 80},
      sensor_raw_events: {device_uid: 'verification', topic_or_endpoint: '/verification', received_at: now, payload: {}, parse_status: 'parsed'},
      ai_inference_logs: {inference_type: 'disease_detection', model_version_id: NumberInt(1), request_payload: {}, result_payload: {}, created_at: now},
    };
    for (const name of names) {
      const collection = db.getCollection(name);
      const id = new ObjectId();
      const valid = {...fixtures[name], _id: id, source: 'synthetic', ingest_key: 'verification-' + id.toHexString()};
      created.push([collection, id]);
      collection.insertOne(valid);
      print('PASS valid ' + name);
      expectError('duplicate ingest ' + name, 11000, () => collection.insertOne({...valid, _id: new ObjectId()}));
      const missing = {...valid, _id: new ObjectId()}; delete missing.source;
      expectError('required provenance source ' + name, 121, () => collection.insertOne(missing));
      expectError('unknown field ' + name, 121, () => collection.insertOne({...valid, _id: new ObjectId(), unexpected: true}));
      if (name === 'telemetry_readings') {
        expectError('humidity range', 121, () => collection.insertOne({...valid, _id: new ObjectId(), air_humidity_pct: 101}));
        expectError('BSON identifier type', 121, () => collection.insertOne({...valid, _id: new ObjectId(), device_id: '1'}));
      }
    }
  } finally {
    for (const [collection, id] of created) {
      collection.deleteOne({_id: id});
      if (collection.countDocuments({_id: id}) !== 0) throw new Error('Fixture cleanup failed');
    }
  }
  print('PASS MongoDB schema, validators, indexes and fixture cleanup');
} catch (error) {
  print(error.stack || String(error));
  quit(1);
}
