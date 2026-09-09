# Isolated board and interaction graph v0

`neurosis.board.IsolatedBoard` is an in-process, run-scoped resource for controlled experiments. Every operation requires the exact experiment/run/population scope supplied when the board was created. It has no database client, HTTP client, public-memory import, or fallback path. Its only external effect is the operator-supplied event sink.

Posts emit `message_written`; reads emit `message_read`. Record content is hashed, references point to earlier write events, and controlled origin IDs remain in operator events. An explicit view exposes `source_ids` and `references`. A hidden view contains only `peer_id`, `claim_id`, and `statement`. Tests compare the actual read view with the frozen target prompt and fail the run on any mismatch.

`neurosis.graph.build_graph` deterministically derives entity nodes and observed relationship edges from one run's events. Each edge includes sorted supporting event IDs, evidence kinds, and recorder IDs. Exact duplicate events and repeated entity identities collapse deterministically. Conflicting event IDs, mixed runs, and mixed populations fail. Missing parent events and unknown origins remain explicit artifact fields.

Known-origin analysis counts apparent supporting reporter identities and the union of controlled origin IDs for a claim. IEC is the known origin count. CIR is `IEC / apparent_consensus`; it is undefined when provenance is missing or apparent consensus is zero. Direct and common ancestor traversal operates on recorded relationships. It does not convert temporal order or an absent path into causal or independence proof.

Trial bundles contain a static, dependency-free `report.html` with the main metrics and a provenance graph. The authoritative artifacts remain `events.jsonl`, `trial.json`, `graph.json`, and `metrics.json`. A future reviewed public run viewer can consume the same graph JSON with Cytoscape.js and the aggregate metrics with Vega-Lite without changing the recorded evidence.
