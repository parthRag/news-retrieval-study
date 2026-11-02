# Integrated group experiments

`hamsini_robustness/` preserves Hamsini G's independently developed project at
commit `7b73bb339d9ea3827375ec10aa2e1c4bb67bde06` from
https://github.com/HamsiniGururaj/robust-news-retrieval.
The adjacent provenance manifest binds every imported file. Original source,
query rewrites, run files, results, tests and proposal remain unchanged.

The active news engine remains `src/news_ir/`. Integration code recomputes
the imported experiments and adds news-domain query-form/rewrite comparisons;
the scientific and news benchmarks are always reported separately. The imported
README/proposal/progress files describe their original milestone, including
work that was pending at import. They are not the current combined report.

Hamsini's implemented contributions include the controlled two-rewrite
TREC-COVID experiment, rewrite-validation tooling, retrieval/evaluation pipeline
and statistical analysis. Integration and subsequent corrections have their own
records; they are not attributed retroactively to the original snapshot.
