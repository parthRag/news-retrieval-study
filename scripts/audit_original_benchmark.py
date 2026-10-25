"""Audit cached NIST reference labels/topics against the supplied 57-query mirror."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from news_ir.data import DocumentStore, read_queries, sha256_file
from news_ir.evaluation import load_qrels


def main():
    root = Path.cwd()
    reference = root / "artifacts/reference/news2019"
    queries = read_queries(root / "queries.jsonl")
    qrels = load_qrels(root / "qrel.jsonl", [q["_id"] for q in queries])
    supplied = {(qid, doc_id): grade for qid, labels in qrels.items() for doc_id, grade in labels.items()}
    official = {}
    qrel_path = reference / "newsir19-qrels-background.txt"
    for line in qrel_path.read_text().splitlines():
        qid, _, doc_id, grade = line.split()
        if (qid, doc_id) in official:
            raise ValueError("Duplicate official qrel pair")
        official[(qid, doc_id)] = int(grade)
    if set(supplied) != set(official):
        raise ValueError("Supplied and official judgment pairs differ")
    if any(official[pair] != (2 ** grade if grade > 0 else 0) for pair, grade in supplied.items()):
        raise ValueError("Official gain mapping differs from expected 0/2/4/8/16")
    topics_path = reference / "newsir19-background-linking-topics.xml"
    # NIST publishes consecutive <top> elements, rather than a single XML root.
    topics = ET.fromstring("<topics>" + topics_path.read_text() + "</topics>")
    source = {top.findtext("num").split(":")[-1].strip(): top.findtext("docid").strip()
              for top in topics.findall("top")}
    if not set(qrels).issubset(source):
        raise ValueError("A supplied query is missing from official topics")
    with DocumentStore(root / "artifacts/indexes/bm25") as store:
        present = [{"query_id": qid, "canonical_source_id": source[qid]}
                   for qid in qrels if store._db.execute("SELECT 1 FROM documents WHERE doc_id=?", (source[qid],)).fetchone()]
        corpus_hash = store.manifest["source"]["sha256"]
    report = {
        "status": "passed", "supplied_query_count": len(queries), "official_topic_count": len(source),
        "judgment_pairs_checked": len(supplied), "same_judgment_pairs": True,
        "all_gains_match": True, "gain_mapping": {0: 0, 1: 2, 2: 4, 3: 8, 4: 16},
        "canonical_query_source_articles_present": present,
        "self_article_policy": "No canonical query article is present; do not infer exclusions from title equality",
        "corpus_sha256": corpus_hash, "supplied_qrels_sha256": sha256_file(root / "qrel.jsonl"),
        "official_qrels_sha256": sha256_file(qrel_path), "official_topics_sha256": sha256_file(topics_path),
        "reference_sources": ["https://trec.nist.gov/data/news/2019/newsir19-qrels-background.txt",
                              "https://trec.nist.gov/data/news/2019/newsir19-background-linking-topics.xml"],
        "scope": "Judgment/topic provenance verified; this does not establish full corpus or official protocol equivalence",
    }
    output = root / "artifacts/original_benchmark_provenance.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
