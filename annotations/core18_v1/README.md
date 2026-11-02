# Core 2018 available-corpus experiment

The 50 official topics and 26,233 source qrels come from the preserved Hamsini study snapshot and were checked against NIST. Each topic has three separately evaluated formulations: official title, official description and one provisional AI-authored rewrite. All texts/protocol inputs were frozen before first Core 2018 retrieval.

Rewrites are not independently human-verified. The CSV is an unfilled review template, not completed annotation. Preserve the frozen texts and original results; save actual human verdicts with reviewer identity in a new file and document any later corrections before separately versioned evaluation.

Descriptions vary length/detail and are a query-form diagnostic. Rewrites intend to preserve the topic narrative; qrel reuse is conditional on that assumption. Earlier news/COVID results were known during experiment design. Primary metrics retain the one unavailable positive. The available mirror is not established as equivalent to official WaPo v2; see corpus_audit.json.
