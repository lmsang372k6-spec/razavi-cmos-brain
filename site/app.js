/* Razavi CMOS Knowledge Brain — Standalone Interactive Web Application
 * Zero build dependencies. Works identically on GitHub Pages (/kb/*) and locally (../kb/*).
 */
"use strict";

(() => {
  const EDGE_COLORS = {
    upgrades_to: "#1f6c9f",
    fixes: "#346538",
    compensated_by: "#956400",
    trades_off_with: "#9f2f2d",
    requires: "#5b3b8c",
    governed_by: "#5e6266",
    layout_constrained_by: "#0f766e",
  };

  const EDGE_LABELS = {
    upgrades_to: "upgrades_to (Nâng cấp lên)",
    fixes: "fixes (Khắc phục bẫy)",
    compensated_by: "compensated_by (Bù ổn định bởi)",
    trades_off_with: "trades_off_with (Đánh đổi với)",
    requires: "requires (Yêu cầu)",
    governed_by: "governed_by (Chi phối bởi)",
    layout_constrained_by: "layout_constrained_by (Ràng buộc Layout)",
  };

  const state = {
    kbBase: "./kb",
    router: null,
    nodeMap: new Map(),
    edges: [],
    adjOut: new Map(),
    adjIn: new Map(),
    glossary: null,
    glossaryLoading: false,
    checklistCache: new Map(),
    markdownCache: new Map(),
    mode: "nodes", // nodes | graph | checklists | glossary | detail
    activeNodeId: null,
    activeChecklistId: null,
    filterDomain: "all",
    filterChapter: null,
    filterKind: "all",
    query: "",
    modalZoom: 1,
    glossaryLimit: 40,
  };

  const el = {
    search: document.getElementById("global-search"),
    clearSearch: document.getElementById("clear-search"),
    modeTabs: Array.from(document.querySelectorAll(".mode-tab")),
    kindBtns: Array.from(document.querySelectorAll("#kind-filters .pill")),
    domainList: document.getElementById("domain-list"),
    chapterGrid: document.getElementById("chapter-grid"),
    resetFilters: document.getElementById("reset-filters"),
    loadingBanner: document.getElementById("loading-banner"),
    view: document.getElementById("view-container"),
    sidebar: document.getElementById("sidebar"),
    sidebarToggle: document.getElementById("sidebar-toggle"),
    themeToggle: document.getElementById("theme-toggle"),
    iconSun: document.getElementById("icon-sun"),
    iconMoon: document.getElementById("icon-moon"),
    statNodes: document.getElementById("stat-nodes"),
    statDiagrams: document.getElementById("stat-diagrams"),
    statChecklists: document.getElementById("stat-checklists"),
    statGlossary: document.getElementById("stat-glossary"),
    releaseVer: document.getElementById("release-version"),
    rawIndexLink: document.getElementById("raw-index-link"),
    modal: document.getElementById("svg-modal"),
    modalTitle: document.getElementById("svg-modal-title"),
    modalInner: document.getElementById("svg-modal-inner"),
    modalOpenRaw: document.getElementById("modal-open-raw"),
    modalZoomIn: document.getElementById("modal-zoom-in"),
    modalZoomOut: document.getElementById("modal-zoom-out"),
    modalZoomReset: document.getElementById("modal-zoom-reset"),
    modalClose: document.getElementById("modal-close"),
    toast: document.getElementById("toast"),
  };

  let toastTimer = null;
  function showToast(msg) {
    el.toast.textContent = msg;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.toast.hidden = true;
    }, 2200);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function foldAscii(value) {
    return String(value ?? "")
      .replace(/đ/g, "d")
      .replace(/Đ/g, "D")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[_-]+/g, " ")
      .replace(/[^a-z0-9/+.]+/g, " ")
      .trim();
  }

  function kbUrl(relFromKb) {
    const clean = String(relFromKb).replace(/^\/+/, "").replace(/^kb\//, "");
    return `${state.kbBase}/${clean}`;
  }

  function resolveDiagramUrl(diagField) {
    if (!diagField) return "";
    const baseName = diagField.split("/").pop();
    return `${state.kbBase}/diagrams/${baseName}`;
  }

  function kindBadgeClass(kind) {
    if (kind === "topology") return "badge-topology";
    if (kind === "technique") return "badge-technique";
    return "badge-law";
  }

  async function detectAndLoadCore() {
    const candidates = ["./kb", "../kb"];
    let loadedRouter = null;
    for (const base of candidates) {
      try {
        const res = await fetch(`${base}/router-index.json`);
        if (res.ok) {
          loadedRouter = await res.json();
          state.kbBase = base;
          break;
        }
      } catch (_err) {
        // Try next candidate
      }
    }
    if (!loadedRouter) {
      throw new Error("Không tìm thấy kb/router-index.json. Hãy chạy python tools/build_index.py trước.");
    }
    state.router = loadedRouter;
    el.rawIndexLink.href = `${state.kbBase}/router-index.json`;

    for (const n of loadedRouter.nodes || []) {
      state.nodeMap.set(n.id, n);
      state.adjOut.set(n.id, []);
      state.adjIn.set(n.id, []);
    }

    // Load edges.jsonl
    try {
      const edgeRes = await fetch(`${state.kbBase}/graph/edges.jsonl`);
      if (edgeRes.ok) {
        const text = await edgeRes.text();
        for (const line of text.split(/\r?\n/)) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          const edge = JSON.parse(trimmed);
          state.edges.push(edge);
          if (!state.adjOut.has(edge.from)) state.adjOut.set(edge.from, []);
          if (!state.adjIn.has(edge.to)) state.adjIn.set(edge.to, []);
          state.adjOut.get(edge.from).push(edge);
          state.adjIn.get(edge.to).push(edge);
        }
      }
    } catch (_err) {
      // Non-fatal if edges not yet built
    }

    // Populate stats & sidebar
    const st = loadedRouter.stats || {};
    el.statNodes.textContent = st.node_count ?? loadedRouter.nodes.length;
    el.statDiagrams.textContent = st.diagram_count ?? 38;
    el.statChecklists.textContent = st.checklist_count ?? (loadedRouter.checklists || []).length;
    el.statGlossary.textContent = st.glossary_count ?? 2200;
    el.releaseVer.textContent = loadedRouter.release || "2026.11.18.1";

    renderSidebarControls();
    el.loadingBanner.hidden = true;
    el.view.hidden = false;

    // Kick off background glossary load for instant bilingual search
    ensureGlossaryLoaded();
  }

  async function ensureGlossaryLoaded() {
    if (state.glossary || state.glossaryLoading) return state.glossary;
    state.glossaryLoading = true;
    try {
      const res = await fetch(`${state.kbBase}/glossary/terms-vi-en.json`);
      if (res.ok) {
        const data = await res.json();
        state.glossary = data.terms || [];
      }
    } catch (_err) {
      state.glossary = [];
    } finally {
      state.glossaryLoading = false;
    }
    if (state.mode === "glossary" || state.query) {
      renderActiveView();
    }
    return state.glossary;
  }

  function renderSidebarControls() {
    // Domain list
    const totalCount = (state.router.nodes || []).length;
    const domainItems = [
      `<li><button type="button" class="nav-item ${state.filterDomain === "all" ? "is-active" : ""}" data-domain="all"><span>Tất cả 7 Tầng Tri thức</span><span class="nav-count">${totalCount}</span></button></li>`,
    ];
    for (const d of state.router.domains || []) {
      const active = state.filterDomain === d.id ? "is-active" : "";
      domainItems.push(
        `<li><button type="button" class="nav-item ${active}" data-domain="${escapeHtml(d.id)}"><span>${escapeHtml(d.title_vi)}</span><span class="nav-count">${d.node_count || 0}</span></button></li>`
      );
    }
    el.domainList.innerHTML = domainItems.join("");

    // Chapter buttons 01..19
    const chButtons = [];
    for (let ch = 1; ch <= 19; ch++) {
      const label = String(ch).padStart(2, "0");
      const active = state.filterChapter === ch ? "is-active" : "";
      const chMeta = (state.router.chapters || []).find((c) => c.chapter === ch);
      const title = chMeta ? `Ch.${label}: ${chMeta.title_vi} (${chMeta.title_en})` : `Chương ${label}`;
      chButtons.push(
        `<button type="button" class="ch-btn ${active}" data-chapter="${ch}" title="${escapeHtml(title)}">${label}</button>`
      );
    }
    el.chapterGrid.innerHTML = chButtons.join("");

    for (const btn of el.kindBtns) {
      btn.classList.toggle("is-active", btn.dataset.kind === state.filterKind);
    }

    const hasFilter = state.filterDomain !== "all" || state.filterChapter !== null || state.filterKind !== "all" || Boolean(state.query);
    el.resetFilters.hidden = !hasFilter;
  }

  function scoreNode(node, qFold, qTokens) {
    if (!qFold) return 1;
    const idFold = foldAscii(node.id);
    const viFold = foldAscii(node.title_vi);
    const enFold = foldAscii(node.title_en);
    const hay = node.search_text || foldAscii(`${node.id} ${node.title_vi} ${node.title_en} ${node.summary}`);
    if (idFold === qFold) return 120;
    if (enFold.includes(qFold) || viFold.includes(qFold)) return 95;
    if (idFold.includes(qFold)) return 85;
    let matched = 0;
    for (const tok of qTokens) {
      if (hay.includes(tok)) matched++;
    }
    if (matched === qTokens.length) return 60 + matched * 4;
    return 0;
  }

  function filterNodes() {
    const qFold = foldAscii(state.query);
    const qTokens = qFold ? qFold.split(/\s+/).filter(Boolean) : [];
    const results = [];

    for (const node of state.router.nodes || []) {
      if (state.filterDomain !== "all" && node.domain !== state.filterDomain) continue;
      if (state.filterChapter !== null && !(node.chapters || []).includes(state.filterChapter)) continue;
      if (state.filterKind === "topology" && node.kind !== "topology") continue;
      if (state.filterKind === "technique" && node.kind !== "technique") continue;
      if (state.filterKind === "law-concept" && !["law", "concept", "physical_rule"].includes(node.kind)) continue;

      // Support ch10 / chuong 10 query syntax
      const chMatch = qFold.match(/^(?:ch|chuong|chapter)\s*(\d{1,2})$/);
      if (chMatch) {
        if ((node.chapters || []).includes(Number(chMatch[1]))) {
          results.push({ node, score: 100 });
        }
        continue;
      }

      const sc = scoreNode(node, qFold, qTokens);
      if (sc > 0) results.push({ node, score: sc });
    }

    results.sort((a, b) => b.score - a.score || (a.node.chapters?.[0] || 99) - (b.node.chapters?.[0] || 99));
    return results.map((r) => r.node);
  }

  function searchGlossaryPreview(limit = 8) {
    if (!state.glossary || !state.query) return [];
    const qRaw = state.query.trim();
    const qFold = foldAscii(qRaw);
    if (!qFold) return [];
    const qTokens = qFold.split(/\s+/).filter(Boolean);
    const codeMatch = qRaw.match(/^t0*(\d+)$/i);
    const hits = [];

    for (const term of state.glossary) {
      if (state.filterChapter !== null && !(term.chapters || []).includes(state.filterChapter)) continue;
      if (codeMatch && Number(term.id.slice(1)) === Number(codeMatch[1])) {
        hits.push({ term, rank: 0 });
        continue;
      }
      const key = term.search_key || foldAscii(`${term.id} ${term.en} ${term.vi}`);
      const enF = foldAscii(term.en);
      const viF = foldAscii(term.vi);
      if (enF === qFold || viF === qFold) hits.push({ term, rank: 1 });
      else if (enF.startsWith(qFold) || viF.startsWith(qFold)) hits.push({ term, rank: 2 });
      else if (enF.includes(qFold) || viF.includes(qFold)) hits.push({ term, rank: 3 });
      else if (qTokens.every((t) => key.includes(t))) hits.push({ term, rank: 4 });
    }
    hits.sort((a, b) => a.rank - b.rank || Number(a.term.id.slice(1)) - Number(b.term.id.slice(1)));
    return hits.slice(0, limit).map((h) => h.term);
  }

  function syncModeTabs() {
    const tabMode = state.mode === "detail" ? "nodes" : state.mode;
    for (const btn of el.modeTabs) {
      btn.classList.toggle("is-active", btn.dataset.mode === tabMode);
    }
  }

  function renderActiveView() {
    syncModeTabs();
    renderSidebarControls();
    if (state.mode === "detail" && state.activeNodeId) {
      renderNodeDetailView(state.activeNodeId);
    } else if (state.mode === "graph") {
      renderGlobalGraphView();
    } else if (state.mode === "checklists") {
      renderChecklistsView();
    } else if (state.mode === "glossary") {
      renderGlossaryView();
    } else {
      renderNodesCatalogView();
    }
  }

  function renderNodesCatalogView() {
    const nodes = filterNodes();
    const glossaryHits = searchGlossaryPreview(6);
    const chLabel = state.filterChapter ? ` · Chương ${String(state.filterChapter).padStart(2, "0")}` : "";
    const domMeta = (state.router.domains || []).find((d) => d.id === state.filterDomain);
    const domLabel = domMeta ? ` · ${domMeta.title_vi}` : "";

    let glossaryStrip = "";
    if (state.query && glossaryHits.length > 0) {
      glossaryStrip = `
        <div class="section-bar">
          <h2>Thuật ngữ Chuẩn CLB khớp nhanh (${glossaryHits.length})</h2>
          <button type="button" class="link-btn" id="jump-all-glossary">Xem toàn bộ trong kho 2.200 thuật ngữ →</button>
        </div>
        <div class="node-grid" style="margin-bottom:24px">
          ${glossaryHits
            .map(
              (t) => `
            <div class="bento-box">
              <div class="card-topline">
                <span class="badge badge-neutral">${escapeHtml(t.id)}</span>
                <span class="meta">${(t.chapters || []).map((c) => `Ch.${c}`).join(", ")}</span>
              </div>
              <strong style="display:block;margin-top:6px;font-size:15px">${escapeHtml(t.vi)}</strong>
              <div style="font-size:12.5px;color:var(--ink-muted);margin-bottom:6px">${escapeHtml(t.en)}</div>
              <div style="font-size:12px;color:var(--ink-secondary)">${escapeHtml((t.context || "").slice(0, 150))}${(t.context || "").length > 150 ? "…" : ""}</div>
            </div>`
            )
            .join("")}
        </div>
      `;
    }

    el.view.innerHTML = `
      <section class="hero-header">
        <p class="eyebrow">DESIGN OF ANALOG CMOS INTEGRATED CIRCUITS · 2ND EDITION</p>
        <h1>Bản đồ Tri thức Cấu trúc & Tiến hóa Mạch CMOS Razavi</h1>
        <p>Tra cứu tức thì 68 thẻ nguyên lý 6 khối, 38 sơ đồ nguyên lý vector, 13 bảng kiểm bất biến độc lập tiến trình (90nm / 65nm / 45nm) và đồ thị nâng cấp cấu trúc mạch cho cả người đọc lẫn Codex CLI.</p>
        <div class="quick-chips">
          <span class="label">TRA NHANH:</span>
          <button type="button" class="chip-query" data-q="folded cascode">Folded-Cascode OTA</button>
          <button type="button" class="chip-query" data-q="guong dong dien ap thap">Gương dòng áp thấp LVCCML</button>
          <button type="button" class="chip-query" data-q="miller rhp zero">Miller &amp; RHP Zero</button>
          <button type="button" class="chip-query" data-q="middlebrook stb">Middlebrook &amp; Spectre STB</button>
          <button type="button" class="chip-query" data-q="bandgap">Bandgap &amp; Sub-1V</button>
          <button type="button" class="chip-query" data-q="lay mau tam day">Lấy mẫu tấm đáy</button>
          <button type="button" class="chip-query" data-q="pelgrom">Định luật Pelgrom</button>
        </div>
      </section>

      ${glossaryStrip}

      <div class="section-bar">
        <h2>Thẻ Tri thức Kỹ thuật${escapeHtml(domLabel)}${escapeHtml(chLabel)}</h2>
        <span class="meta">Hiển thị <strong>${nodes.length}</strong> / ${(state.router.nodes || []).length} thẻ</span>
      </div>

      ${
        nodes.length === 0
          ? `<div class="status-card"><h3>Không có thẻ khớp bộ lọc hiện tại</h3><p>Hãy thử gõ tiếng Việt không dấu (ví dụ: <code>bu tan so</code>, <code>ghep cheo</code>), tên mạch tiếng Anh hoặc bấm Đặt lại bộ lọc.</p></div>`
          : `<div class="node-grid">
              ${nodes
                .map((n) => {
                  const refs = (n.razavi_refs || [])
                    .slice(0, 2)
                    .map((r) => `Ch.${r.chapter}${r.section ? ` §${r.section}` : ""}`)
                    .join(" · ");
                  const outCount = (state.adjOut.get(n.id) || []).length;
                  const inCount = (state.adjIn.get(n.id) || []).length;
                  return `
                    <article class="node-card" data-open-node="${escapeHtml(n.id)}" tabindex="0" role="link" aria-label="${escapeHtml(n.title_vi)}">
                      <div class="card-topline">
                        <span class="badge ${kindBadgeClass(n.kind)}">${escapeHtml(n.kind)}</span>
                        <span class="badge badge-neutral">${escapeHtml(refs || n.domain)}</span>
                      </div>
                      <h3>${escapeHtml(n.title_vi)}</h3>
                      <p class="en-sub">${escapeHtml(n.title_en)}</p>
                      <p class="summary">${escapeHtml(n.summary)}</p>
                      <div class="card-footer">
                        <code>${escapeHtml(n.id)}</code>
                        <span>${inCount + outCount} liên kết đồ thị →</span>
                      </div>
                    </article>
                  `;
                })
                .join("")}
            </div>`
      }
    `;

    for (const chip of el.view.querySelectorAll(".chip-query")) {
      chip.addEventListener("click", () => {
        setSearchQuery(chip.dataset.q || "");
      });
    }
    const jumpGlossary = document.getElementById("jump-all-glossary");
    if (jumpGlossary) {
      jumpGlossary.addEventListener("click", () => {
        state.mode = "glossary";
        renderActiveView();
      });
    }
    bindNodeCardClicks(el.view);
  }

  function bindNodeCardClicks(root) {
    for (const card of root.querySelectorAll("[data-open-node]")) {
      const open = () => {
        const nid = card.getAttribute("data-open-node");
        if (nid) location.hash = `#node/${nid}`;
      };
      card.addEventListener("click", open);
      card.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          open();
        }
      });
    }
  }

  // Markdown + KaTeX Renderer (protects math spans before HTML escaping)
  function renderMathToken(tex, displayMode) {
    const cleanTex = tex.trim();
    if (window.katex && typeof window.katex.renderToString === "function") {
      try {
        return window.katex.renderToString(cleanTex, {
          displayMode,
          throwOnError: false,
          strict: "ignore",
        });
      } catch (_err) {
        // Fallback below
      }
    }
    return `<span class="math-fallback">${escapeHtml(displayMode ? `$$${cleanTex}$$` : `$${cleanTex}$`)}</span>`;
  }

  function renderMarkdownToHtml(mdBody) {
    const mathStore = [];
    const codeStore = [];

    // 1. Extract fenced code blocks first
    let working = mdBody.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_m, lang, code) => {
      const idx = codeStore.length;
      codeStore.push({ lang: lang || "text", code });
      return `\u0000CODEBLOCK_${idx}\u0000`;
    });

    // 2. Extract inline backtick code spans so `$` inside code is untouched
    const inlineCodeStore = [];
    working = working.replace(/`([^`\n]+)`/g, (_m, code) => {
      const idx = inlineCodeStore.length;
      inlineCodeStore.push(code);
      return `\u0000INLINECODE_${idx}\u0000`;
    });

    // 3. Extract display math $$...$$
    working = working.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) => {
      const idx = mathStore.length;
      mathStore.push({ tex, display: true });
      return `\u0000MATH_${idx}\u0000`;
    });

    // 4. Extract inline math $...$
    working = working.replace(/(?<!\\)\$([^\n$]+?)(?<!\\)\$/g, (_m, tex) => {
      const idx = mathStore.length;
      mathStore.push({ tex, display: false });
      return `\u0000MATH_${idx}\u0000`;
    });

    // Helper for inline formatting
    function formatInline(rawLine) {
      let s = escapeHtml(rawLine);

      // Images ![alt](url)
      s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, src) => {
        const resolved = src.includes("diagrams/") ? resolveDiagramUrl(src) : src;
        return `<figure class="md-diagram" data-zoom-svg="${escapeHtml(resolved)}" data-zoom-title="${escapeHtml(alt)}"><img src="${escapeHtml(resolved)}" alt="${escapeHtml(alt)}" loading="lazy"><figcaption>${escapeHtml(alt)} · Nhấp để phóng to sơ đồ vector</figcaption></figure>`;
      });

      // Links [text](url)
      s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, href) => {
        if (href.startsWith("#")) {
          return `<a href="${escapeHtml(href)}">${label}</a>`;
        }
        return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener">${label}</a>`;
      });

      // Bold & Italic
      s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");

      // Semantic Invariant & Trap tags [INV-...] / [TRAP-...]
      s = s.replace(/\[(INV-[A-Za-z0-9_-]+)\]/g, '<span class="badge badge-inv">$1</span>');
      s = s.replace(/\[(TRAP-[A-Za-z0-9_-]+)\]/g, '<span class="badge badge-trap">$1</span>');

      // Restore inline code spans (linking canonical node IDs!)
      s = s.replace(/\u0000INLINECODE_(\d+)\u0000/g, (_m, idxStr) => {
        const rawCode = inlineCodeStore[Number(idxStr)] || "";
        const trimmed = rawCode.trim();
        if (state.nodeMap.has(trimmed)) {
          return `<a class="node-ref-pill" href="#node/${escapeHtml(trimmed)}" title="Mở thẻ ${escapeHtml(trimmed)}">${escapeHtml(trimmed)} →</a>`;
        }
        return `<code>${escapeHtml(rawCode)}</code>`;
      });

      // Restore math tokens
      s = s.replace(/\u0000MATH_(\d+)\u0000/g, (_m, idxStr) => {
        const item = mathStore[Number(idxStr)];
        if (!item) return "";
        const rendered = renderMathToken(item.tex, item.display);
        return item.display ? `<div class="math-display">${rendered}</div>` : rendered;
      });

      return s;
    }

    const lines = working.split(/\r?\n/);
    const out = [];
    let i = 0;
    const headings = [];

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) {
        i++;
        continue;
      }

      // Standalone code block placeholder
      const cbMatch = trimmed.match(/^\u0000CODEBLOCK_(\d+)\u0000$/);
      if (cbMatch) {
        const cb = codeStore[Number(cbMatch[1])];
        out.push(`<pre data-lang="${escapeHtml(cb.lang)}"><code>${escapeHtml(cb.code.replace(/\n$/, ""))}</code></pre>`);
        i++;
        continue;
      }

      // Standalone display math placeholder
      const dmMatch = trimmed.match(/^\u0000MATH_(\d+)\u0000$/);
      if (dmMatch) {
        const item = mathStore[Number(dmMatch[1])];
        out.push(`<div class="math-display">${renderMathToken(item.tex, true)}</div>`);
        i++;
        continue;
      }

      // Headings
      const hMatch = line.match(/^(#{1,4})\s+(.+)$/);
      if (hMatch) {
        const level = Math.min(4, hMatch[1].length);
        const rawTitle = hMatch[2].trim();
        const hid = `sec-${headings.length + 1}`;
        if (level === 2) {
          headings.push({ id: hid, text: rawTitle.replace(/\*\*/g, "") });
        }
        out.push(`<h${level} id="${hid}">${formatInline(rawTitle)}</h${level}>`);
        i++;
        continue;
      }

      // Horizontal rule
      if (/^---+$/.test(trimmed) || /^\*\*\*+$/.test(trimmed)) {
        out.push("<hr>");
        i++;
        continue;
      }

      // Table block
      if (trimmed.startsWith("|") && i + 1 < lines.length && /^\s*\|[\s:-]+\|/.test(lines[i + 1])) {
        const splitRow = (r) =>
          r
            .trim()
            .replace(/^\|/, "")
            .replace(/\|$/, "")
            .split("|")
            .map((c) => formatInline(c.trim()));
        const headers = splitRow(lines[i]);
        i += 2; // Skip separator row
        const bodyRows = [];
        while (i < lines.length && lines[i].trim().startsWith("|")) {
          bodyRows.push(splitRow(lines[i]));
          i++;
        }
        out.push(
          `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${bodyRows
            .map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`)
            .join("")}</tbody></table>`
        );
        continue;
      }

      // Blockquote
      if (trimmed.startsWith(">")) {
        const bqLines = [];
        while (i < lines.length && lines[i].trim().startsWith(">")) {
          bqLines.push(lines[i].trim().replace(/^>\s?/, ""));
          i++;
        }
        out.push(`<blockquote>${bqLines.map((l) => `<p>${formatInline(l)}</p>`).join("")}</blockquote>`);
        continue;
      }

      // Unordered or Ordered Lists
      const ulMatch = line.match(/^\s*[-*]\s+(.+)$/);
      const olMatch = line.match(/^\s*\d+\.\s+(.+)$/);
      if (ulMatch || olMatch) {
        const isOrdered = Boolean(olMatch);
        const tag = isOrdered ? "ol" : "ul";
        const items = [];
        const itemRegex = isOrdered ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*]\s+(.+)$/;
        while (i < lines.length) {
          const m = lines[i].match(itemRegex);
          if (m) {
            items.push(m[1]);
            i++;
          } else if (lines[i].startsWith("  ") && items.length > 0 && lines[i].trim()) {
            items[items.length - 1] += " " + lines[i].trim();
            i++;
          } else {
            break;
          }
        }
        out.push(`<${tag}>${items.map((it) => `<li>${formatInline(it)}</li>`).join("")}</${tag}>`);
        continue;
      }

      // Paragraph
      const pLines = [trimmed];
      i++;
      while (
        i < lines.length &&
        lines[i].trim() &&
        !/^(#{1,4}\s|```|\u0000CODEBLOCK_|\u0000MATH_|>\s|\s*[-*]\s|\s*\d+\.\s|\|)/.test(lines[i].trim())
      ) {
        pLines.push(lines[i].trim());
        i++;
      }
      out.push(`<p>${formatInline(pLines.join(" "))}</p>`);
    }

    return { html: out.join("\n"), headings };
  }

  function stripFrontmatter(rawMd) {
    const lines = rawMd.split(/\r?\n/);
    if (lines[0]?.trim() !== "---") return rawMd;
    for (let i = 1; i < lines.length; i++) {
      if (lines[i].trim() === "---") {
        // Also strip redundant embedded diagram if already shown in top schematic viewer?
        // Keeping it in Section 1 is great because readers see it right in context too!
        return lines.slice(i + 1).join("\n");
      }
    }
    return rawMd;
  }

  // Interactive Pan/Zoom SVG Neighborhood Graph Builder
  function mountInteractiveGraph(viewportEl, inspectorEl, centerNodeId) {
    let panX = 0;
    let panY = 0;
    let scale = 1;
    let dragging = false;
    let startX = 0;
    let startY = 0;

    const nodesToDraw = [];
    const edgesToDraw = [];

    if (centerNodeId) {
      // Ego-graph around centerNodeId
      const center = state.nodeMap.get(centerNodeId);
      const inEdges = state.adjIn.get(centerNodeId) || [];
      const outEdges = state.adjOut.get(centerNodeId) || [];

      const leftIds = Array.from(new Set(inEdges.map((e) => e.from))).slice(0, 8);
      const rightIds = Array.from(new Set(outEdges.map((e) => e.to).filter((id) => !leftIds.includes(id)))).slice(0, 8);

      const pos = new Map();
      pos.set(centerNodeId, { x: 430, y: 195, role: "center", node: center });

      leftIds.forEach((id, idx) => {
        const y = 48 + ((idx + 0.5) * 295) / Math.max(1, leftIds.length);
        pos.set(id, { x: 135, y, role: "in", node: state.nodeMap.get(id) });
      });
      rightIds.forEach((id, idx) => {
        const y = 48 + ((idx + 0.5) * 295) / Math.max(1, rightIds.length);
        pos.set(id, { x: 725, y, role: "out", node: state.nodeMap.get(id) });
      });

      for (const [id, info] of pos.entries()) {
        if (info.node) nodesToDraw.push({ id, ...info });
      }
      for (const e of [...inEdges, ...outEdges]) {
        if (pos.has(e.from) && pos.has(e.to)) {
          edgesToDraw.push({ edge: e, p1: pos.get(e.from), p2: pos.get(e.to) });
        }
      }
    } else {
      // Full 7-layer architecture graph!
      const domains = (state.router.domains || []).map((d) => d.id);
      const pos = new Map();
      domains.forEach((domId, colIdx) => {
        const domNodes = (state.router.nodes || []).filter((n) => n.domain === domId);
        const x = 130 + colIdx * 235;
        domNodes.forEach((n, rowIdx) => {
          const y = 65 + rowIdx * 62;
          pos.set(n.id, { x, y, role: "global", node: n });
          nodesToDraw.push({ id: n.id, x, y, role: "global", node: n });
        });
      });
      for (const e of state.edges) {
        if (pos.has(e.from) && pos.has(e.to)) {
          edgesToDraw.push({ edge: e, p1: pos.get(e.from), p2: pos.get(e.to) });
        }
      }
      scale = 0.66;
      panX = 16;
      panY = 12;
    }

    const defs = Object.entries(EDGE_COLORS)
      .map(
        ([rel, col]) => `
        <marker id="arrow-${rel}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" fill="${col}"></path>
        </marker>`
      )
      .join("");

    const edgePaths = edgesToDraw
      .map((item, idx) => {
        const { edge, p1, p2 } = item;
        const col = EDGE_COLORS[edge.rel] || "#5e6266";
        const dx = p2.x - p1.x;
        const x1 = p1.x + (dx >= 0 ? 84 : -84);
        const x2 = p2.x + (dx >= 0 ? -88 : 88);
        const cx1 = x1 + dx * 0.36;
        const cx2 = x2 - dx * 0.36;
        const dash = edge.rel === "trades_off_with" ? 'stroke-dasharray="5,4"' : "";
        const midX = (x1 + x2) / 2;
        const midY = (p1.y + p2.y) / 2 - 5;
        return `
          <g class="g-edge" data-edge-idx="${idx}" style="cursor:pointer">
            <path d="M ${x1} ${p1.y} C ${cx1} ${p1.y}, ${cx2} ${p2.y}, ${x2} ${p2.y}" fill="none" stroke="${col}" stroke-width="1.8" ${dash} marker-end="url(#arrow-${edge.rel})"></path>
            ${
              centerNodeId
                ? `<text x="${midX}" y="${midY}" text-anchor="middle" font-size="10" font-family="Consolas,monospace" fill="${col}">${escapeHtml(edge.rel)}</text>`
                : ""
            }
          </g>
        `;
      })
      .join("");

    const nodeBoxes = nodesToDraw
      .map((item) => {
        const n = item.node;
        const isCenter = item.role === "center";
        const stroke = isCenter ? "#16594f" : n.kind === "topology" ? "#1f6c9f" : n.kind === "technique" ? "#956400" : "#346538";
        const fill = isCenter ? "#e7f1ee" : "#ffffff";
        const shortLabel = (n.title_en || n.id).slice(0, 25) + ((n.title_en || n.id).length > 25 ? "…" : "");
        const chTag = n.chapters?.[0] ? `Ch.${n.chapters[0]}` : n.kind;
        return `
          <g class="g-node" data-node-id="${escapeHtml(item.id)}" transform="translate(${item.x - 84}, ${item.y - 21})" style="cursor:pointer">
            <rect width="168" height="42" rx="7" fill="${fill}" stroke="${stroke}" stroke-width="${isCenter ? 2.3 : 1.3}"></rect>
            <text x="8" y="16" font-size="10" font-family="Consolas,monospace" fill="#5e6266">${escapeHtml(chTag)} · ${escapeHtml(n.kind)}</text>
            <text x="8" y="31" font-size="11.5" font-weight="${isCenter ? "700" : "600"}" fill="#16181a">${escapeHtml(shortLabel)}</text>
          </g>
        `;
      })
      .join("");

    viewportEl.innerHTML = `
      <svg class="graph-svg" viewBox="0 0 860 390" role="img" aria-label="Đồ thị liên kết và nâng cấp cấu trúc mạch">
        <defs>${defs}</defs>
        <g id="graph-pan-layer" transform="translate(${panX},${panY}) scale(${scale})">
          ${edgePaths}
          ${nodeBoxes}
        </g>
      </svg>
    `;

    const panLayer = viewportEl.querySelector("#graph-pan-layer");
    const applyTransform = () => {
      panLayer.setAttribute("transform", `translate(${panX},${panY}) scale(${scale})`);
    };

    viewportEl.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        const factor = ev.deltaY < 0 ? 1.1 : 0.9;
        scale = Math.min(2.6, Math.max(0.35, scale * factor));
        applyTransform();
      },
      { passive: false }
    );

    viewportEl.addEventListener("mousedown", (ev) => {
      if (ev.target.closest(".g-node")) return;
      dragging = true;
      startX = ev.clientX - panX;
      startY = ev.clientY - panY;
    });

    window.addEventListener("mousemove", (ev) => {
      if (!dragging) return;
      panX = ev.clientX - startX;
      panY = ev.clientY - startY;
      applyTransform();
    });

    window.addEventListener("mouseup", () => {
      dragging = false;
    });

    for (const gNode of viewportEl.querySelectorAll(".g-node")) {
      gNode.addEventListener("click", () => {
        const targetId = gNode.getAttribute("data-node-id");
        if (targetId) location.hash = `#node/${targetId}`;
      });
    }

    for (const gEdge of viewportEl.querySelectorAll(".g-edge")) {
      const showEdgeInfo = () => {
        const item = edgesToDraw[Number(gEdge.getAttribute("data-edge-idx"))];
        if (!item || !inspectorEl) return;
        const { edge } = item;
        inspectorEl.innerHTML = `
          <div>
            <strong>${escapeHtml(edge.from)}</strong> → <code>${escapeHtml(edge.rel)}</code> → <strong>${escapeHtml(edge.to)}</strong>
            ${edge.when ? ` · <span>Khi: ${escapeHtml(edge.when)}</span>` : ""}
            ${edge.cost ? ` · <span>Đánh đổi: ${escapeHtml(edge.cost)}</span>` : ""}
            ${edge.ref ? ` <span>(${escapeHtml(edge.ref)})</span>` : ""}
          </div>
        `;
      };
      gEdge.addEventListener("mouseenter", showEdgeInfo);
      gEdge.addEventListener("click", showEdgeInfo);
    }
  }

  async function renderNodeDetailView(nodeId) {
    const node = state.nodeMap.get(nodeId);
    if (!node) {
      el.view.innerHTML = `<div class="status-card"><h2>Không tìm thấy thẻ <code>${escapeHtml(nodeId)}</code></h2><p><a href="#overview">← Quay lại danh mục 68 thẻ tri thức</a></p></div>`;
      return;
    }

    let mdRaw = state.markdownCache.get(nodeId);
    if (!mdRaw) {
      el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG TẢI THẺ CHI TIẾT</p><h2>${escapeHtml(node.title_vi)}</h2></div>`;
      const res = await fetch(kbUrl(node.raw_rel_path || node.path));
      mdRaw = res.ok ? await res.text() : "## Không thể tải nội dung thẻ.";
      state.markdownCache.set(nodeId, mdRaw);
    }

    // Load linked checklists in parallel
    const linkedChecklists = [];
    for (const cid of node.checklists || []) {
      if (!state.checklistCache.has(cid)) {
        try {
          const r = await fetch(kbUrl(`checklists/${cid}.json`));
          if (r.ok) state.checklistCache.set(cid, await r.json());
        } catch (_err) {
          // ignore
        }
      }
      if (state.checklistCache.has(cid)) linkedChecklists.push(state.checklistCache.get(cid));
    }

    const bodyMd = stripFrontmatter(mdRaw);
    const { html: renderedHtml, headings } = renderMarkdownToHtml(bodyMd);
    const diagUrl = resolveDiagramUrl(node.diagram);
    const refsStr = (node.razavi_refs || [])
      .map((r) => `Ch.${r.chapter}${r.section ? ` §${r.section}` : ""}${r.pages ? ` (p.${r.pages})` : ""}`)
      .join(" · ");

    const rolesEntries = Object.entries(node.roles || {});
    const outEdges = state.adjOut.get(nodeId) || [];
    const inEdges = state.adjIn.get(nodeId) || [];

    el.view.innerHTML = `
      <div class="reader-layout">
        <div class="reader-main">
          <nav class="reader-breadcrumb" aria-label="Đường dẫn">
            <a href="#overview">← Danh mục Thẻ</a>
            <span>/</span>
            <a href="#domain/${escapeHtml(node.domain)}">${escapeHtml(node.domain)}</a>
            <span>/</span>
            <code>${escapeHtml(node.id)}</code>
          </nav>

          <header class="reader-header">
            <div class="card-topline">
              <div style="display:flex;gap:6px;flex-wrap:wrap">
                <span class="badge ${kindBadgeClass(node.kind)}">${escapeHtml(node.kind)}</span>
                <span class="badge badge-neutral">PDK-Agnostic · 90nm / 65nm / 45nm</span>
                ${refsStr ? `<span class="badge badge-neutral">${escapeHtml(refsStr)}</span>` : ""}
              </div>
            </div>
            <h1>${escapeHtml(node.title_vi)}</h1>
            <p class="en-title">${escapeHtml(node.title_en)}</p>
            <p class="reader-summary">${escapeHtml(node.summary)}</p>
            <div class="reader-actions">
              <button type="button" class="btn-primary" id="btn-copy-link">Sao chép liên kết #node</button>
              <button type="button" class="btn-subtle" id="btn-copy-cli">Chép lệnh Codex (kb_fetch.py)</button>
              <a class="btn-subtle" style="padding:6px 11px;border:1px solid var(--border-hairline);border-radius:5px;text-decoration:none" href="${escapeHtml(kbUrl(node.raw_rel_path || node.path))}" target="_blank" rel="noopener">Mở Markdown gốc (.md)</a>
            </div>
          </header>

          ${
            diagUrl
              ? `
            <section class="schematic-panel" id="sec-schematic">
              <div class="panel-bar">
                <span>SƠ ĐỒ NGUYÊN LÝ VECTOR · ${escapeHtml(node.diagram.split("/").pop())}</span>
                <button type="button" class="btn-subtle" id="btn-zoom-main-svg">Phóng to toàn màn hình</button>
              </div>
              <div class="schematic-stage" id="main-schematic-stage" title="Nhấp để phóng to sơ đồ">
                <img src="${escapeHtml(diagUrl)}" alt="${escapeHtml(node.title_vi)}">
              </div>
            </section>`
              : ""
          }

          <section class="graph-panel" id="sec-ego-graph">
            <div class="panel-bar">
              <span>ĐỒ THỊ TIẾN HÓA &amp; PHỤ THUỘC LÂN CẬN (${inEdges.length} vào · ${outEdges.length} ra · Cuộn chuột để Zoom, Nhấp Node để chuyển mạch)</span>
              <button type="button" class="link-btn" id="btn-open-full-graph">Mở toàn đồ thị 68 thẻ →</button>
            </div>
            <div class="graph-viewport" id="ego-graph-viewport"></div>
            <div class="graph-inspector" id="ego-graph-inspector">
              <span>Rê chuột lên mũi tên để xem điều kiện nâng cấp (<code>when</code>) và cái giá đánh đổi (<code>cost</code>).</span>
              <div class="graph-legend">
                <span><i class="legend-dot" style="background:#1f6c9f"></i>upgrades_to</span>
                <span><i class="legend-dot" style="background:#346538"></i>fixes</span>
                <span><i class="legend-dot" style="background:#956400"></i>compensated_by</span>
                <span><i class="legend-dot" style="background:#9f2f2d"></i>trades_off_with</span>
              </div>
            </div>
          </section>

          <section class="meta-bento">
            <div class="bento-box">
              <h3>Vai trò Cấu trúc Từng Nhánh (Structural Roles)</h3>
              ${
                rolesEntries.length
                  ? `<ul class="kv-list">${rolesEntries
                      .map(([k, v]) => `<li><code>${escapeHtml(k)}</code> ${escapeHtml(v)}</li>`)
                      .join("")}</ul>`
                  : `<p class="meta">Áp dụng chung toàn mạch.</p>`
              }
            </div>
            <div class="bento-box">
              <h3>Triệu chứng Giải quyết &amp; Giới hạn Vật lý</h3>
              <div style="margin-bottom:10px">
                <span style="font-size:11.5px;color:var(--ink-muted);display:block;margin-bottom:4px">Giải quyết triệu chứng:</span>
                <div class="tag-cloud">
                  ${(node.symptoms_addressed || [])
                    .map((s) => `<button type="button" class="tag-btn" data-symptom="${escapeHtml(s)}">${escapeHtml(s)}</button>`)
                    .join("")}
                </div>
              </div>
              <div>
                <span style="font-size:11.5px;color:var(--ink-muted);display:block;margin-bottom:4px">Trần vật lý / Đánh đổi:</span>
                <div class="tag-cloud">
                  ${(node.limitations || [])
                    .map((s) => `<span class="badge badge-error" style="text-transform:none;font-family:var(--font-mono)">${escapeHtml(s)}</span>`)
                    .join("")}
                </div>
              </div>
            </div>
          </section>

          <article class="markdown-body" id="node-markdown-article">
            ${renderedHtml}
          </article>

          ${
            linkedChecklists.length > 0
              ? `
            <section style="margin-top:22px" id="sec-node-checklists">
              <div class="section-bar">
                <h2>Bảng kiểm Bất biến Cấu trúc Áp dụng (${linkedChecklists.length})</h2>
                <span class="meta">Đúng cho mọi tiến trình 90nm / 65nm / 45nm</span>
              </div>
              ${linkedChecklists.map((cl) => renderChecklistCardHtml(cl)).join("")}
            </section>`
              : ""
          }
        </div>

        <aside class="reader-toc" aria-label="Mục lục trên trang">
          <h4>TRÊN THẺ NÀY</h4>
          <ul class="toc-links">
            ${diagUrl ? `<li><a href="#sec-schematic">Sơ đồ nguyên lý SVG</a></li>` : ""}
            <li><a href="#sec-ego-graph">Đồ thị nâng cấp lân cận</a></li>
            ${headings.map((h) => `<li><a href="#${h.id}">${escapeHtml(h.text)}</a></li>`).join("")}
            ${linkedChecklists.length ? `<li><a href="#sec-node-checklists">Bảng kiểm cấu trúc (${linkedChecklists.length})</a></li>` : ""}
          </ul>
        </aside>
      </div>
    `;

    // Mount neighborhood SVG graph
    mountInteractiveGraph(
      document.getElementById("ego-graph-viewport"),
      document.getElementById("ego-graph-inspector"),
      nodeId
    );

    // Bind schematic lightbox zoom
    const openMainSvg = () => openSvgModal(diagUrl, node.title_vi);
    document.getElementById("btn-zoom-main-svg")?.addEventListener("click", openMainSvg);
    document.getElementById("main-schematic-stage")?.addEventListener("click", openMainSvg);
    for (const fig of el.view.querySelectorAll("[data-zoom-svg]")) {
      fig.addEventListener("click", () => {
        openSvgModal(fig.getAttribute("data-zoom-svg"), fig.getAttribute("data-zoom-title") || node.title_vi);
      });
    }

    document.getElementById("btn-open-full-graph")?.addEventListener("click", () => {
      location.hash = "#graph";
    });

    document.getElementById("btn-copy-link")?.addEventListener("click", () => {
      navigator.clipboard?.writeText(location.href);
      showToast("Đã sao chép liên kết sâu của thẻ!");
    });

    document.getElementById("btn-copy-cli")?.addEventListener("click", () => {
      const cmd = `python /home/disk/eda/references/SKILL-ANALOG/tools/kb_fetch.py ${node.id}`;
      navigator.clipboard?.writeText(cmd);
      showToast("Đã chép lệnh kb_fetch.py cho Codex CLI!");
    });

    for (const symBtn of el.view.querySelectorAll("[data-symptom]")) {
      symBtn.addEventListener("click", () => {
        const sym = symBtn.getAttribute("data-symptom") || "";
        state.mode = "nodes";
        location.hash = "#overview";
        setSearchQuery(sym);
      });
    }

    for (const tocLink of el.view.querySelectorAll(".toc-links a")) {
      tocLink.addEventListener("click", (ev) => {
        const href = tocLink.getAttribute("href");
        if (href && href.startsWith("#sec-")) {
          ev.preventDefault();
          document.getElementById(href.slice(1))?.scrollIntoView({ behavior: "smooth" });
        }
      });
    }

    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function renderGlobalGraphView() {
    el.view.innerHTML = `
      <section class="hero-header" style="margin-bottom:16px;padding-bottom:14px">
        <p class="eyebrow">TOPOLOGY EVOLUTION &amp; DEPENDENCY GRAPH</p>
        <h1>Đồ thị Tiến hóa Toàn cục 7 Tầng (Ch.01 – Ch.19)</h1>
        <p>Cuộn chuột để phóng to/thu nhỏ, kéo nền để di chuyển, bấm vào bất kỳ khối mạch nào để mở thẻ nguyên lý 6 khối chi tiết.</p>
      </section>
      <section class="graph-panel">
        <div class="panel-bar">
          <span>${(state.router.nodes || []).length} Nodes · ${state.edges.length} Directed Engineering Edges</span>
          <div class="graph-legend">
            ${Object.entries(EDGE_COLORS)
              .map(([rel, col]) => `<span><i class="legend-dot" style="background:${col}"></i>${escapeHtml(rel)}</span>`)
              .join("")}
          </div>
        </div>
        <div class="graph-viewport full-height" id="global-graph-viewport"></div>
        <div class="graph-inspector" id="global-graph-inspector">
          <span>Nhấp hoặc rê chuột lên cạnh đồ thị để đọc điều kiện kỹ thuật và chi phí đánh đổi theo Bát giác Thiết kế.</span>
        </div>
      </section>
    `;
    mountInteractiveGraph(
      document.getElementById("global-graph-viewport"),
      document.getElementById("global-graph-inspector"),
      null
    );
  }

  function renderChecklistCardHtml(cl) {
    const checks = cl.checks || [];
    return `
      <article class="checklist-card" id="cl-${escapeHtml(cl.checklist_id)}">
        <div class="card-topline">
          <span class="badge badge-inv">CHECKLIST · ${escapeHtml(cl.checklist_id)}</span>
          <span class="badge badge-neutral">${checks.length} phép kiểm bất biến</span>
        </div>
        <h3 style="margin:8px 0 4px;font-size:18px">${escapeHtml(cl.title_vi)}</h3>
        <p style="margin:0 0 12px;font-size:12.5px;color:var(--ink-muted)">Áp dụng cho: ${escapeHtml(
          Array.isArray(cl.applies_to) ? cl.applies_to.join(", ") : cl.applies_to || ""
        )}</p>
        <div>
          ${checks
            .map(
              (c) => `
            <div class="check-row">
              <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:4px">
                <span class="badge ${c.severity === "error" ? "badge-error" : "badge-technique"}">${escapeHtml(c.severity || "error")}</span>
                <span class="badge badge-neutral">${escapeHtml(c.method || "structural")}</span>
                <code>${escapeHtml(c.id)}</code>
                <strong>${escapeHtml(c.name)}</strong>
              </div>
              <div style="font-size:13.5px;margin:4px 0"><strong>Bất biến:</strong> <code>${escapeHtml(c.invariant || "")}</code></div>
              <div style="font-size:13.5px;color:var(--ink-secondary);margin:4px 0">${escapeHtml(c.why_vi || "")}</div>
              ${
                c.cadence_check
                  ? `<div style="font-size:12.5px;background:var(--bg-canvas);padding:7px 10px;border-radius:5px;margin-top:6px"><strong>Kiểm chứng Cadence / Spectre:</strong> ${escapeHtml(c.cadence_check)}</div>`
                  : ""
              }
              ${
                (c.related_nodes || []).length
                  ? `<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:5px">${c.related_nodes
                      .filter((nid) => state.nodeMap.has(nid))
                      .map((nid) => `<a class="node-ref-pill" href="#node/${escapeHtml(nid)}">${escapeHtml(nid)} →</a>`)
                      .join("")}</div>`
                  : ""
              }
            </div>`
            )
            .join("")}
        </div>
      </article>
    `;
  }

  async function renderChecklistsView() {
    const list = state.router.checklists || [];
    el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG TẢI 13 BẢNG KIỂM CẤU TRÚC</p><h2>Đang đồng bộ quy tắc bất biến…</h2></div>`;

    await Promise.all(
      list.map(async (item) => {
        if (!state.checklistCache.has(item.checklist_id)) {
          const r = await fetch(kbUrl(item.path));
          if (r.ok) state.checklistCache.set(item.checklist_id, await r.json());
        }
      })
    );

    const qFold = foldAscii(state.query);
    const loaded = list
      .map((item) => state.checklistCache.get(item.checklist_id))
      .filter(Boolean)
      .filter((cl) => {
        if (state.activeChecklistId && cl.checklist_id !== state.activeChecklistId) return true;
        if (!qFold) return true;
        const blob = foldAscii(JSON.stringify(cl));
        return blob.includes(qFold);
      });

    el.view.innerHTML = `
      <section class="hero-header">
        <p class="eyebrow">PDK-AGNOSTIC STRUCTURAL VERIFICATION</p>
        <h1>13 Bảng kiểm Bất biến Cấu trúc (90nm / 65nm / 45nm)</h1>
        <p>Tách biệt hoàn toàn quy luật vật lý bất biến (KCL nút gập, khoảng hở bão hòa $V_{DS,\\min}$, ổn định vòng hồi tiếp STB, khởi động Bandgap, lấy mẫu tấm đáy, Common-Centroid) khỏi thông số riêng của từng bộ PDK.</p>
      </section>
      ${loaded.map((cl) => renderChecklistCardHtml(cl)).join("")}
    `;

    if (state.activeChecklistId) {
      document.getElementById(`cl-${state.activeChecklistId}`)?.scrollIntoView({ behavior: "smooth" });
    }
  }

  async function renderGlossaryView() {
    if (!state.glossary) {
      el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG NẠP KHO THUẬT NGỮ CLB</p><h2>Đang tải 2.200 mục T001–T2200…</h2></div>`;
      await ensureGlossaryLoaded();
    }

    const qRaw = state.query.trim();
    const qFold = foldAscii(qRaw);
    const qTokens = qFold ? qFold.split(/\s+/).filter(Boolean) : [];
    const codeMatch = qRaw.match(/^t0*(\d+)$/i);

    const matches = [];
    for (const term of state.glossary || []) {
      if (state.filterChapter !== null && !(term.chapters || []).includes(state.filterChapter)) continue;
      if (!qFold) {
        matches.push({ term, rank: 5 });
        continue;
      }
      if (codeMatch && Number(term.id.slice(1)) === Number(codeMatch[1])) {
        matches.push({ term, rank: 0 });
        continue;
      }
      const enF = foldAscii(term.en);
      const viF = foldAscii(term.vi);
      const key = term.search_key || `${enF} ${viF}`;
      if (enF === qFold || viF === qFold) matches.push({ term, rank: 1 });
      else if (enF.startsWith(qFold) || viF.startsWith(qFold)) matches.push({ term, rank: 2 });
      else if (enF.includes(qFold) || viF.includes(qFold)) matches.push({ term, rank: 3 });
      else if (qTokens.every((tok) => key.includes(tok))) matches.push({ term, rank: 4 });
    }

    matches.sort((a, b) => a.rank - b.rank || Number(a.term.id.slice(1)) - Number(b.term.id.slice(1)));
    const slice = matches.slice(0, state.glossaryLimit);

    el.view.innerHTML = `
      <section class="hero-header">
        <p class="eyebrow">CHUẨN DỊCH THUẬT CLB VI MẠCH · T001 – T2200</p>
        <h1>Kho 2.200 Thuật ngữ Song ngữ Anh – Việt Chuẩn hóa</h1>
        <p>Đồng bộ nguyên bản 2.134 mục đã hiệu đính của CLB Vi Mạch (Ch.01–Ch.12) cùng 66 thuật ngữ mở rộng chuẩn xác cho các chương Ch.13–Ch.19 (Switched-Capacitor, Pelgrom, VCO, PLL, Latch-Up, Layout &amp; LDO).</p>
      </section>
      <div class="section-bar">
        <h2>Kết quả tra cứu thuật ngữ${state.filterChapter ? ` · Chương ${state.filterChapter}` : ""}</h2>
        <span class="meta">Khớp <strong>${matches.length}</strong> mục (đang hiện ${slice.length})</span>
      </div>
      <div class="glossary-list">
        ${slice
          .map(
            ({ term }) => `
          <article class="glossary-item">
            <div class="glossary-top">
              <div>
                <span class="badge badge-neutral">${escapeHtml(term.id)}</span>
                ${term.curated_extension ? `<span class="badge badge-technique">Ch.13–19 Mở rộng</span>` : ""}
                <strong style="font-size:16.5px;margin-left:6px">${escapeHtml(term.vi)}</strong>
                <div style="font-size:13px;color:var(--ink-muted);margin-top:2px">${escapeHtml(term.en)}</div>
              </div>
              <button type="button" class="btn-subtle" data-copy-vi="${escapeHtml(term.vi)} (${escapeHtml(term.en)})">Chép thuật ngữ</button>
            </div>
            <p style="margin:8px 0 0;font-size:13px;color:var(--ink-secondary)">${escapeHtml(term.context || "")}</p>
          </article>`
          )
          .join("")}
      </div>
      ${
        matches.length > slice.length
          ? `<div style="margin-top:18px;text-align:center"><button type="button" class="btn-subtle" id="btn-more-glossary">Hiện thêm 50 thuật ngữ (${matches.length - slice.length} còn lại)</button></div>`
          : ""
      }
    `;

    for (const copyBtn of el.view.querySelectorAll("[data-copy-vi]")) {
      copyBtn.addEventListener("click", () => {
        navigator.clipboard?.writeText(copyBtn.getAttribute("data-copy-vi") || "");
        showToast("Đã chép thuật ngữ song ngữ!");
      });
    }
    document.getElementById("btn-more-glossary")?.addEventListener("click", () => {
      state.glossaryLimit += 50;
      renderGlossaryView();
    });
  }

  // Lightbox Modal Controls
  function openSvgModal(url, title) {
    if (!url) return;
    state.modalZoom = 1;
    el.modalTitle.textContent = title || "Schematic Viewer";
    el.modalOpenRaw.href = url;
    el.modalInner.style.transform = "scale(1)";
    el.modalInner.innerHTML = `<img src="${escapeHtml(url)}" alt="${escapeHtml(title)}">`;
    el.modal.hidden = false;
  }

  function closeSvgModal() {
    el.modal.hidden = true;
    el.modalInner.innerHTML = "";
  }

  function setSearchQuery(q) {
    state.query = q;
    el.search.value = q;
    el.clearSearch.hidden = !q;
    state.glossaryLimit = 40;
    if (state.mode === "detail" && q) {
      state.mode = "nodes";
    }
    renderActiveView();
  }

  // Hash Router (#node/<id>, #checklist/<id>, #domain/<id>, #chapter/<n>, #graph, #glossary)
  function applyRouteFromHash() {
    if (!state.router) return;
    const h = decodeURIComponent(location.hash || "").replace(/^#/, "");
    state.activeChecklistId = null;

    if (h.startsWith("node/")) {
      state.activeNodeId = h.slice(5).trim();
      state.mode = "detail";
    } else if (h.startsWith("checklist/")) {
      state.activeChecklistId = h.slice(10).trim();
      state.mode = "checklists";
    } else if (h === "checklists") {
      state.mode = "checklists";
    } else if (h.startsWith("domain/")) {
      state.filterDomain = h.slice(7).trim() || "all";
      state.mode = "nodes";
    } else if (h.startsWith("chapter/")) {
      const n = Number(h.slice(8));
      state.filterChapter = n >= 1 && n <= 19 ? n : null;
      state.mode = "nodes";
    } else if (h === "graph") {
      state.mode = "graph";
    } else if (h.startsWith("glossary")) {
      state.mode = "glossary";
      const sub = h.slice(9).trim();
      if (sub) {
        state.query = sub;
        el.search.value = sub;
        el.clearSearch.hidden = false;
      }
    } else {
      state.mode = "nodes";
      state.activeNodeId = null;
    }
    el.sidebar.classList.remove("is-open");
    renderActiveView();
  }

  // Global Event Listeners
  function bindGlobalEvents() {
    let debounceTimer = null;
    el.search.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        setSearchQuery(el.search.value);
      }, 90);
    });

    el.clearSearch.addEventListener("click", () => {
      setSearchQuery("");
      el.search.focus();
    });

    window.addEventListener("keydown", (ev) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") {
        ev.preventDefault();
        el.search.focus();
        el.search.select();
      } else if (ev.key === "Escape" && !el.modal.hidden) {
        closeSvgModal();
      }
    });

    for (const btn of el.modeTabs) {
      btn.addEventListener("click", () => {
        const m = btn.dataset.mode;
        if (m === "graph") location.hash = "#graph";
        else if (m === "checklists") location.hash = "#checklists";
        else if (m === "glossary") location.hash = "#glossary";
        else location.hash = "#overview";
      });
    }

    for (const btn of el.kindBtns) {
      btn.addEventListener("click", () => {
        state.filterKind = btn.dataset.kind || "all";
        if (state.mode === "detail") location.hash = "#overview";
        else renderActiveView();
      });
    }

    el.domainList.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-domain]");
      if (!btn) return;
      state.filterDomain = btn.getAttribute("data-domain") || "all";
      if (state.mode === "detail") location.hash = state.filterDomain === "all" ? "#overview" : `#domain/${state.filterDomain}`;
      else renderActiveView();
    });

    el.chapterGrid.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-chapter]");
      if (!btn) return;
      const ch = Number(btn.getAttribute("data-chapter"));
      state.filterChapter = state.filterChapter === ch ? null : ch;
      if (state.mode === "detail") location.hash = state.filterChapter ? `#chapter/${state.filterChapter}` : "#overview";
      else renderActiveView();
    });

    el.resetFilters.addEventListener("click", () => {
      state.filterDomain = "all";
      state.filterChapter = null;
      state.filterKind = "all";
      setSearchQuery("");
      if (state.mode === "detail") location.hash = "#overview";
    });

    el.sidebarToggle.addEventListener("click", () => {
      el.sidebar.classList.toggle("is-open");
    });

    // Theme switcher
    const savedTheme = localStorage.getItem("razavi-brain-theme");
    if (savedTheme === "dark" || savedTheme === "light") {
      document.documentElement.setAttribute("data-theme", savedTheme);
      el.iconSun.hidden = savedTheme !== "dark";
      el.iconMoon.hidden = savedTheme === "dark";
    }
    el.themeToggle.addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", cur);
      localStorage.setItem("razavi-brain-theme", cur);
      el.iconSun.hidden = cur !== "dark";
      el.iconMoon.hidden = cur === "dark";
    });

    // Modal zoom events
    el.modalClose.addEventListener("click", closeSvgModal);
    el.modal.addEventListener("click", (ev) => {
      if (ev.target === el.modal) closeSvgModal();
    });
    el.modalZoomIn.addEventListener("click", () => {
      state.modalZoom = Math.min(3.5, state.modalZoom + 0.25);
      el.modalInner.style.transform = `scale(${state.modalZoom})`;
    });
    el.modalZoomOut.addEventListener("click", () => {
      state.modalZoom = Math.max(0.5, state.modalZoom - 0.25);
      el.modalInner.style.transform = `scale(${state.modalZoom})`;
    });
    el.modalZoomReset.addEventListener("click", () => {
      state.modalZoom = 1;
      el.modalInner.style.transform = "scale(1)";
    });

    window.addEventListener("hashchange", applyRouteFromHash);
  }

  bindGlobalEvents();
  detectAndLoadCore()
    .then(() => {
      applyRouteFromHash();
      // Re-render math if KaTeX finishes loading slightly after initial DOM render
      window.addEventListener("load", () => {
        if (state.mode === "detail" && state.activeNodeId) {
          renderNodeDetailView(state.activeNodeId);
        }
      });
    })
    .catch((err) => {
      el.loadingBanner.innerHTML = `
        <p class="eyebrow">CHƯA BIÊN DỊCH CHỈ MỤC</p>
        <h2>Không thể nạp dữ liệu Bộ não Tri thức</h2>
        <p>${escapeHtml(err.message)}</p>
      `;
    });
})();
