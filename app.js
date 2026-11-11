const API = ""; // same origin — works on Vercel and with `python dev_server.py`

let papers = [];
let importance = [];
let currentQuestion = "";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function setError(el, message) {
  el.textContent = message;
  el.classList.toggle("hidden", !message);
}

async function parseError(res) {
  try { const body = await res.json(); return body.error || body.detail || `HTTP ${res.status}`; }
  catch { return `HTTP ${res.status}`; }
}

async function search(question) {
  const q = question.trim().replace(/\s+/g, " ");
  if (q.length < 3) { setError($("errorBox"), "Please enter at least 3 characters."); return; }

  $("loading").classList.remove("hidden");
  setError($("errorBox"), "");
  $("searchBtn").disabled = true;

  try {
    const res = await fetch(`${API}/api/rank`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    if (!res.ok) throw new Error(await parseError(res));
    const data = await res.json();

    papers = data.papers;
    importance = data.importance || [];
    currentQuestion = q;

    renderAll();
    $("results").classList.remove("hidden");
    $("ragAnswer").classList.add("hidden");
    $("ragSourcesWrap").classList.add("hidden");
    $("results").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    $("results").classList.add("hidden");
    setError($("errorBox"), err.message || "The analysis could not be completed.");
  } finally {
    $("loading").classList.add("hidden");
    $("searchBtn").disabled = false;
  }
}

function renderAll() {
  renderMetrics();
  renderTop5();
  renderCharts();
  renderInterpretation();
  renderTable();
}

function renderMetrics() {
  const avgCitations = papers.reduce((s, p) => s + p.citations, 0) / papers.length;
  const openPct = 100 * papers.filter((p) => p.open_access).length / papers.length;
  const years = papers.map((p) => p.year).filter((y) => y !== null);
  const latest = years.length ? Math.max(...years) : "—";
  const avgScore = papers.reduce((s, p) => s + p.ranking_score, 0) / papers.length;

  $("metrics").innerHTML = `
    <div class="metric"><div class="label">Papers retrieved</div><div class="value">${papers.length}</div></div>
    <div class="metric"><div class="label">Average citations</div><div class="value">${avgCitations.toFixed(1)}</div></div>
    <div class="metric"><div class="label">Open access</div><div class="value">${openPct.toFixed(0)}%</div></div>
    <div class="metric"><div class="label">Latest year</div><div class="value">${latest}</div></div>
    <div class="metric"><div class="label">Avg ranking score</div><div class="value">${avgScore.toFixed(3)}</div></div>`;
}

function renderTop5() {
  $("topPapers").innerHTML = [...papers].sort((a, b) => a.rank - b.rank).slice(0, 5).map((p) => {
    const pct = Math.min(100, Math.max(0, p.ranking_score * 100));
    return `<div class="paper-card">
      <h3>${p.rank}. ${esc(p.title)}</h3>
      <div class="meta">${esc(p.authors)} · ${p.year ?? "year n/a"} · ${p.citations.toLocaleString()} citations · ${p.open_access ? "open access" : "not open access"}</div>
      <div class="progress"><div style="width:${pct}%"></div></div>
      <span style="font-size:0.78rem;color:var(--muted)">Ranking score ${p.ranking_score.toFixed(3)} · proxy ${p.proxy_score.toFixed(3)}</span><br/>
      ${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noreferrer">Open the paper ↗</a>` : ""}
    </div>`;
  }).join("");
}

function shortTitle(t) { return t.length > 55 ? t.slice(0, 52) + "…" : t; }

function renderCharts() {
  const layout = { font: { family: "Poppins" }, margin: { l: 8, r: 8, t: 44, b: 40 }, paper_bgcolor: "#fff", plot_bgcolor: "#fbfaf5" };
  const cfg = { displayModeBar: false, responsive: true };

  const top10 = [...papers].sort((a, b) => a.ranking_score - b.ranking_score).slice(-10);
  Plotly.newPlot("chartTop", [{
    type: "bar", orientation: "h",
    x: top10.map((p) => p.ranking_score), y: top10.map((p) => shortTitle(p.title)),
    marker: { color: "#134e5e" },
    hovertemplate: "%{y}<br>Score: %{x:.3f}<extra></extra>",
  }], { ...layout, title: "Top 10 papers by ranking score", xaxis: { title: "Ranking score" }, yaxis: { automargin: true } }, cfg);

  Plotly.newPlot("chartScatter", [{
    type: "scatter", mode: "markers",
    x: papers.map((p) => p.citations), y: papers.map((p) => p.text_similarity),
    marker: { size: 12, color: papers.map((p) => p.ranking_score), colorscale: "Blues", showscale: true, colorbar: { title: "Score" }, line: { width: 0.5, color: "#134e5e" } },
    text: papers.map((p) => p.title),
    hovertemplate: "%{text}<br>Citations: %{x}<br>Similarity: %{y:.3f}<extra></extra>",
  }], { ...layout, title: "Citations vs textual similarity", xaxis: { title: "Citation count" }, yaxis: { title: "Textual similarity (TF-IDF)" } }, cfg);

  const yearCounts = {};
  for (const p of papers) if (p.year !== null) yearCounts[p.year] = (yearCounts[p.year] || 0) + 1;
  const years = Object.keys(yearCounts).map(Number).sort((a, b) => a - b);
  Plotly.newPlot("chartYears", [{
    type: "bar", x: years, y: years.map((y) => yearCounts[y]),
    marker: { color: "#1b6a74" }, hovertemplate: "Year %{x}<br>Papers: %{y}<extra></extra>",
  }], { ...layout, title: "Publication year distribution", xaxis: { title: "Year" }, yaxis: { title: "Papers", dtick: 1 } }, cfg);

  const open = papers.filter((p) => p.open_access).length;
  Plotly.newPlot("chartOpenAccess", [{
    type: "pie", labels: ["Open access", "Not open access"], values: [open, papers.length - open],
    marker: { colors: ["#8ab17d", "#e3645f"] }, textinfo: "label+percent+value",
  }], { ...layout, title: "Open-access distribution" }, cfg);

  const imp = [...importance].sort((a, b) => a.pct - b.pct);
  Plotly.newPlot("chartImportance", [{
    type: "bar", orientation: "h",
    x: imp.map((i) => i.pct), y: imp.map((i) => i.label),
    marker: { color: "#e3645f" }, text: imp.map((i) => i.pct.toFixed(1) + "%"), textposition: "outside",
    hovertemplate: "%{y}: %{x:.1f}%<extra></extra>",
  }], { ...layout, title: "ML feature importance (Random Forest)", xaxis: { title: "Importance (%)", range: [0, 100] } }, cfg);
}

function renderInterpretation() {
  const avgCitations = papers.reduce((s, p) => s + p.citations, 0) / papers.length;
  const openPct = 100 * papers.filter((p) => p.open_access).length / papers.length;
  const best = [...papers].sort((a, b) => a.rank - b.rank)[0];
  const topFeature = importance[0] ? importance[0].label.toLowerCase() : "text similarity";
  $("interpretation").innerHTML = `
    <li><strong>${papers.length} papers</strong> matched your question. The model ranks <strong>“${esc(best.title)}”</strong> highest (score ${best.ranking_score.toFixed(3)}). Ranking scores predict a proxy formula — not human-verified usefulness.</li>
    <li>Average citations is <strong>${avgCitations.toFixed(1)}</strong>; <strong>${openPct.toFixed(0)}%</strong> of the sample is open access. Open access = free to read, not higher quality.</li>
    <li>The forest relied most on <strong>${esc(topFeature)}</strong>. Citations favour older papers, so newer work scores on recency instead.</li>`;
}

function renderTable() {
  $("datasetTable").querySelector("tbody").innerHTML = [...papers].sort((a, b) => a.rank - b.rank).map((p) => `
    <tr>
      <td>${p.rank}</td>
      <td class="title-cell">${esc(p.title)}</td>
      <td>${esc(p.authors)}</td>
      <td>${p.year ?? "—"}</td>
      <td>${p.citations.toLocaleString()}</td>
      <td>${p.open_access ? "Open" : "Closed"}</td>
      <td>${p.text_similarity.toFixed(3)}</td>
      <td>${p.ranking_score.toFixed(3)}</td>
      <td>${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noreferrer">↗</a>` : ""}</td>
    </tr>`).join("");
}

function escapeCsv(v) {
  const s = v === null || v === undefined ? "" : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadCsv() {
  const cols = ["rank", "title", "authors", "abstract", "year", "citations", "open_access",
    "url", "text_similarity", "citation_score", "recency_score", "abstract_length",
    "abstract_length_score", "open_access_score", "proxy_score", "ranking_score"];
  const rows = [...papers].sort((a, b) => a.rank - b.rank).map((p) => cols.map((c) => escapeCsv(p[c])).join(","));
  const slug = currentQuestion.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40) || "results";
  const blob = new Blob([[cols.join(","), ...rows].join("\r\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `ranked_papers_${slug}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function generateAnswer() {
  const btn = $("generateBtn");
  btn.disabled = true;
  $("ragLoading").classList.remove("hidden");
  setError($("ragError"), "");

  const chosen = [...papers].sort((a, b) => a.rank - b.rank).slice(0, Number($("topK").value));
  try {
    const res = await fetch(`${API}/api/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: currentQuestion,
        papers: chosen.map((p) => ({ title: p.title, abstract: p.abstract, year: p.year, citations: p.citations })),
      }),
    });
    if (!res.ok) throw new Error(await parseError(res));
    const data = await res.json();

    $("ragAnswer").textContent = data.answer;
    $("ragAnswer").classList.remove("hidden");
    $("ragSources").innerHTML = chosen.map((p, i) =>
      `<li><a href="${esc(p.url)}" target="_blank" rel="noreferrer">[${i + 1}] ${esc(p.title)}</a> · ${p.year ?? "n/a"} · ${p.citations.toLocaleString()} citations</li>`
    ).join("");
    $("ragSourcesWrap").classList.remove("hidden");
  } catch (err) {
    setError($("ragError"), err.message || "The answer could not be generated.");
  } finally {
    btn.disabled = false;
    $("ragLoading").classList.add("hidden");
  }
}

$("searchForm").addEventListener("submit", (event) => { event.preventDefault(); search($("queryInput").value); });
document.querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click", () => {
  $("queryInput").value = chip.dataset.query;
  search(chip.dataset.query);
}));
$("topK").addEventListener("input", (event) => { $("topKValue").textContent = event.target.value; });
$("generateBtn").addEventListener("click", generateAnswer);
$("csvBtn").addEventListener("click", downloadCsv);
