(() => {
  const $ = (sel) => document.querySelector(sel);
  const main = $("#main");
  const thread = $("#thread");
  const form = $("#composer");
  const input = $("#input");
  const sendBtn = $("#send");
  const errorEl = $("#error");
  const modeEl = $("#mode");
  const resetBtn = $("#reset");

  let mode = "search";
  let hasResults = false;
  let busy = false;
  // Papers from the latest search, for the cited-papers panel under each answer.
  let knownPapers = new Map();
  let topIds = new Set();

  // One session id per browser tab, so /api/chat reads this tab's last search.
  const sessionId = (() => {
    const key = "pa_session";
    try {
      const existing = sessionStorage.getItem(key);
      if (existing) return existing;
      const fresh = crypto.randomUUID().replace(/-/g, "");
      sessionStorage.setItem(key, fresh);
      return fresh;
    } catch {
      return Math.random().toString(16).slice(2) + Date.now().toString(16);
    }
  })();

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    for (const child of children) {
      if (child == null) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  async function api(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-Id": sessionId },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch { /* non-JSON error page */ }
    if (!res.ok) {
      const detail = data && data.detail;
      const message = Array.isArray(detail)
        ? detail.map((d) => d.msg).join("; ")
        : detail || `Request failed (${res.status})`;
      throw new Error(message);
    }
    return data;
  }

  function setMode(next) {
    mode = next;
    modeEl.querySelectorAll("button").forEach((b) => {
      b.setAttribute("aria-checked", String(b.dataset.mode === mode));
    });
    input.placeholder = mode === "search"
      ? "Ask a research question…"
      : "Ask something about the top 5 papers…";
    $("#input-label").textContent = mode === "search" ? "Research question" : "Ask the top 5";
    $(".send-text").textContent = mode === "search" ? "Search" : "Ask";
    sendBtn.setAttribute("aria-label", mode === "search" ? "Search" : "Ask");
    input.maxLength = mode === "search" ? 500 : 2000;
  }

  function showError(message) {
    errorEl.textContent = message;
    errorEl.hidden = !message;
  }

  function setBusy(state) {
    busy = state;
    sendBtn.disabled = state;
    input.disabled = state;
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }

  function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }

  function loadingNode(text) {
    return el("div", { class: "loading" },
      el("span", { class: "dots", "aria-hidden": "true" }, el("span"), el("span"), el("span")),
      text);
  }

  function recordView(paperId) {
    fetch(`/api/papers/${encodeURIComponent(paperId)}/view`, {
      method: "POST",
      headers: { "X-Session-Id": sessionId },
      keepalive: true,
    }).catch(() => {});
  }

  function paperLink(paper, className) {
    return el("a", {
      class: className,
      href: paper.url,
      target: "_blank",
      rel: "noopener noreferrer",
      onclick: () => recordView(paper.paper_id),
      text: paper.title,
    });
  }

  function metaLine(paper) {
    const authors = /^not identified/i.test(paper.authors || "") ? null : paper.authors;
    const parts = [paper.domain, paper.year, authors].filter(Boolean);
    return parts.join(" · ");
  }

  function scoreTitle(paper) {
    const f = (n) => (typeof n === "number" ? n.toFixed(2) : "–");
    return `Semantic ${f(paper.embedding_score)} · BM25 ${f(paper.bm25_score)} · Tavily ${f(paper.tavily_score)}`;
  }

  function renderPaperCard(paper, index) {
    return el("article", { class: "paper" },
      el("div", { class: "paper-rank", text: index + 1 }),
      paperLink(paper, "paper-title"),
      el("span", { class: "score", title: scoreTitle(paper), text: (paper.ranking_score ?? 0).toFixed(2) }),
      metaLine(paper) ? el("div", { class: "paper-meta", text: metaLine(paper) }) : null,
      paper.abstract ? el("p", { class: "paper-abstract", text: paper.abstract }) : null,
    );
  }

  function renderResults(data) {
    const wrap = el("div");
    (data.fetch_warnings || []).forEach((w) => wrap.append(el("div", { class: "notice", text: w })));

    wrap.append(el("p", { class: "turn-label", text: "Top 5 papers" }));
    const cards = el("div", { class: "papers" });
    data.top_5.forEach((p, i) => cards.append(renderPaperCard(p, i)));
    wrap.append(cards);

    const all = data.all_papers || [];
    if (all.length) {
      const list = el("ol", { class: "paper-list" });
      all.forEach((p) => list.append(el("li", {},
        el("span", { class: "n", text: p.rank }),
        paperLink(p),
        el("span", { class: "s", title: scoreTitle(p), text: (p.ranking_score ?? 0).toFixed(2) }),
      )));
      wrap.append(el("details", { class: "all-papers" },
        el("summary", { text: `All ${data.total_retrieved || all.length} ranked papers` }),
        list));
    }
    return wrap;
  }

  // Escape model output, then add light formatting and clickable [S#] citations.
  function formatAnswer(text, citations) {
    const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
    const cite = (n) => {
      const c = citations[n - 1];
      if (!c) return `<span class="cite" title="Unknown source">S${n}</span>`;
      return `<a class="cite" href="${esc(c.url)}" target="_blank" rel="noopener noreferrer" data-paper="${esc(c.paper_id)}" title="${esc(c.title)}">S${n}</a>`;
    };
    const inline = (line) => esc(line)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\n]+?)\*(?![*\w])/g, "$1<em>$2</em>")
      .replace(/[\[【]((?:S\d+\s*[,，]?\s*)+)[\]】]/g, (_, group) =>
        group.match(/\d+/g).map((n) => cite(Number(n))).join(""));

    const blocks = [];
    let list = null;
    for (const raw of text.split(/\n/)) {
      const line = raw.trim().replace(/^#{1,6}\s+/, "");
      const bullet = line.match(/^(?:[-*•]|\d+[.)])\s+(.*)/);
      if (bullet) {
        if (!list) { list = []; blocks.push({ list }); }
        list.push(inline(bullet[1]));
        continue;
      }
      list = null;
      if (line) blocks.push({ p: inline(line) });
    }
    return blocks.map((b) => b.list
      ? `<ul>${b.list.map((li) => `<li>${li}</li>`).join("")}</ul>`
      : `<p>${b.p}</p>`).join("");
  }

  function renderAnswer(data) {
    const citations = data.citations || data.sources || [];
    const box = el("div", { class: "answer" });
    const body = el("div");
    body.innerHTML = formatAnswer(data.answer || "", citations);
    body.querySelectorAll("a.cite").forEach((a) => a.addEventListener("click", () => recordView(a.dataset.paper)));
    box.append(body);

    const foot = el("div", { class: "answer-foot" });
    if (data.abstains) foot.append(el("span", { class: "badge warn", text: "Not enough evidence" }));
    else if (data.verified) foot.append(el("span", { class: "badge ok", text: "Citations checked" }));
    else foot.append(el("span", { class: "badge warn", text: "Check citations" }));
    foot.append(el("span", { text: `${data.retrieved_passages || 0} passages · fact-checked` }));
    if (data.writing_standard) {
      foot.append(el("span", { title: "Written in ASD-STE100 Simplified Technical English", text: `· ${data.writing_standard}` }));
    }
    box.append(foot);

    if (!data.abstains) {
      const panel = renderCitedPapers(citations, data.used_citations || []);
      if (panel) box.append(panel);
    }
    return box;
  }

  // One entry per cited paper (several passages often come from the same paper).
  function renderCitedPapers(citations, usedCitations) {
    const byPaper = new Map();
    [...new Set(usedCitations)].sort((a, b) => a - b).forEach((n) => {
      const c = citations[n - 1];
      if (!c) return;
      const entry = byPaper.get(c.paper_id) || { citation: c, labels: [] };
      entry.labels.push(`S${n}`);
      byPaper.set(c.paper_id, entry);
    });
    if (!byPaper.size) return null;

    const list = el("ol", { class: "cited-list" });
    for (const [id, { citation, labels }] of byPaper) {
      const known = knownPapers.get(id);
      const paper = known ? { ...known, title: known.title || citation.title, url: known.url || citation.url } : citation;
      const meta = known ? metaLine(known) : "";
      const abstract = topIds.has(id) ? known.abstract : "";
      list.append(el("li", { class: "cited-item" },
        el("div", { class: "cited-labels" }, ...labels.map((l) => el("span", { class: "cite", text: l }))),
        paperLink(paper, "cited-title"),
        meta ? el("div", { class: "cited-meta", text: meta }) : null,
        abstract ? el("p", { class: "cited-abstract", text: abstract }) : null,
      ));
    }
    return el("details", { class: "cited" },
      el("summary", {}, `View cited papers (${byPaper.size})`),
      list);
  }

  const STAGE_TEXT = {
    drafting: "Drafting an answer from the top 5 papers…",
    checking: "Checking facts and simplifying the wording…",
  };

  // Stream /api/chat/stream (newline-delimited JSON) into `slot`; resolves when the answer is done.
  async function streamAnswer(question, slot) {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-Id": sessionId },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) {
      let detail = null;
      try { detail = (await res.json()).detail; } catch { /* non-JSON error page */ }
      throw new Error(Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || `Request failed (${res.status})`);
    }

    let citations = [];
    let text = "";
    let body = null;
    let frame = 0;
    const paint = () => {
      frame = 0;
      body.innerHTML = formatAnswer(text, citations);
    };

    const handle = (event) => {
      if (event.type === "meta") {
        citations = event.citations || [];
      } else if (event.type === "status") {
        slot.replaceChildren(loadingNode(STAGE_TEXT[event.stage] || "Working…"));
      } else if (event.type === "delta") {
        if (!body) {
          body = el("div", { class: "stream-body" });
          slot.replaceChildren(el("div", { class: "answer streaming", "aria-busy": "true" }, body));
        }
        text += event.text;
        // A timer (not requestAnimationFrame) so text still paints when the tab is in the background.
        if (!frame) frame = setTimeout(paint, 40);
      } else if (event.type === "done") {
        if (frame) clearTimeout(frame);
        slot.replaceChildren(renderAnswer(event));
        return true;
      } else if (event.type === "error") {
        throw new Error(event.message || "The answer failed.");
      }
      return false;
    };

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line && handle(JSON.parse(line))) return;
      }
      if (done) break;
    }
    if (buffer.trim() && handle(JSON.parse(buffer))) return;
    throw new Error("The answer stream ended early. Try again.");
  }

  async function runSearch(question) {
    const turn = el("div");
    const bubble = el("div", { class: "turn-q", text: question });
    turn.append(loadingNode("Searching scholarly sources and ranking papers… this can take a little while."));
    thread.append(bubble, turn);
    scrollToBottom();

    let data;
    try {
      data = await api("/api/search", { question });
    } catch (err) {
      bubble.remove();
      turn.remove();
      input.value = question;
      showError(err.message);
      return;
    }

    // Answer slot sits above the papers, so the answer reads first once it arrives.
    const answerSlot = el("div", { class: "answer-slot" }, loadingNode("Reading the top 5 papers…"));
    turn.replaceChildren(answerSlot, renderResults(data));
    knownPapers = new Map((data.all_papers || data.top_5 || []).map((p) => [p.paper_id, p]));
    topIds = new Set((data.top_5 || []).map((p) => p.paper_id));
    hasResults = true;
    modeEl.hidden = false;
    resetBtn.hidden = false;
    $("#chips").hidden = true;
    setMode("chat");

    try {
      await streamAnswer(question, answerSlot);
    } catch (err) {
      answerSlot.replaceChildren(el("div", { class: "notice", text: `Couldn't answer from these papers: ${err.message}` }));
    }
  }

  async function runChat(question) {
    const turn = el("div");
    const bubble = el("div", { class: "turn-q", text: question });
    turn.append(loadingNode("Reading the top 5 papers…"));
    thread.append(bubble, turn);
    scrollToBottom();

    try {
      await streamAnswer(question, turn);
    } catch (err) {
      bubble.remove();
      turn.remove();
      input.value = question;
      showError(err.message);
    }
  }

  async function submit() {
    const question = input.value.trim().replace(/\s+/g, " ");
    const min = mode === "search" ? 5 : 3;
    if (question.length < min) {
      showError(`Enter at least ${min} characters.`);
      input.focus();
      return;
    }
    if (busy) return;

    showError("");
    main.classList.remove("is-empty");
    input.value = "";
    autosize();
    setBusy(true);
    try {
      if (mode === "search") await runSearch(question);
      else await runChat(question);
    } finally {
      if (!thread.children.length) main.classList.add("is-empty");
      autosize();
      setBusy(false);
      input.focus();
      scrollToBottom();
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); submit(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  });
  input.addEventListener("input", () => { autosize(); if (!errorEl.hidden) showError(""); });

  document.querySelectorAll(".example").forEach((chip) => chip.addEventListener("click", () => {
    input.value = chip.textContent;
    autosize();
    input.focus();
  }));

  modeEl.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-mode]");
    if (!btn || (btn.dataset.mode === "chat" && !hasResults)) return;
    setMode(btn.dataset.mode);
    input.focus();
  });

  resetBtn.addEventListener("click", () => {
    thread.replaceChildren();
    main.classList.add("is-empty");
    hasResults = false;
    knownPapers = new Map();
    topIds = new Set();
    modeEl.hidden = true;
    resetBtn.hidden = true;
    $("#chips").hidden = false;
    input.value = "";
    autosize();
    setMode("search");
    showError("");
    input.focus();
  });

  setMode("search");
  input.focus();
})();
