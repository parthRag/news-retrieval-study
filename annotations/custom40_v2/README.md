# Forty-query suite, version 2

See [the extension report](../../reports/CUSTOM_40_EXTENSION.md) for all added queries, temporal anchors, rationale and evaluation plan.

- `queries.all40.jsonl`: original 20 byte-for-byte, followed by new20; ten per category.
- `queries.extension20.jsonl`: only the 20 new information needs; five per category.
- `topic_families.json`: query-to-family mapping for dependence-aware analysis.
- `protocol.json`: immutable design freeze, source hashes, timing and assessment/evaluation rules.

Assessment and evaluation are complete:707 added pairs and 1,444 combined pairs, with initial 737 decisions byte-preserved. See [expanded results](../../reports/CUSTOM_40_DEPTH20.md). This follow-up was designed after initial results; no held-out replication or preregistration is claimed.

`assessments.{vocabulary,negation,homonym,temporal}.jsonl` preserve original assessor outputs. `adjudication.json` records five targeted full-article checks and one conservative date-evidence downgrade before scoring. `assessments.extension20.jsonl` contains final 707 decisions; `assessments.all40.jsonl` appends these to the original 737 bytes. `assessment_completion.json` binds hashes/counts. The current labels are thorough, full-article AI judgments for preliminary comparison; human review is planned next and has not yet been completed. See the [assessment method and review plan](../../reports/ASSESSMENT_METHOD.md). Disjoint parallel assignments do not provide inter-annotator agreement.

`evidence_visibility.all40.json` audits the exact512-token input for every assessed pair. Frozen query/protocol pending-status fields remain historical; completion is recorded separately rather than rewriting the freeze. All queries, including zero-positive V05, remain in averages. Custom MAP uses shallow pooled positives.
