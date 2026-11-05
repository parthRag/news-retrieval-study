"use strict";
const $ = id => document.getElementById(id);
const isCustom = suite => suite === "custom" || suite === "expanded";
const isCore = suite => suite?.startsWith("core18-");
const suiteTitle = suite => catalog.suite_labels?.[suite] || suite;
const names = {bm25: "BM25 keyword search", dense: "E5 semantic search", rrf: "RRF hybrid · k = 60"};
let catalog, current, article, livePending = false;
function node(tag, text, className) {const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if(className) n.className = className; return n;}
function status(text, error=false) {$("status").textContent = text; $("status").className = error ? "error" : "";}
async function api(path, options) {const response = await fetch(path, options); const data = await response.json(); if(!response.ok) throw new Error(data.error || "Request failed"); return data;}
function fillQueries() {const suite = $("suite").value; $("query").replaceChildren(); for(const q of catalog.suites[suite]) {const option = node("option", `${q._id} · ${q.category ? q.category.replaceAll("_", " ") + " · " : ""}${q.text}`); option.value = q._id; $("query").append(option);}}
function metric(value, label) {const n = node("span", label); n.prepend(node("b", value.toFixed(3))); return n;}
function render(data) {
 current = data; $("assessment-status").hidden = !(data.mode === "saved" && (isCustom(data.suite) || data.suite === "core18-rewrite")); $("assessment-status").textContent = data.suite === "core18-rewrite" ? "These rewrites are AI-authored and await independent human intent review. Scores reuse NIST human relevance labels conditionally on preserving the original information need." : "Custom comparisons use full-article AI judgments. Human review is deferred and has not yet been completed."; $("comparison").hidden = false; $("result-query").textContent = data.query;
 $("result-source").textContent = data.mode === "live" ? "LIVE SEARCH · NEW QUERY · UNJUDGED" : isCustom(data.suite) ? `${data.query_id} · PRELIMINARY CUSTOM EXPERIMENT` : `${data.query_id} · ${isCore(data.suite) ? "CORE 2018 · AVAILABLE NEWS CORPUS" : "ORIGINAL BENCHMARK"} · SUPPLIED QRELS`;
 $("overlap").textContent = `${data.overlap} shared IDs in top ${data.k}`;
 $("rubric").hidden = !data.rubric?.relevant_if;
 $("include").textContent = `Include: ${data.rubric?.relevant_if || ""}`; $("exclude").textContent = `Exclude: ${data.rubric?.exclude_if || ""}`;
 $("score-note").textContent = data.mode === "live" ? `Live run completed in ${(data.elapsed_ms_with_startup/1000).toFixed(1)} s including process/model startup. RRF combines both complete top-1,000 lists. No relevance metrics are available for this query.` : isCustom(data.suite) ? "nDCG uses linear 0–2 gains. Pooled AP@1000 uses the complete top-20 union's known positives; unjudged is not confirmed irrelevant. Grades: 0 fails the need, 1 limited detail, 2 substantive match." : isCore(data.suite) ? "Metrics use NIST 0–2 qrels on the available news corpus, with unavailable positives retained. Description queries change length/detail; provisional rewrites require human intent review. This is not an official full-corpus reproduction." : "Metrics use the saved top-1,000 run and supplied 0–4 benchmark qrels. Unjudged documents retain their ranks and have zero metric contribution.";
 const results = $("results"); results.replaceChildren(); results.className = `results${Object.keys(data.engines).length === 3 ? " three" : ""}`;
 for(const [engine, result] of Object.entries(data.engines)) {
  const column = node("section", undefined, `engine ${engine}`); column.setAttribute("aria-label", names[engine]);
  const head = node("div", undefined, "engine-head"); head.append(node("h3", names[engine]), node("p", engine === "bm25" ? "Exact terms · full article text" : engine === "dense" ? "Semantic similarity · first 512 tokens" : "Equal-weight fusion of both ranked lists", "hint"));
  if(result.metrics) {const row = node("div", undefined, "metric-row"); row.append(metric(result.metrics.ndcg_at_5, "nDCG@5"), metric(result.metrics.ap_at_1000, isCustom(data.suite) ? "Pooled AP@1000" : "AP@1000"), metric(result.metrics.precision_at_5, "Precision@5")); head.append(row); if(data.paired_original) {const delta=result.metrics.ndcg_at_5-data.paired_original.metrics[engine].ndcg_at_5; head.append(node("p",`${delta >= 0 ? "+" : ""}${delta.toFixed(3)} nDCG@5 vs original title: ${data.paired_original.query}`,"hint"));}}
  column.append(head);
  for(const hit of result.hits.slice(0, data.k)) {
   const card = node("article", undefined, "card"), top = node("div", undefined, "card-top"); top.append(node("span", `RANK ${hit.rank}`));
   top.append(node("span", hit.assessment ? `grade ${hit.assessment.grade}` : "Unjudged", `grade${hit.assessment ? " g"+hit.assessment.grade : ""}`)); card.append(top, node("h4", hit.title), node("p", hit.empty_body ? "This record has no article body. The title is the available source content." : hit.snippet + (hit.snippet.length === 450 ? "…" : ""), "snippet"));
   const button = node("button", "Read article & evidence ↗"); button.type = "button"; button.addEventListener("click", () => openArticle(hit.doc_id)); card.append(button, node("div", `${engine === "dense" ? "Cosine" : engine === "rrf" ? "RRF" : "BM25"} score ${hit.score.toFixed(6)}`, "score"));
   if(hit.fusion) {
    const f = hit.fusion, rankLabel = e => f.component_ranks[e] === null ? `outside top ${f.component_depths[e].toLocaleString()}` : `#${f.component_ranks[e]}`;
    const explanation = node("details", undefined, "fusion-explanation"); explanation.append(node("summary", `BM25 ${rankLabel("bm25")} · E5 ${rankLabel("dense")}`));
    explanation.append(node("p", `Each source contributes 1 / (${f.k} + rank). BM25 contributes ${f.contributions.bm25.toFixed(6)}; E5 contributes ${f.contributions.dense.toFixed(6)}. A record outside a source's saved list contributes zero. These source ranks use the complete candidate lists, not just the displayed results.`, "hint")); card.append(explanation);
   }
   column.append(card);
  }
  results.append(column);
 }
}
async function replay(event) {event?.preventDefault(); try {status("Loading saved rankings and source articles…"); const p = new URLSearchParams({suite:$("suite").value, qid:$("query").value, k:$("depth").value}); render(await api(`/api/replay?${p}`)); status("Saved experiment loaded. No new retrieval was run.");} catch(e) {status(e.message,true);}}
async function openArticle(id) {
 try {const p = new URLSearchParams({id, suite:current.suite || "", qid:current.query_id || ""}); article = await api(`/api/document?${p}`); $("article-title").textContent = article.title || "Untitled article"; $("article-id").textContent = id;
 const a = article.assessment; $("assessment").textContent = a ? `Relevance grade ${a.grade} · ${a.assessor_type}${a.confidence ? " · " + a.confidence + " confidence (self-rated)" : ""}\n${a.rationale || "Supplied benchmark relevance judgment."}${a.evidence ? "\n\nEvidence:\n" + a.evidence.map(x=>`“${x.quote}”`).join("\n") : ""}` : "Unjudged for this query. No relevance grade is inferred.";
 $("prefix-only").checked = false; $("prefix-only").disabled = article.e5_input_end === null; drawArticle(); $("article").showModal();
 } catch(e) {status(e.message,true);}
}
function drawArticle() {
 const chars = Array.from(article.contents), part = (start,end) => chars.slice(start,end).join("");
 const prefix = $("prefix-only").checked, end = prefix ? article.e5_input_end : chars.length;
 $("article-note").textContent = prefix ? `Exact retained passage text: ${end.toLocaleString()} Unicode characters. Prefix/special tokens also count toward E5's 512-token budget.` : article.e5_input_end === null ? "Full stored title and body. An exact E5 input audit is available for assessed custom pairs." : `Full stored title and body. E5 retained ${article.e5_input_end.toLocaleString()} of ${chars.length.toLocaleString()} characters. Highlighted spans are saved assessment evidence.`;
 const body = $("article-body"); body.replaceChildren(); let cursor=0;
 const spans = [...(article.assessment?.evidence || [])].sort((a,b)=>a.start-b.start);
 for(const s of spans) {if(s.start < cursor || s.end > end) continue; body.append(document.createTextNode(part(cursor,s.start)), node("mark",part(s.start,s.end))); cursor=s.end;}
 body.append(document.createTextNode(part(cursor,end)));
}
function aggregate() {$("aggregate").replaceChildren(); for(const [suite, engines] of Object.entries(catalog.aggregate)) {const box=node("article"); box.append(node("h3",isCustom(suite) ? `Custom ${catalog.suites[suite].length} · preliminary` : suiteTitle(suite))); const table=node("table"), thead=node("thead"), tr=node("tr"); for(const name of ["Engine","nDCG@5",isCustom(suite) ? "Pooled MAP" : "MAP@1000"]) tr.append(node("th",name)); thead.append(tr); table.append(thead); const tbody=node("tbody"); for(const [e, m] of Object.entries(engines)){const r=node("tr"); for(const x of [e === "dense" ? "E5 dense" : e.toUpperCase(),m.ndcg_at_5.toFixed(4),m.ap_at_1000.toFixed(4)])r.append(node("td",x)); tbody.append(r);} table.append(tbody); box.append(table); $("aggregate").append(box);}}
$("saved-form").addEventListener("submit",replay); $("suite").addEventListener("change",()=>{fillQueries();replay();}); $("depth").addEventListener("change",replay);
for(const mode of ["saved","live"]) $(mode+"-tab").addEventListener("click",()=>{for(const m of ["saved","live"]){$(m+"-form").hidden = mode!==m; $(m+"-tab").setAttribute("aria-selected",String(mode===m));}});
$("close-article").addEventListener("click",()=>$("article").close()); $("prefix-only").addEventListener("change",drawArticle);
$("live-form").addEventListener("submit",async event=>{event.preventDefault(); if(livePending)return; livePending=true; $("live-submit").disabled=true; const start=Date.now(); try {status("Starting live BM25 search…"); const {job_id}=await api("/api/live",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:$("live-query").value})}); let job; do {await new Promise(r=>setTimeout(r,1200)); job=await api(`/api/job/${job_id}`); if(job.status==="running")status(`${job.stage} search running · ${Math.round((Date.now()-start)/1000)} s elapsed. You can continue exploring saved experiments.`);}while(job.status==="running"); if(job.status==="failed")throw new Error(job.error); render(job.result); status("Live search complete. Results are unjudged and do not alter the saved experiments.");} catch(e){status(e.message,true);} finally{livePending=false; $("live-submit").disabled=false;}});
(async()=>{try{catalog=await api("/api/catalog"); $("corpus").replaceChildren(node("span",`${catalog.eligible_documents.toLocaleString()} shared articles`),node("span",`${catalog.evaluated_query_count} distinct evaluated queries`),node("span",`${catalog.custom_assessed_pairs} assessed pairs`)); if(catalog.suites.expanded) {const option=node("option","40 linguistic challenges · preliminary"); option.value="expanded"; $("suite").prepend(option); $("suite").value="expanded";} $("assessment-scope").textContent=`The current custom study covers ${catalog.custom_assessed_pairs} article–query assessments in the complete union of each engine’s top 20. Its MAP is a shallow-pool estimate. The background-linking benchmark uses separate supplied judgments. Core 2018 adds 50 news topics with three formulations; its description and provisional-rewrite scores are separate. The original 20-query view is retained within the expanded suite.`; for (const suite of Object.keys(catalog.suites)) {if (![...$("suite").options].some(o=>o.value===suite)) {const option=node("option",suiteTitle(suite)); option.value=suite; $("suite").append(option);}} fillQueries(); aggregate(); await replay();}catch(e){status(e.message,true);}})();
