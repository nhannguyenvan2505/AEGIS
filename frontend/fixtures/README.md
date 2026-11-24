# Synthetic telemetry fixture

`raw_snapshot.synthetic.json` is a byte-for-byte curated copy of the software-only
`environment_ingest_20261025/raw_snapshot.json` rehearsal. Its metadata declares
`source=synthetic`, instrument `Software fixture — no physical sensor` and
`reference=SYNTHETIC`. UUIDs are generated test identifiers. No field observations,
physical sensors, real account credentials or disease labels are represented.
The original historical evidence remains unchanged. The package manifest records
the SHA-256 of the curated bytes; test_telemetry_audit checks integrity/as-of/QC.
It is not a training dataset or evidence of field performance.
