/* Razavi CMOS Knowledge Brain v3 — 10-Domain Coordinate Graph, PMIC/AMS, 19-Chapter Navigator & Closed-Loop Cadence-Codex Explorer
 * Zero build dependencies. Works identically on GitHub Pages (./kb/*) and locally (../kb/*).
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

  const RAZAVI_CORE_DOMAINS = new Set([
    "foundations",
    "stages-and-mirrors",
    "dynamics-noise-feedback",
    "opamps-and-compensation",
    "references-and-biasing",
    "sampled-and-clocked",
    "nonideal-and-physical",
  ]);

  const DEFAULT_DESIGN_CYCLE = [
    { stage: 1, id: "1_spec_and_kb", title_vi: "1 · Tra cứu KB & Checklist", tool: "kb_lookup.py + checklists" },
    { stage: 2, id: "2_hierarchical_budget", title_vi: "2 · Phân bổ Spec & Giao tiếp", tool: "spec.json + blocks[]" },
    { stage: 3, id: "3_gmid_physics_sizing", title_vi: "3 · Định cỡ Vật lý gm/ID", tool: "gmid_lut.py (<5ms)" },
    { stage: 4, id: "4_schematic_and_veriloga", title_vi: "4 · Dựng OA & Verilog-A", tool: "ic617_live_bridge.il" },
    { stage: 5, id: "5_spectre_psf_audit", title_vi: "5 · Kiểm toán OP & STB/PSTB", tool: "cadence_exec + psf_audit.py" },
    { stage: 6, id: "6_pareto_optimization", title_vi: "6 · Độ nhạy & Tối ưu Pareto", tool: "sizing_opt.py" },
    { stage: 7, id: "7_pvt_mc_pex_signoff", title_vi: "7 · Nghiệm thu PVT / MC / PEX", tool: "psf_audit + CACE" },
  ];

  const TRACK_META = [
    { id: "laws", index: 0, label: "Track 1 · Vật lý & Định luật (Concept / Law)", short: "Laws & Physics", tint: "rgba(52, 101, 56, 0.045)" },
    { id: "topologies", index: 1, label: "Track 2 · Cấu trúc Mạch CMOS / PMIC / AMS (Topology)", short: "Topologies", tint: "rgba(31, 108, 159, 0.045)" },
    { id: "techniques", index: 2, label: "Track 3 · Định cỡ, Bù ổn định & Hệ thống (Technique)", short: "Techniques", tint: "rgba(149, 100, 0, 0.045)" },
    { id: "skills", index: 3, label: "Track 4 · Chu trình Tối ưu Khép kín Cadence IC617 / Spectre / GitHub Skills", short: "GitHub EDA Skills", tint: "rgba(91, 59, 140, 0.05)" },
  ];

  const state = {
    kbBase: "./kb",
    router: null,
    nodeMap: new Map(),
    edges: [],
    adjOut: new Map(),
    adjIn: new Map(),
    coords: null,
    coordsLoading: false,
    catalog: null,
    catalogLoading: false,
    glossary: null,
    glossaryLoading: false,
    checklistCache: new Map(),
    markdownCache: new Map(),
    mode: "nodes", // nodes | graph | coords | skills | checklists | glossary | detail
    activeNodeId: null,
    activeChecklistId: null,
    filterDomain: "all",
    filterChapter: null,
    filterKind: "all", // all | pmic | ams | razavi | skill | topology | law-concept | technique
    filterStage: null, // null | 1..7 (7-Stage Optimal Design Cycle)
    graphScope: "all", // all | razavi | pmic | ams | skill
    graphRel: "all",
    graphFocusNodeId: null,
    coordsTab: "sections", // sections | equations | index
    expandedChapters: new Set([1, 2, 3, 8, 9, 10, 12, 13, 15, 16, 19]),
    skillsTab: "all", // all | playbooks | repos
    skillsCategory: "all",
    diagTab: "all", // all | symptoms | checklists
    query: "",
    modalZoom: 1,
    glossaryLimit: 50,
    indexLimit: 80,
    eqLimit: 60,
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
    statSections: document.getElementById("stat-sections"),
    statRepos: document.getElementById("stat-repos"),
    statChecklists: document.getElementById("stat-checklists"),
    statGlossary: document.getElementById("stat-glossary"),
    releaseVer: document.getElementById("release-version"),
    rawIndexLink: document.getElementById("raw-index-link"),
    rawCoordsLink: document.getElementById("raw-coords-link"),
    rawCatalogLink: document.getElementById("raw-catalog-link"),
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
    }, 2300);
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
      .replace(/[^a-z0-9/+.:§()-]+/g, " ")
      .trim();
  }

  function foldWords(value) {
    return String(value ?? "")
      .replace(/đ/g, "d")
      .replace(/Đ/g, "D")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function kbUrl(relFromKb) {
    const clean = String(relFromKb || "").replace(/^\/+/, "").replace(/^kb\//, "");
    return `${state.kbBase}/${clean}`;
  }

  function resolveDiagramUrl(diagField) {
    if (!diagField) return "";
    const baseName = String(diagField).split("/").pop();
    return `${state.kbBase}/diagrams/${baseName}`;
  }

  function kindBadgeClass(kind) {
    if (kind === "topology") return "badge-topology";
    if (kind === "technique") return "badge-technique";
    if (kind === "skill") return "badge-skill";
    return "badge-law";
  }

  function isSkillNode(node) {
    return node.kind === "skill" || node.domain === "eda-and-github-skills" || String(node.id).startsWith("skill-");
  }

  function isPmicNode(node) {
    return node.domain === "power-management-ic";
  }

  function isAmsNode(node) {
    return node.domain === "ams-filters-and-system";
  }

  function isRazaviCoreNode(node) {
    return RAZAVI_CORE_DOMAINS.has(node.domain);
  }

  function getDesignCycleList() {
    return Array.isArray(state.router?.design_cycle) && state.router.design_cycle.length === 7
      ? state.router.design_cycle
      : DEFAULT_DESIGN_CYCLE;
  }

  function getNodeDesignStages(node) {
    if (Array.isArray(node.design_stages) && node.design_stages.length > 0) {
      return node.design_stages;
    }
    const nid = String(node.id || "");
    const stages = new Set();
    if (["concept", "law"].includes(node.kind) || nid.includes("octagon") || nid.includes("25-topology")) stages.add(1);
    if (node.kind === "topology") {
      stages.add(1);
      stages.add(4);
    }
    if (/budget|interface|central-bias-hub|protections-por-uvlo|cace/.test(nid)) stages.add(2);
    if (/gmid|gm-id|vdsmin|sizing|scaling|current-mirrors|pelgrom/.test(nid)) stages.add(3);
    if (/ic617|schematic|veriloga|startup|cmfb/.test(nid)) stages.add(4);
    if (/stb|pss|pnoise|pstb|psf|ocean|middlebrook|nyquist|phase-margin|compensat|type2|type3|slope-comp/.test(nid)) stages.add(5);
    if (/closed-loop-sizing|pareto|slewing-vs-linear|octagon|tradeoff|charge-pump-dcdc|hs-bootstrap/.test(nid)) stages.add(6);
    if (/pvt|montecarlo|layout|pex|latchup|esd|mismatch|substrate|interconnect|cace|protections/.test(nid) || node.domain === "nonideal-and-physical") stages.add(7);
    if (stages.size === 0) stages.add(isSkillNode(node) ? 5 : 1);
    return Array.from(stages).sort((a, b) => a - b);
  }

  function normalizeEqKey(raw) {
    const m = String(raw || "").match(/(\d{1,2}\.\d+[a-z]?)/i);
    return m ? m[1].toLowerCase() : "";
  }

  function pageMatchesRange(pageNum, rangeStr) {
    if (!rangeStr || !Number.isFinite(pageNum)) return false;
    const s = String(rangeStr);
    const parts = s.split(/[,;]/);
    for (const p of parts) {
      const mRange = p.match(/(\d+)\s*[-–]\s*(\d+)/);
      if (mRange) {
        const a = Number(mRange[1]);
        const b = Number(mRange[2]);
        if (pageNum >= Math.min(a, b) && pageNum <= Math.max(a, b)) return true;
      } else {
        const mSingle = p.match(/\b(\d+)\b/);
        if (mSingle && Number(mSingle[1]) === pageNum) return true;
      }
    }
    return false;
  }

  function parseCoordinateQuery(rawQuery) {
    const q = String(rawQuery || "").trim();
    if (!q) return { type: "empty" };

    // 1. Page query: "p. 342", "p.342", "page 342", "trang 342", "tr 342"
    const pageMatch = q.match(/^(?:p\.?|pp\.?|page|trang|tr\.?)\s*(\d{1,3})$/i);
    if (pageMatch) {
      return { type: "page", page: Number(pageMatch[1]), raw: q };
    }

    // 2. Equation query: "Eq. 10.25", "eq 2.10", "(2.10)", "pt 9.17"
    const eqMatch = q.match(/^(?:eq\.?|equation|pt|phuong\s*trinh)\s*\(?(\d{1,2}\.\d+[a-z]?)\)?$/i) || q.match(/^\((\d{1,2}\.\d+[a-z]?)\)$/i);
    if (eqMatch) {
      return { type: "equation", eq: eqMatch[1].toLowerCase(), raw: q };
    }

    // 3. Section query: "§9.2", "9.2", "9.2.4", "sec 12.3", "muc 13.4"
    const secMatch = q.match(/^(?:§|sec\.?|section|muc)\s*(\d{1,2}(?:\.\d+)+)$/i) || q.match(/^(\d{1,2}(?:\.\d+)+)$/);
    if (secMatch) {
      return { type: "section", section: secMatch[1], raw: q };
    }

    // 4. Chapter query: "ch10", "chuong 9", "chapter 16"
    const chMatch = foldWords(q).match(/^(?:ch|chuong|chapter)\s*(\d{1,2})$/);
    if (chMatch) {
      const ch = Number(chMatch[1]);
      if (ch >= 1 && ch <= 19) return { type: "chapter", chapter: ch, raw: q };
    }

    return { type: "text", raw: q };
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
      throw new Error("Không tìm thấy kb/router-index.json. Hãy chạy python -B tools/build_index.py trước.");
    }
    state.router = loadedRouter;
    if (el.rawIndexLink) el.rawIndexLink.href = `${state.kbBase}/router-index.json`;
    if (el.rawCoordsLink) el.rawCoordsLink.href = `${state.kbBase}/coordinates/book-coordinates.json`;
    if (el.rawCatalogLink) el.rawCatalogLink.href = `${state.kbBase}/github-skills/catalog.json`;

    for (const n of loadedRouter.nodes || []) {
      state.nodeMap.set(n.id, n);
      state.adjOut.set(n.id, []);
      state.adjIn.set(n.id, []);
    }

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
      // Non-fatal
    }

    updateSidebarStats();
    renderSidebarControls();
    el.loadingBanner.hidden = true;
    el.view.hidden = false;

    // Kick off non-blocking loads of coordinates, GitHub catalog, and glossary
    ensureCoordsLoaded();
    ensureCatalogLoaded();
    ensureGlossaryLoaded();
  }

  function updateSidebarStats() {
    if (!state.router) return;
    const st = state.router.stats || {};
    if (el.statNodes) el.statNodes.textContent = st.node_count ?? (state.router.nodes || []).length;
    if (el.statDiagrams) el.statDiagrams.textContent = st.diagram_count ?? 72;
    if (el.statChecklists) el.statChecklists.textContent = st.checklist_count ?? (state.router.checklists || []).length;
    if (el.statGlossary) el.statGlossary.textContent = st.glossary_count ?? 2280;
    if (el.statSections) {
      const secCnt = state.coords?.sections?.length ?? st.book_section_count ?? 293;
      el.statSections.textContent = secCnt;
    }
    if (el.statRepos) {
      const repoCnt = state.catalog?.repos?.length ?? st.github_repo_count ?? 52;
      el.statRepos.textContent = repoCnt;
    }
    if (el.releaseVer) el.releaseVer.textContent = state.router.release || "2026.11.18.6";
  }

  function normalizeCoordsPayload(raw) {
    if (!raw || typeof raw !== "object") {
      return { chapters: [], sections: [], equations: [], index_terms: [] };
    }
    const chapters = Array.isArray(raw.chapters) ? raw.chapters : [];
    const sections = (Array.isArray(raw.sections) ? raw.sections : []).map((s) => ({
      section_id: String(s.section_id || s.section || s.id || ""),
      chapter: Number(s.chapter || String(s.section_id || "").split(".")[0] || 1),
      title_en: s.title_en || "",
      title_vi: s.title_vi || "",
      book_pages: String(s.book_pages || s.pages || ""),
      pdf_pages: String(s.pdf_pages || ""),
      key_equations: Array.isArray(s.key_equations) ? s.key_equations : [],
      key_figures: Array.isArray(s.key_figures) ? s.key_figures : [],
      primary_nodes: Array.isArray(s.primary_nodes) ? s.primary_nodes : Array.isArray(s.nodes) ? s.nodes : [],
      summary_vi: s.summary_vi || s.summary || "",
      search_key: foldWords(`${s.section_id || ""} ${s.title_en || ""} ${s.title_vi || ""} ${s.summary_vi || ""} ${(s.key_equations || []).join(" ")}`),
    }));
    const equations = (Array.isArray(raw.equations) ? raw.equations : []).map((e) => {
      const rawId = String(e.eq_id || e.id || e.equation || "");
      const normKey = normalizeEqKey(rawId || e.eq_num);
      const mergedNodes = [];
      for (const cand of [e.node_id, ...(Array.isArray(e.node_ids) ? e.node_ids : []), ...(Array.isArray(e.related_nodes) ? e.related_nodes : [])]) {
        if (cand && !mergedNodes.includes(cand)) mergedNodes.push(cand);
      }
      return {
        eq_id: rawId || (normKey ? `Eq.${normKey}` : ""),
        eq_num: normKey,
        chapter: Number(e.chapter || (normKey ? normKey.split(".")[0] : 1)),
        section: String(e.section || ""),
        book_page: e.book_page ?? e.page ?? "",
        pdf_page: e.pdf_page ?? "",
        latex: e.latex || "",
        meaning_vi: e.meaning_vi || e.meaning || e.title_vi || "",
        node_ids: mergedNodes,
        search_key: foldWords(`${rawId} ${e.section || ""} ${e.meaning_vi || ""} ${e.latex || ""}`),
      };
    });
    const indexTerms = (Array.isArray(raw.index_terms) ? raw.index_terms : []).map((t) => ({
      term_en: t.term_en || t.en || t.term || "",
      term_vi: t.term_vi || t.vi || "",
      book_pages: Array.isArray(t.book_pages) ? t.book_pages.join(", ") : String(t.book_pages || t.pages || ""),
      chapters: Array.isArray(t.chapters) ? t.chapters : [],
      mapped_nodes: Array.isArray(t.mapped_nodes) ? t.mapped_nodes : Array.isArray(t.nodes) ? t.nodes : [],
      search_key: foldWords(`${t.term_en || ""} ${t.term_vi || ""} ${t.book_pages || ""}`),
    }));
    return { chapters, sections, equations, index_terms: indexTerms };
  }

  async function ensureCoordsLoaded() {
    if (state.coords || state.coordsLoading) return state.coords;
    state.coordsLoading = true;
    try {
      const res = await fetch(`${state.kbBase}/coordinates/book-coordinates.json`);
      if (res.ok) {
        state.coords = normalizeCoordsPayload(await res.json());
      } else {
        state.coords = { chapters: [], sections: [], equations: [], index_terms: [] };
      }
    } catch (_err) {
      state.coords = { chapters: [], sections: [], equations: [], index_terms: [] };
    } finally {
      state.coordsLoading = false;
    }
    updateSidebarStats();
    if (state.mode === "coords" || state.query) {
      renderActiveView();
    }
    return state.coords;
  }

  function normalizeCatalogPayload(raw) {
    if (!raw || typeof raw !== "object") return { repos: [], categories: [] };
    const arr = raw.repositories || raw.repos || raw.entries || raw.items || [];
    const categories = Array.isArray(raw.categories) ? raw.categories : [];
    const repos = (Array.isArray(arr) ? arr : []).map((r) => ({
      id: r.id || r.repo || "",
      repo: r.repo || r.full_name || r.name || r.id || "",
      url: r.url || (r.repo ? `https://github.com/${r.repo}` : "#"),
      pinned: r.pinned_commit_or_branch || r.pinned_ref || r.commit || r.branch || "main",
      license: r.license || "Open-Source",
      stars: r.stars ?? null,
      category: r.category || "analog-eda",
      quality_tier: r.quality_tier || r.tier || "Tier-1",
      ic617_compatibility: r.ic617_compatibility || r.compatibility || "Compatible",
      summary_vi: r.summary_vi || r.summary || r.description || "",
      key_techniques: Array.isArray(r.key_techniques) ? r.key_techniques : [],
      linked_nodes: Array.isArray(r.linked_nodes) ? r.linked_nodes : [],
      search_key: foldWords(
        `${r.id || ""} ${r.repo || ""} ${r.category || ""} ${r.ic617_compatibility || ""} ${r.summary_vi || ""} ${(r.key_techniques || []).join(" ")}`
      ),
    }));
    return { repos, categories, meta: raw };
  }

  async function ensureCatalogLoaded() {
    if (state.catalog || state.catalogLoading) return state.catalog;
    state.catalogLoading = true;
    try {
      const res = await fetch(`${state.kbBase}/github-skills/catalog.json`);
      if (res.ok) {
        state.catalog = normalizeCatalogPayload(await res.json());
      } else {
        state.catalog = { repos: [] };
      }
    } catch (_err) {
      state.catalog = { repos: [] };
    } finally {
      state.catalogLoading = false;
    }
    updateSidebarStats();
    if (state.mode === "skills" || state.query) {
      renderActiveView();
    }
    return state.catalog;
  }

  async function ensureGlossaryLoaded() {
    if (state.glossary || state.glossaryLoading) return state.glossary;
    state.glossaryLoading = true;
    try {
      const res = await fetch(`${state.kbBase}/glossary/terms-vi-en.json`);
      if (res.ok) {
        const data = await res.json();
        state.glossary = data.terms || [];
      } else {
        state.glossary = [];
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
    if (!state.router) return;
    const totalCount = (state.router.nodes || []).length;
    const domainCount = (state.router.domains || []).length || 10;
    const domainItems = [
      `<li><button type="button" class="nav-item ${state.filterDomain === "all" ? "is-active" : ""}" data-domain="all"><span>Tất cả ${domainCount} Tầng Tri thức</span><span class="nav-count">${totalCount}</span></button></li>`,
    ];
    for (const d of state.router.domains || []) {
      const active = state.filterDomain === d.id ? "is-active" : "";
      domainItems.push(
        `<li><button type="button" class="nav-item ${active}" data-domain="${escapeHtml(d.id)}"><span>${escapeHtml(d.title_vi)}</span><span class="nav-count">${d.node_count || 0}</span></button></li>`
      );
    }
    el.domainList.innerHTML = domainItems.join("");

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

    const hasFilter =
      state.filterDomain !== "all" ||
      state.filterChapter !== null ||
      state.filterKind !== "all" ||
      state.filterStage !== null ||
      Boolean(state.query);
    el.resetFilters.hidden = !hasFilter;
  }

  // ---------------- Coordinate & Full-Text Search Engine ----------------
  function searchExactCoordinates(rawQuery) {
    const parsed = parseCoordinateQuery(rawQuery);
    if (parsed.type === "empty") return { parsed, sections: [], equations: [], indexTerms: [], repos: [] };

    const coords = state.coords || { sections: [], equations: [], index_terms: [] };
    const catalog = state.catalog || { repos: [] };
    const qWords = foldWords(rawQuery);
    const qTokens = qWords ? qWords.split(/\s+/).filter(Boolean) : [];

    let hitSections = [];
    let hitEquations = [];
    let hitIndex = [];
    let hitRepos = [];

    if (parsed.type === "section") {
      const target = parsed.section;
      hitSections = coords.sections.filter(
        (s) => s.section_id === target || s.section_id.startsWith(`${target}.`) || target.startsWith(`${s.section_id}.`)
      );
      hitEquations = coords.equations.filter((e) => e.section === target || e.section.startsWith(`${target}.`));
    } else if (parsed.type === "equation") {
      const targetEq = parsed.eq;
      hitEquations = coords.equations.filter((e) => e.eq_num === targetEq || e.eq_num.startsWith(targetEq));
      const secSet = new Set(hitEquations.map((e) => e.section).filter(Boolean));
      hitSections = coords.sections.filter(
        (s) => secSet.has(s.section_id) || (s.key_equations || []).some((ke) => normalizeEqKey(ke) === targetEq)
      );
    } else if (parsed.type === "page") {
      const p = parsed.page;
      hitSections = coords.sections.filter((s) => pageMatchesRange(p, s.book_pages));
      hitEquations = coords.equations.filter((e) => Number(e.book_page) === p || pageMatchesRange(p, String(e.book_page)));
      hitIndex = coords.index_terms.filter((t) => pageMatchesRange(p, t.book_pages));
    } else if (parsed.type === "chapter") {
      hitSections = coords.sections.filter((s) => s.chapter === parsed.chapter).slice(0, 6);
    } else if (qTokens.length > 0) {
      hitSections = coords.sections
        .filter((s) => qTokens.every((t) => s.search_key.includes(t)))
        .slice(0, 4);
      hitEquations = coords.equations
        .filter((e) => qTokens.every((t) => e.search_key.includes(t)))
        .slice(0, 4);
      hitIndex = coords.index_terms
        .filter((it) => qTokens.every((t) => it.search_key.includes(t)))
        .slice(0, 4);
      hitRepos = catalog.repos
        .filter((r) => qTokens.every((t) => r.search_key.includes(t)))
        .slice(0, 4);
    }

    return {
      parsed,
      sections: hitSections.slice(0, 6),
      equations: hitEquations.slice(0, 6),
      indexTerms: hitIndex.slice(0, 6),
      repos: hitRepos.slice(0, 4),
    };
  }

  function scoreNode(node, parsed, qWords, qTokens, coordBoostIds) {
    if (parsed.type === "empty") return 1;

    if (parsed.type === "chapter") {
      return (node.chapters || []).includes(parsed.chapter) ? 110 : 0;
    }

    if (parsed.type === "section") {
      const target = parsed.section;
      let sc = coordBoostIds.has(node.id) ? 140 : 0;
      for (const r of node.razavi_refs || []) {
        const sec = String(r.section || "");
        if (sec === target || sec.includes(target)) sc = Math.max(sc, 150);
        else if (sec.split(/[,;\s-]+/).some((part) => part && (target.startsWith(part) || part.startsWith(target)))) {
          sc = Math.max(sc, 125);
        }
      }
      return sc;
    }

    if (parsed.type === "equation") {
      const targetEq = parsed.eq;
      let sc = coordBoostIds.has(node.id) ? 140 : 0;
      for (const r of node.razavi_refs || []) {
        for (const eq of r.equations || []) {
          if (normalizeEqKey(eq) === targetEq) sc = Math.max(sc, 160);
        }
      }
      return sc;
    }

    if (parsed.type === "page") {
      const p = parsed.page;
      let sc = coordBoostIds.has(node.id) ? 135 : 0;
      for (const r of node.razavi_refs || []) {
        if (pageMatchesRange(p, r.pages)) sc = Math.max(sc, 155);
      }
      return sc;
    }

    if (!qWords) return 1;
    const idFold = foldWords(node.id);
    const viFold = foldWords(node.title_vi);
    const enFold = foldWords(node.title_en);
    const ghBlob = (node.github_refs || []).map((g) => `${g.repo || ""} ${g.use || ""}`).join(" ");
    const hay = `${node.search_text || ""} ${foldWords(`${node.id} ${node.title_vi} ${node.title_en} ${node.summary} ${ghBlob}`)}`;

    if (idFold === qWords) return 150;
    let boost = coordBoostIds.has(node.id) ? 35 : 0;
    if (enFold.includes(qWords) || viFold.includes(qWords)) return 105 + boost;
    if (idFold.includes(qWords)) return 95 + boost;
    let matched = 0;
    for (const tok of qTokens) {
      if (hay.includes(tok)) matched++;
    }
    if (matched === qTokens.length) return 65 + matched * 5 + boost;
    return boost > 0 ? 55 : 0;
  }

  function passesKindFilter(node, kindFilter) {
    if (kindFilter === "all") return true;
    if (kindFilter === "pmic") return isPmicNode(node);
    if (kindFilter === "ams") return isAmsNode(node);
    if (kindFilter === "razavi") return isRazaviCoreNode(node);
    if (kindFilter === "skill") return isSkillNode(node);
    if (kindFilter === "topology") return node.kind === "topology";
    if (kindFilter === "technique") return node.kind === "technique";
    if (kindFilter === "law-concept") return ["law", "concept", "physical_rule"].includes(node.kind);
    return true;
  }

  function filterNodes() {
    const coordHits = searchExactCoordinates(state.query);
    const coordBoostIds = new Set();
    for (const s of coordHits.sections) for (const id of s.primary_nodes) coordBoostIds.add(id);
    for (const e of coordHits.equations) for (const id of e.node_ids) coordBoostIds.add(id);
    for (const it of coordHits.indexTerms) for (const id of it.mapped_nodes) coordBoostIds.add(id);
    for (const rp of coordHits.repos) for (const id of rp.linked_nodes) coordBoostIds.add(id);

    const qWords = foldWords(state.query);
    const qTokens = qWords ? qWords.split(/\s+/).filter(Boolean) : [];
    const results = [];

    for (const node of state.router.nodes || []) {
      if (state.filterDomain !== "all" && node.domain !== state.filterDomain) continue;
      if (state.filterChapter !== null && !(node.chapters || []).includes(state.filterChapter)) continue;
      if (!passesKindFilter(node, state.filterKind)) continue;
      if (state.filterStage !== null && !getNodeDesignStages(node).includes(state.filterStage)) continue;

      const sc = scoreNode(node, coordHits.parsed, qWords, qTokens, coordBoostIds);
      if (sc > 0) results.push({ node, score: sc });
    }

    results.sort(
      (a, b) =>
        b.score - a.score ||
        (isSkillNode(a.node) ? 1 : 0) - (isSkillNode(b.node) ? 1 : 0) ||
        (a.node.chapters?.[0] || 99) - (b.node.chapters?.[0] || 99) ||
        a.node.id.localeCompare(b.node.id)
    );
    return { nodes: results.map((r) => r.node), coordHits };
  }

  function searchGlossaryPreview(limit = 6) {
    if (!state.glossary || !state.query) return [];
    const qRaw = state.query.trim();
    const qWords = foldWords(qRaw);
    if (!qWords) return [];
    const qTokens = qWords.split(/\s+/).filter(Boolean);
    const codeMatch = qRaw.match(/^t0*(\d+)$/i);
    const hits = [];

    for (const term of state.glossary) {
      if (state.filterChapter !== null && !(term.chapters || []).includes(state.filterChapter)) continue;
      if (codeMatch && Number(term.id.slice(1)) === Number(codeMatch[1])) {
        hits.push({ term, rank: 0 });
        continue;
      }
      const key = term.search_key || foldWords(`${term.id} ${term.en} ${term.vi}`);
      const enF = foldWords(term.en);
      const viF = foldWords(term.vi);
      if (enF === qWords || viF === qWords) hits.push({ term, rank: 1 });
      else if (enF.startsWith(qWords) || viF.startsWith(qWords)) hits.push({ term, rank: 2 });
      else if (enF.includes(qWords) || viF.includes(qWords)) hits.push({ term, rank: 3 });
      else if (qTokens.every((t) => key.includes(t))) hits.push({ term, rank: 4 });
    }
    hits.sort((a, b) => a.rank - b.rank || Number(a.term.id.slice(1)) - Number(b.term.id.slice(1)));
    return hits.slice(0, limit).map((h) => h.term);
  }

  // ---------------- Markdown + KaTeX Renderer ----------------
  function renderMathToken(tex, displayMode) {
    const cleanTex = String(tex || "").trim();
    if (!cleanTex) return "";
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

    let working = mdBody.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_m, lang, code) => {
      const idx = codeStore.length;
      codeStore.push({ lang: lang || "text", code });
      return `\u0000CODEBLOCK_${idx}\u0000`;
    });

    const inlineCodeStore = [];
    working = working.replace(/`([^`\n]+)`/g, (_m, code) => {
      const idx = inlineCodeStore.length;
      inlineCodeStore.push(code);
      return `\u0000INLINECODE_${idx}\u0000`;
    });

    working = working.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) => {
      const idx = mathStore.length;
      mathStore.push({ tex, display: true });
      return `\u0000MATH_${idx}\u0000`;
    });

    working = working.replace(/(?<!\\)\$([^\n$]+?)(?<!\\)\$/g, (_m, tex) => {
      const idx = mathStore.length;
      mathStore.push({ tex, display: false });
      return `\u0000MATH_${idx}\u0000`;
    });

    function formatInline(rawLine) {
      let s = escapeHtml(rawLine);

      s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, src) => {
        const resolved = src.includes("diagrams/") ? resolveDiagramUrl(src) : src;
        return `<figure class="md-diagram" data-zoom-svg="${escapeHtml(resolved)}" data-zoom-title="${escapeHtml(alt)}"><img src="${escapeHtml(resolved)}" alt="${escapeHtml(alt)}" loading="lazy"><figcaption>${escapeHtml(alt)} · Nhấp để phóng to sơ đồ vector</figcaption></figure>`;
      });

      s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, href) => {
        if (href.startsWith("#")) {
          return `<a href="${escapeHtml(href)}">${label}</a>`;
        }
        return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener">${label}</a>`;
      });

      s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");

      s = s.replace(/\[(INV-[A-Za-z0-9_-]+)\]/g, '<span class="badge badge-inv">$1</span>');
      s = s.replace(/\[(TRAP-[A-Za-z0-9_-]+)\]/g, '<span class="badge badge-trap">$1</span>');

      s = s.replace(/\u0000INLINECODE_(\d+)\u0000/g, (_m, idxStr) => {
        const rawCode = inlineCodeStore[Number(idxStr)] || "";
        const trimmed = rawCode.trim();
        if (state.nodeMap.has(trimmed)) {
          return `<a class="node-ref-pill" href="#node/${escapeHtml(trimmed)}" title="Mở thẻ ${escapeHtml(trimmed)}">${escapeHtml(trimmed)} →</a>`;
        }
        return `<code>${escapeHtml(rawCode)}</code>`;
      });

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

      const cbMatch = trimmed.match(/^\u0000CODEBLOCK_(\d+)\u0000$/);
      if (cbMatch) {
        const cb = codeStore[Number(cbMatch[1])];
        out.push(`<pre data-lang="${escapeHtml(cb.lang)}"><code>${escapeHtml(cb.code.replace(/\n$/, ""))}</code></pre>`);
        i++;
        continue;
      }

      const dmMatch = trimmed.match(/^\u0000MATH_(\d+)\u0000$/);
      if (dmMatch) {
        const item = mathStore[Number(dmMatch[1])];
        out.push(`<div class="math-display">${renderMathToken(item.tex, true)}</div>`);
        i++;
        continue;
      }

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

      if (/^---+$/.test(trimmed) || /^\*\*\*+$/.test(trimmed)) {
        out.push("<hr>");
        i++;
        continue;
      }

      if (trimmed.startsWith("|") && i + 1 < lines.length && /^\s*\|[\s:-]+\|/.test(lines[i + 1])) {
        const splitRow = (r) =>
          r
            .trim()
            .replace(/^\|/, "")
            .replace(/\|$/, "")
            .split("|")
            .map((c) => formatInline(c.trim()));
        const headers = splitRow(lines[i]);
        i += 2;
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

      if (trimmed.startsWith(">")) {
        const bqLines = [];
        while (i < lines.length && lines[i].trim().startsWith(">")) {
          bqLines.push(lines[i].trim().replace(/^>\s?/, ""));
          i++;
        }
        out.push(`<blockquote>${bqLines.map((l) => `<p>${formatInline(l)}</p>`).join("")}</blockquote>`);
        continue;
      }

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
        return lines.slice(i + 1).join("\n");
      }
    }
    return rawMd;
  }

  function renderNodePillsHtml(nodeIds, limit = 4) {
    const valid = (nodeIds || []).filter((id) => state.nodeMap.has(id));
    if (!valid.length) return "";
    return valid
      .slice(0, limit)
      .map((id) => `<a class="node-ref-pill" href="#node/${escapeHtml(id)}">${escapeHtml(id)} →</a>`)
      .join(" ");
  }

  function renderNodeCardHtml(n) {
    const refs = (n.razavi_refs || [])
      .slice(0, 2)
      .map((r) => `Ch.${r.chapter}${r.section ? ` §${r.section}` : ""}${r.pages ? ` p.${r.pages}` : ""}`)
      .join(" · ");
    const ghRefs = n.github_refs || [];
    const domPill = isPmicNode(n)
      ? `<span class="badge badge-pmic">PMIC</span>`
      : isAmsNode(n)
      ? `<span class="badge badge-ams">AMS</span>`
      : "";
    const ghBadge = ghRefs.length
      ? `<span class="badge badge-skill" style="text-transform:none;font-family:var(--font-mono)">${escapeHtml(ghRefs[0].repo || "GitHub")}</span>`
      : "";
    const outCount = (state.adjOut.get(n.id) || []).length;
    const inCount = (state.adjIn.get(n.id) || []).length;

    return `
      <article class="node-card" data-open-node="${escapeHtml(n.id)}" tabindex="0" role="link" aria-label="${escapeHtml(n.title_vi)}">
        <div class="card-topline">
          <div style="display:flex;gap:5px;flex-wrap:wrap">
            <span class="badge ${kindBadgeClass(n.kind)}">${escapeHtml(n.kind)}</span>
            ${domPill}
            ${ghBadge}
          </div>
          <span class="badge badge-neutral">${escapeHtml(refs || n.domain)}</span>
        </div>
        <h3>${escapeHtml(n.title_vi)}</h3>
        <p class="en-sub">${escapeHtml(n.title_en)}</p>
        <p class="summary">${escapeHtml(n.summary)}</p>
        <div class="card-footer">
          <code>${escapeHtml(n.id)}</code>
          <span>${inCount + outCount} liên kết →</span>
        </div>
      </article>
    `;
  }

  function renderCoordHitsStripHtml(coordHits) {
    const totalHits =
      coordHits.sections.length +
      coordHits.equations.length +
      coordHits.indexTerms.length +
      coordHits.repos.length;
    if (!state.query || totalHits === 0) return "";

    const cards = [];

    for (const s of coordHits.sections.slice(0, 3)) {
      cards.push(`
        <div class="coord-hit-card">
          <div class="card-topline">
            <span class="badge badge-topology">MỤC §${escapeHtml(s.section_id)}</span>
            <span class="meta">Ch.${s.chapter}${s.book_pages ? ` · Trang ${escapeHtml(s.book_pages)}` : ""}${s.pdf_pages ? ` (PDF p.${escapeHtml(s.pdf_pages)})` : ""}</span>
          </div>
          <strong>${escapeHtml(s.title_vi || s.title_en)}</strong>
          ${s.title_vi && s.title_en ? `<div style="font-size:12px;color:var(--ink-muted)">${escapeHtml(s.title_en)}</div>` : ""}
          ${s.summary_vi ? `<div style="font-size:12.5px;color:var(--ink-secondary)">${escapeHtml(s.summary_vi.slice(0, 140))}${s.summary_vi.length > 140 ? "…" : ""}</div>` : ""}
          <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:auto;padding-top:4px">
            ${renderNodePillsHtml(s.primary_nodes, 3)}
          </div>
        </div>
      `);
    }

    for (const eq of coordHits.equations.slice(0, 3)) {
      cards.push(`
        <div class="coord-hit-card">
          <div class="card-topline">
            <span class="badge badge-law">${escapeHtml(eq.eq_id)}</span>
            <span class="meta">Ch.${eq.chapter}${eq.section ? ` §${escapeHtml(eq.section)}` : ""}${eq.book_page ? ` · p.${escapeHtml(eq.book_page)}` : ""}</span>
          </div>
          ${eq.latex ? `<div class="math-display" style="margin:2px 0;padding:6px 8px">${renderMathToken(eq.latex, false)}</div>` : ""}
          <div style="font-size:12.5px;color:var(--ink-secondary)">${escapeHtml(eq.meaning_vi)}</div>
          <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:auto;padding-top:4px">
            ${renderNodePillsHtml(eq.node_ids, 2)}
          </div>
        </div>
      `);
    }

    for (const it of coordHits.indexTerms.slice(0, 2)) {
      cards.push(`
        <div class="coord-hit-card">
          <div class="card-topline">
            <span class="badge badge-technique">20_INDEX</span>
            <span class="meta">Trang ${escapeHtml(it.book_pages)}</span>
          </div>
          <strong>${escapeHtml(it.term_en)}</strong>
          ${it.term_vi ? `<div style="font-size:12.5px;color:var(--ink-secondary)">${escapeHtml(it.term_vi)}</div>` : ""}
          <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:auto;padding-top:4px">
            ${renderNodePillsHtml(it.mapped_nodes, 3)}
          </div>
        </div>
      `);
    }

    for (const rp of coordHits.repos.slice(0, 2)) {
      cards.push(`
        <div class="coord-hit-card">
          <div class="card-topline">
            <span class="badge badge-skill">GITHUB REPO</span>
            <span class="badge badge-neutral">${escapeHtml(rp.license)}${rp.stars ? ` · ${rp.stars} stars` : ""}</span>
          </div>
          <strong><a href="${escapeHtml(rp.url)}" target="_blank" rel="noopener">${escapeHtml(rp.repo)} ↗</a></strong>
          <div style="font-size:12.5px;color:var(--ink-secondary)">${escapeHtml(rp.summary_vi.slice(0, 130))}${rp.summary_vi.length > 130 ? "…" : ""}</div>
          <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:auto;padding-top:4px">
            ${renderNodePillsHtml(rp.linked_nodes, 3)}
          </div>
        </div>
      `);
    }

    return `
      <section class="coord-hit-panel" aria-label="Kết quả đối chiếu tọa độ sách và GitHub">
        <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px">
          <div>
            <span class="eyebrow" style="margin:0">ĐỐI CHIẾU TỌA ĐỘ TỨC THÌ · SÁCH RAZAVI &amp; GITHUB SKILLS</span>
          </div>
          <div style="display:flex;gap:10px">
            <button type="button" class="link-btn" id="jump-open-coords">Mở Cây Tọa độ 19 Chương →</button>
            <button type="button" class="link-btn" id="jump-open-skills">Mở Kho GitHub Skills →</button>
          </div>
        </div>
        <div class="coord-hit-grid">${cards.join("")}</div>
      </section>
    `;
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
    } else if (state.mode === "coords") {
      renderBookCoordsView();
    } else if (state.mode === "skills") {
      renderGitHubSkillsView();
    } else if (state.mode === "checklists") {
      renderChecklistsView();
    } else if (state.mode === "glossary") {
      renderGlossaryView();
    } else {
      renderNodesCatalogView();
    }
  }

  function renderDesignCycleBannerHtml() {
    const cycleList = getDesignCycleList();
    const stageCounts = new Map();
    for (let s = 1; s <= 7; s++) stageCounts.set(s, 0);
    for (const n of state.router?.nodes || []) {
      for (const s of getNodeDesignStages(n)) {
        stageCounts.set(s, (stageCounts.get(s) || 0) + 1);
      }
    }
    const flowSvgUrl = `${state.kbBase}/diagrams/closed-loop-cadence-codex-flow.svg`;

    return `
      <section class="cycle-banner" aria-label="Chu trình Tối ưu Khép kín 7 Bước Cadence-Codex">
        <div class="cycle-banner-top">
          <div>
            <span class="eyebrow" style="margin:0;display:block">MANDATORY 7-STAGE CLOSED-LOOP OPTIMAL ANALOG DESIGN CYCLE (VIRTUOSO IC617 · SPECTRE 15.1 · CODEX)</span>
            <h2>Chu trình Thiết kế &amp; Tối ưu Pareto Khép kín 7 Bước (Nhấp từng bước để lọc thẻ &amp; công cụ tương ứng)</h2>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            ${
              state.filterStage !== null
                ? `<button type="button" class="btn-primary" id="btn-clear-stage">Bỏ lọc Bước ${state.filterStage}</button>`
                : ""
            }
            <button type="button" class="btn-subtle" id="btn-open-cycle-svg" data-svg="${escapeHtml(flowSvgUrl)}">Mở lưu đồ SVG 7 bước</button>
          </div>
        </div>
        <div class="cycle-grid" role="group" aria-label="7 bước tối ưu thiết kế vi mạch">
          ${cycleList
            .map((st) => {
              const sNum = Number(st.stage);
              const active = state.filterStage === sNum ? "is-active" : "";
              const cnt = stageCounts.get(sNum) || 0;
              return `
                <button type="button" class="cycle-step ${active}" data-stage="${sNum}" aria-pressed="${state.filterStage === sNum}">
                  <div class="cycle-step-head">
                    <span class="cycle-step-num">STAGE 0${sNum}</span>
                    <span class="nav-count">${cnt}</span>
                  </div>
                  <div class="cycle-step-title">${escapeHtml(st.title_vi)}</div>
                  <div class="cycle-step-tool">${escapeHtml(st.tool || "")}</div>
                </button>
              `;
            })
            .join("")}
        </div>
      </section>
    `;
  }

  // ---------------- View 0: Full Nodes Catalog + Coordinate Jump Bar ----------------
  function renderNodesCatalogView() {
    const { nodes, coordHits } = filterNodes();
    const glossaryHits = searchGlossaryPreview(4);
    const chLabel = state.filterChapter ? ` · Chương ${String(state.filterChapter).padStart(2, "0")}` : "";
    const domMeta = (state.router.domains || []).find((d) => d.id === state.filterDomain);
    const domLabel = domMeta ? ` · ${domMeta.title_vi}` : "";
    const stageMeta = state.filterStage
      ? getDesignCycleList().find((s) => Number(s.stage) === state.filterStage)
      : null;
    const stageLabel = stageMeta ? ` · [${stageMeta.title_vi}]` : "";

    const st = state.router.stats || {};
    const totalNodes = (state.router.nodes || []).length;
    const razaviCoreCount = st.razavi_core_node_count ?? (state.router.nodes || []).filter(isRazaviCoreNode).length;
    const pmicCount = st.pmic_node_count ?? (state.router.nodes || []).filter(isPmicNode).length;
    const amsCount = st.ams_node_count ?? (state.router.nodes || []).filter(isAmsNode).length;
    const edaDomainCount =
      st.eda_domain_node_count ?? (state.router.nodes || []).filter((n) => n.domain === "eda-and-github-skills").length;
    const diagCount = st.diagram_count ?? 72;
    const clCount = (state.router.checklists || []).length;
    const glCount = st.glossary_count ?? 2280;

    let glossaryStrip = "";
    if (state.query && glossaryHits.length > 0) {
      glossaryStrip = `
        <div class="section-bar">
          <h2>Thuật ngữ Chuẩn CLB khớp nhanh (${glossaryHits.length})</h2>
          <button type="button" class="link-btn" id="jump-all-glossary">Xem toàn bộ kho ${glCount} thuật ngữ →</button>
        </div>
        <div class="node-grid" style="margin-bottom:22px">
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
              <div style="font-size:12px;color:var(--ink-secondary)">${escapeHtml((t.context || "").slice(0, 140))}${(t.context || "").length > 140 ? "…" : ""}</div>
            </div>`
            )
            .join("")}
        </div>
      `;
    }

    el.view.innerHTML = `
      <section class="hero-header">
        <p class="eyebrow">10 DOMAINS · RAZAVI 19 CH. + PMIC (BUCK/BOOST/LDO) + AMS (FILTER/DAC/ΔΣ/INA) + CLOSED-LOOP CADENCE-CODEX</p>
        <h1>Bản đồ Tri thức Toàn Chip CMOS, PMIC, AMS &amp; Tối ưu Khép kín EDA</h1>
        <p>Tra cứu tức thì <strong>${totalNodes}</strong> thẻ chuyên sâu 6 khối xuyên suốt <strong>10 tầng</strong> (${razaviCoreCount} thẻ Razavi Ch.01–19 + ${pmicCount} thẻ PMIC Nguồn chuyển mạch/LDO + ${amsCount} thẻ AMS Bộ lọc/DAC/ΔΣ/AFE + ${edaDomainCount} Playbook Cadence IC617/Spectre/Pareto), <strong>${diagCount}</strong> sơ đồ nguyên lý vector SVG và <strong>${clCount}</strong> bảng kiểm đa tiến trình.</p>
        <div class="quick-chips">
          <span class="label">NHẢY NHANH V3:</span>
          <button type="button" class="chip-query" data-q="4-switch buck-boost">4-Switch Buck-Boost</button>
          <button type="button" class="chip-query" data-q="capless ldo fvf">Capless FVF/DFC LDO</button>
          <button type="button" class="chip-query" data-q="type3 slope">Type-III &amp; Slope Comp</button>
          <button type="button" class="chip-query" data-q="current steering dac">Segmented DAC</button>
          <button type="button" class="chip-query" data-q="deltasigma ciff">ΔΣ CIFF Modulator</button>
          <button type="button" class="chip-query" data-q="chopper cfia">Chopper CFIA / INA</button>
          <button type="button" class="chip-query" data-q="sizing_opt">Pareto sizing_opt.py</button>
          <button type="button" class="chip-query" data-q="psf_audit">PSF OP/STB Auditor</button>
          <button type="button" class="chip-query" data-q="§9.2">§9.2 (Cascode OTA)</button>
        </div>
      </section>

      ${renderDesignCycleBannerHtml()}
      ${renderCoordHitsStripHtml(coordHits)}
      ${glossaryStrip}

      <div class="section-bar">
        <h2>Danh mục Thẻ Tri thức &amp; Playbook${escapeHtml(domLabel)}${escapeHtml(chLabel)}${escapeHtml(stageLabel)}</h2>
        <span class="meta">Hiển thị <strong>${nodes.length}</strong> / ${totalNodes} thẻ</span>
      </div>

      ${
        nodes.length === 0
          ? `<div class="status-card"><h3>Không có thẻ khớp bộ lọc hiện tại</h3><p>Hãy thử gõ số mục (<code>§9.2</code>), phương trình (<code>Eq. 5.26</code>), từ khóa PMIC/AMS (<code>buck</code>, <code>tow-thomas</code>), hoặc bấm Đặt lại bộ lọc.</p></div>`
          : `<div class="node-grid">${nodes.map(renderNodeCardHtml).join("")}</div>`
      }
    `;

    for (const chip of el.view.querySelectorAll(".chip-query")) {
      chip.addEventListener("click", () => setSearchQuery(chip.dataset.q || ""));
    }
    for (const stepBtn of el.view.querySelectorAll("[data-stage]")) {
      stepBtn.addEventListener("click", () => {
        const s = Number(stepBtn.getAttribute("data-stage"));
        state.filterStage = state.filterStage === s ? null : s;
        renderNodesCatalogView();
        renderSidebarControls();
      });
    }
    document.getElementById("btn-clear-stage")?.addEventListener("click", () => {
      state.filterStage = null;
      renderNodesCatalogView();
      renderSidebarControls();
    });
    document.getElementById("btn-open-cycle-svg")?.addEventListener("click", (ev) => {
      const svgUrl = ev.currentTarget.getAttribute("data-svg");
      openSvgModal(svgUrl, "Chu trình Thiết kế & Tối ưu Khép kín 7 Bước Cadence IC617 – Spectre – Codex");
    });
    document.getElementById("jump-all-glossary")?.addEventListener("click", () => {
      location.hash = "#glossary";
    });
    document.getElementById("jump-open-coords")?.addEventListener("click", () => {
      location.hash = "#coords";
    });
    document.getElementById("jump-open-skills")?.addEventListener("click", () => {
      location.hash = "#skills";
    });
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

  // ---------------- Deterministic 2D Coordinate Grid Layout Engine ----------------
  function computeDeterministic2DGrid(nodes) {
    // Returns { posMap, swimlanes, maxCol, totalWidth, totalHeight }
    // Uses node.coord_2d.grid_col if available, else computes (X = Chapter 1..19 or EDA 20, Y = 4 Functional Swimlanes)
    const DOMAIN_CH = {
      foundations: [1, 2, 11, 17],
      "stages-and-mirrors": [3, 4, 5],
      "dynamics-noise-feedback": [6, 7, 8],
      "opamps-and-compensation": [9, 10],
      "references-and-biasing": [12],
      "sampled-and-clocked": [13, 15, 16],
      "nonideal-and-physical": [14, 18, 19],
    };

    function getTrackIdx(n) {
      if (isSkillNode(n)) return 3;
      if (n.kind === "topology") return 1;
      if (n.kind === "technique") return 2;
      return 0;
    }

    function getGridCol(n) {
      if (n.coord_2d && Number.isFinite(n.coord_2d.grid_col)) {
        return n.coord_2d.grid_col;
      }
      if (isPmicNode(n)) return 20;
      if (isAmsNode(n)) return 21;
      if (isSkillNode(n)) {
        const chs = n.chapters || [];
        if (
          /ic617|ocean|psf|techsweep|gmid-lut|gm-id-lookup|closed-loop-sizing|veriloga|pex|cace|25-topology|montecarlo|layout-common-centroid/.test(n.id) ||
          chs.length === 0 ||
          chs.length > 4
        ) {
          return 22;
        }
        return chs[0];
      }
      const domChs = DOMAIN_CH[n.domain] || [];
      for (const r of n.razavi_refs || []) {
        if (domChs.includes(Number(r.chapter))) return Number(r.chapter);
      }
      return Number(n.chapters?.[0] || 1);
    }

    // Group nodes into cells [trackIdx][col] across Columns 1..22
    const cells = [new Map(), new Map(), new Map(), new Map()];
    for (const n of nodes) {
      const tIdx = getTrackIdx(n);
      const col = Math.max(1, Math.min(22, getGridCol(n)));
      if (!cells[tIdx].has(col)) cells[tIdx].set(col, []);
      cells[tIdx].get(col).push(n);
    }

    // Sort deterministically inside each cell by section / id
    for (let t = 0; t < 4; t++) {
      for (const arr of cells[t].values()) {
        arr.sort((a, b) => {
          const sa = String(a.razavi_refs?.[0]?.section || "");
          const sb = String(b.razavi_refs?.[0]?.section || "");
          return sa.localeCompare(sb, undefined, { numeric: true }) || a.id.localeCompare(b.id);
        });
      }
    }

    // Determine active columns so filtered views stay compact & crisp!
    const usedColsSet = new Set();
    for (let t = 0; t < 4; t++) {
      for (const c of cells[t].keys()) usedColsSet.add(c);
    }
    const orderedCols = Array.from(usedColsSet).sort((a, b) => a - b);
    const colIndexMap = new Map();
    orderedCols.forEach((c, idx) => colIndexMap.set(c, idx));

    const COL_W = 216;
    const LEFT_PAD = 150;
    const ROW_H = 58;
    const LANE_PAD_TOP = 36;
    const LANE_PAD_BOT = 20;

    let curY = 74;
    const swimlanes = [];
    const posMap = new Map();

    for (let t = 0; t < 4; t++) {
      let maxRowsInTrack = 0;
      for (const arr of cells[t].values()) {
        if (arr.length > maxRowsInTrack) maxRowsInTrack = arr.length;
      }
      if (maxRowsInTrack === 0) continue;

      const laneH = LANE_PAD_TOP + maxRowsInTrack * ROW_H + LANE_PAD_BOT;
      swimlanes.push({
        ...TRACK_META[t],
        y: curY,
        h: laneH,
        rows: maxRowsInTrack,
      });

      for (const [col, arr] of cells[t].entries()) {
        const cIdx = colIndexMap.get(col) || 0;
        const cx = LEFT_PAD + cIdx * COL_W;
        arr.forEach((n, rIdx) => {
          const cy = curY + LANE_PAD_TOP + rIdx * ROW_H + 22;
          posMap.set(n.id, {
            x: cx,
            y: cy,
            grid_col: col,
            grid_row: n.coord_2d?.grid_row ?? rIdx + 1,
            track: TRACK_META[t].short,
            node: n,
          });
        });
      }
      curY += laneH + 14;
    }

    const totalWidth = Math.max(960, LEFT_PAD + orderedCols.length * COL_W + 90);
    const totalHeight = Math.max(520, curY + 30);
    return { posMap, swimlanes, orderedCols, colIndexMap, COL_W, LEFT_PAD, totalWidth, totalHeight };
  }

  // ---------------- Interactive Pan/Zoom Graph (Ego & Global 2D Coordinate Grid) ----------------
  function mountInteractiveGraph(viewportEl, inspectorEl, centerNodeId, controls = null) {
    let panX = 16;
    let panY = 12;
    let scale = 1;
    let dragging = false;
    let startX = 0;
    let startY = 0;

    const nodesToDraw = [];
    const edgesToDraw = [];
    let gridDecorations = "";
    let canvasW = 860;
    let canvasH = 390;

    if (centerNodeId) {
      const center = state.nodeMap.get(centerNodeId);
      const inEdges = state.adjIn.get(centerNodeId) || [];
      const outEdges = state.adjOut.get(centerNodeId) || [];

      const leftIds = Array.from(new Set(inEdges.map((e) => e.from))).slice(0, 8);
      const rightIds = Array.from(new Set(outEdges.map((e) => e.to).filter((id) => !leftIds.includes(id)))).slice(0, 8);

      const pos = new Map();
      pos.set(centerNodeId, { x: 430, y: 195, role: "center", node: center });

      leftIds.forEach((id, idx) => {
        const y = 46 + ((idx + 0.5) * 300) / Math.max(1, leftIds.length);
        pos.set(id, { x: 135, y, role: "in", node: state.nodeMap.get(id) });
      });
      rightIds.forEach((id, idx) => {
        const y = 46 + ((idx + 0.5) * 300) / Math.max(1, rightIds.length);
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
      // Filtered Global 2D Coordinate Graph!
      const qWords = foldWords(state.query);
      const qTokens = qWords ? qWords.split(/\s+/).filter(Boolean) : [];

      const visibleNodes = (state.router.nodes || []).filter((n) => {
        if (state.graphScope === "razavi" && !isRazaviCoreNode(n)) return false;
        if (state.graphScope === "pmic" && !isPmicNode(n)) return false;
        if (state.graphScope === "ams" && !isAmsNode(n)) return false;
        if (state.graphScope === "skill" && !isSkillNode(n)) return false;
        if (state.filterDomain !== "all" && n.domain !== state.filterDomain) return false;
        if (state.filterChapter !== null && !(n.chapters || []).includes(state.filterChapter)) return false;
        if (!passesKindFilter(nodeOrSelf(n), state.filterKind)) return false;
        if (state.filterStage !== null && !getNodeDesignStages(n).includes(state.filterStage)) return false;
        if (qTokens.length > 0) {
          const hay = `${n.search_text || ""} ${foldWords(`${n.id} ${n.title_vi} ${n.title_en}`)}`;
          if (!qTokens.every((t) => hay.includes(t))) return false;
        }
        return true;
      });

      function nodeOrSelf(x) {
        return x;
      }

      const layout = computeDeterministic2DGrid(visibleNodes);
      canvasW = layout.totalWidth;
      canvasH = layout.totalHeight;

      // Build X-axis Column Headers + Vertical Grid Guides + Y-axis Swimlanes
      const laneRects = layout.swimlanes
        .map(
          (ln) => `
          <rect x="20" y="${ln.y}" width="${layout.totalWidth - 40}" height="${ln.h}" rx="8" fill="${ln.tint}" stroke="var(--border-hairline)" stroke-width="1"></rect>
          <text x="34" y="${ln.y + 21}" font-size="11" font-weight="700" fill="var(--ink-secondary)" letter-spacing="0.04em">${escapeHtml(ln.label)}</text>
        `
        )
        .join("");

      const colHeaders = layout.orderedCols
        .map((col, idx) => {
          const cx = layout.LEFT_PAD + idx * layout.COL_W;
          const chMeta = (state.router.chapters || []).find((c) => c.chapter === col);
          let badge = `Ch.${String(col).padStart(2, "0")}`;
          let sub = (chMeta?.title_vi || "").slice(0, 22);
          if (col === 20) {
            badge = "PMIC · Layer 8";
            sub = "Buck / Boost / Capless LDO";
          } else if (col === 21) {
            badge = "AMS · Layer 9";
            sub = "Filter / DAC / ΔΣ / INA";
          } else if (col === 22) {
            badge = "EDA · Layer 10";
            sub = "IC617 / psf_audit / Opt";
          }
          return `
            <g class="g-col-header">
              <line x1="${cx}" y1="56" x2="${cx}" y2="${layout.totalHeight - 24}" stroke="var(--border-hairline)" stroke-width="1" stroke-dasharray="4,4"></line>
              <rect x="${cx - 88}" y="14" width="176" height="38" rx="6" fill="var(--bg-surface)" stroke="var(--border-strong)" stroke-width="1"></rect>
              <text x="${cx}" y="30" text-anchor="middle" font-size="11" font-family="Consolas,monospace" font-weight="700" fill="var(--accent-ink)">${escapeHtml(badge)}</text>
              <text x="${cx}" y="44" text-anchor="middle" font-size="10" fill="var(--ink-muted)">${escapeHtml(sub)}</text>
            </g>
          `;
        })
        .join("");

      gridDecorations = laneRects + colHeaders;

      for (const [id, info] of layout.posMap.entries()) {
        nodesToDraw.push({ id, ...info, role: "global" });
      }
      for (const e of state.edges) {
        if (state.graphRel !== "all" && e.rel !== state.graphRel) continue;
        if (layout.posMap.has(e.from) && layout.posMap.has(e.to)) {
          edgesToDraw.push({ edge: e, p1: layout.posMap.get(e.from), p2: layout.posMap.get(e.to) });
        }
      }

      const rect = viewportEl.getBoundingClientRect();
      const vw = rect.width || 1050;
      const vh = rect.height || 580;
      scale = Math.min(1.0, Math.max(0.42, Math.min((vw - 24) / Math.min(canvasW, 2200), (vh - 24) / canvasH)));
      panX = 12;
      panY = 8;

      if (controls) {
        controls.fit = () => {
          const r2 = viewportEl.getBoundingClientRect();
          scale = Math.min(1.0, Math.max(0.24, Math.min(((r2.width || 1050) - 24) / canvasW, ((r2.height || 580) - 24) / canvasH)));
          panX = 12;
          panY = 8;
          applyTransform();
        };
        controls.zoomBy = (f) => {
          scale = Math.min(2.6, Math.max(0.22, scale * f));
          applyTransform();
        };
        controls.reset100 = () => {
          scale = 0.85;
          panX = 14;
          panY = 10;
          applyTransform();
        };
        controls.panToCol = (colNum) => {
          const cIdx = layout.colIndexMap.get(colNum);
          if (cIdx === undefined) return;
          const cx = layout.LEFT_PAD + cIdx * layout.COL_W;
          const r2 = viewportEl.getBoundingClientRect();
          scale = 0.88;
          panX = (r2.width || 960) / 2 - cx * scale;
          panY = 14;
          applyTransform();
        };
      }
    }

    const defs = Object.entries(EDGE_COLORS)
      .map(
        ([rel, col]) => `
        <marker id="arrow-${rel}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
          <path d="M 0 1.2 L 9.5 5 L 0 8.8 z" fill="${col}"></path>
        </marker>`
      )
      .join("");

    const edgePaths = edgesToDraw
      .map((item, idx) => {
        const { edge, p1, p2 } = item;
        const col = EDGE_COLORS[edge.rel] || "#5e6266";
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        let dPath = "";
        if (Math.abs(dx) < 25) {
          // Same column vertical connection (e.g. Theory <-> Skill inside same chapter!)
          const y1 = p1.y + (dy >= 0 ? 21 : -21);
          const y2 = p2.y + (dy >= 0 ? -23 : 23);
          const bendX = p1.x + 96;
          dPath = `M ${p1.x + 78} ${y1} C ${bendX} ${y1}, ${bendX} ${y2}, ${p2.x + 78} ${y2}`;
        } else {
          const x1 = p1.x + (dx >= 0 ? 86 : -86);
          const x2 = p2.x + (dx >= 0 ? -90 : 90);
          const cx1 = x1 + dx * 0.38;
          const cx2 = x2 - dx * 0.38;
          dPath = `M ${x1} ${p1.y} C ${cx1} ${p1.y}, ${cx2} ${p2.y}, ${x2} ${p2.y}`;
        }
        const dash = edge.rel === "trades_off_with" ? 'stroke-dasharray="5,4"' : "";
        const midX = (p1.x + p2.x) / 2;
        const midY = (p1.y + p2.y) / 2 - 5;
        return `
          <g class="g-edge" data-edge-idx="${idx}" data-from="${escapeHtml(edge.from)}" data-to="${escapeHtml(edge.to)}" style="cursor:pointer">
            <path d="${dPath}" fill="none" stroke="${col}" stroke-width="${centerNodeId ? 1.85 : 1.45}" ${dash} marker-end="url(#arrow-${edge.rel})"></path>
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
        const stroke = isCenter
          ? "#16594f"
          : isSkillNode(n)
          ? "#5b3b8c"
          : n.kind === "topology"
          ? "#1f6c9f"
          : n.kind === "technique"
          ? "#956400"
          : "#346538";
        const fill = isCenter ? "var(--accent-bg)" : "var(--bg-surface)";
        const shortLabel = (n.title_vi || n.title_en || n.id).slice(0, 24) + ((n.title_vi || n.title_en || n.id).length > 24 ? "…" : "");
        const secTag = n.razavi_refs?.[0]?.section ? `§${n.razavi_refs[0].section.split(/[,;\s-]/)[0]}` : "";
        const chTag = isPmicNode(n)
          ? `PMIC · ${n.kind}`
          : isAmsNode(n)
          ? `AMS · ${n.kind}`
          : isSkillNode(n)
          ? `Skill · Ch.${n.chapters?.[0] || "EDA"}`
          : `Ch.${n.chapters?.[0] || "?"}${secTag ? ` ${secTag}` : ""} · ${n.kind}`;
        return `
          <g class="g-node" data-node-id="${escapeHtml(item.id)}" transform="translate(${item.x - 86}, ${item.y - 21})" style="cursor:pointer">
            <rect width="172" height="42" rx="7" fill="${fill}" stroke="${stroke}" stroke-width="${isCenter ? 2.4 : 1.4}"></rect>
            <text x="8" y="15" font-size="9.8" font-family="Consolas,monospace" fill="var(--ink-secondary)">${escapeHtml(chTag.slice(0, 26))}</text>
            <text x="8" y="31" font-size="11.2" font-weight="${isCenter ? "700" : "600"}" fill="var(--ink-primary)">${escapeHtml(shortLabel)}</text>
          </g>
        `;
      })
      .join("");

    const vbW = centerNodeId ? 860 : Math.min(1180, canvasW);
    const vbH = centerNodeId ? 390 : Math.min(640, canvasH);

    viewportEl.innerHTML = `
      <svg class="graph-svg" viewBox="0 0 ${vbW} ${vbH}" role="img" aria-label="Đồ thị tọa độ 2D tiến hóa cấu trúc mạch và GitHub EDA skills">
        <defs>${defs}</defs>
        <g id="graph-pan-layer" transform="translate(${panX},${panY}) scale(${scale})">
          ${gridDecorations}
          ${edgePaths}
          ${nodeBoxes}
        </g>
      </svg>
    `;

    const svgEl = viewportEl.querySelector(".graph-svg");
    const panLayer = viewportEl.querySelector("#graph-pan-layer");
    function applyTransform() {
      panLayer.setAttribute("transform", `translate(${panX},${panY}) scale(${scale})`);
    }

    // Hover & Focus Neighborhood Highlighting
    const nodeDomMap = new Map();
    for (const gNode of viewportEl.querySelectorAll(".g-node")) {
      nodeDomMap.set(gNode.getAttribute("data-node-id"), gNode);
    }
    const edgeDomList = Array.from(viewportEl.querySelectorAll(".g-edge"));

    function highlightNeighborhood(focusId) {
      if (!focusId || !nodeDomMap.has(focusId)) {
        svgEl.classList.remove("has-focus");
        for (const gn of nodeDomMap.values()) gn.classList.remove("is-neighbor", "is-center");
        for (const ge of edgeDomList) ge.classList.remove("is-neighbor");
        return;
      }
      svgEl.classList.add("has-focus");
      const neighbors = new Set([focusId]);
      for (const ge of edgeDomList) {
        const u = ge.getAttribute("data-from");
        const v = ge.getAttribute("data-to");
        if (u === focusId || v === focusId) {
          ge.classList.add("is-neighbor");
          neighbors.add(u);
          neighbors.add(v);
        } else {
          ge.classList.remove("is-neighbor");
        }
      }
      for (const [nid, gn] of nodeDomMap.entries()) {
        gn.classList.toggle("is-neighbor", neighbors.has(nid));
        gn.classList.toggle("is-center", nid === focusId);
      }

      const fNode = state.nodeMap.get(focusId);
      if (fNode && inspectorEl && !centerNodeId) {
        const inCnt = (state.adjIn.get(focusId) || []).length;
        const outCnt = (state.adjOut.get(focusId) || []).length;
        const posInfo = nodesToDraw.find((x) => x.id === focusId);
        const coordLabel = posInfo ? `[Col ${posInfo.grid_col}, Row ${posInfo.grid_row} · ${posInfo.track}]` : "";
        inspectorEl.innerHTML = `
          <div>
            <code>${escapeHtml(coordLabel)}</code>
            <strong style="margin-left:6px">${escapeHtml(fNode.title_vi)}</strong>
            <span class="meta">(${inCnt} cạnh vào · ${outCnt} cạnh ra · Nhấp để đọc thẻ 6 khối, Shift+Nhấp để ghim lân cận)</span>
          </div>
          <a class="node-ref-pill" href="#node/${escapeHtml(focusId)}">Mở ${escapeHtml(focusId)} →</a>
        `;
      }
    }

    if (state.graphFocusNodeId && !centerNodeId && nodeDomMap.has(state.graphFocusNodeId)) {
      const targetInfo = nodesToDraw.find((x) => x.id === state.graphFocusNodeId);
      if (targetInfo) {
        const r2 = viewportEl.getBoundingClientRect();
        scale = 0.92;
        panX = (r2.width || 960) / 2 - targetInfo.x * scale;
        panY = (r2.height || 560) / 2 - targetInfo.y * scale;
        applyTransform();
      }
      highlightNeighborhood(state.graphFocusNodeId);
    }

    viewportEl.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        const factor = ev.deltaY < 0 ? 1.12 : 0.89;
        scale = Math.min(2.6, Math.max(0.22, scale * factor));
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

    for (const gNode of nodeDomMap.values()) {
      const nid = gNode.getAttribute("data-node-id");
      gNode.addEventListener("mouseenter", () => {
        if (!centerNodeId && !state.graphFocusNodeId) highlightNeighborhood(nid);
      });
      gNode.addEventListener("mouseleave", () => {
        if (!centerNodeId && !state.graphFocusNodeId) highlightNeighborhood(null);
      });
      gNode.addEventListener("click", (ev) => {
        if (!centerNodeId && ev.shiftKey) {
          state.graphFocusNodeId = state.graphFocusNodeId === nid ? null : nid;
          highlightNeighborhood(state.graphFocusNodeId);
          return;
        }
        if (nid) location.hash = `#node/${nid}`;
      });
    }

    for (const gEdge of edgeDomList) {
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

  // ---------------- View 1: 2D Coordinate Graph Workspace ----------------
  function renderGlobalGraphView() {
    const controls = {};
    const scopeBtns = [
      ["all", "Tất cả 10 Tầng"],
      ["razavi", "Razavi Ch.01–19"],
      ["pmic", "PMIC (Col 20)"],
      ["ams", "AMS & Hệ thống (Col 21)"],
      ["skill", "Cadence-Codex Skills"],
    ];
    const relBtns = [
      ["all", "Mọi quan hệ"],
      ["upgrades_to", "upgrades_to"],
      ["fixes", "fixes"],
      ["compensated_by", "compensated_by"],
      ["requires", "requires"],
      ["governed_by", "governed_by"],
      ["trades_off_with", "trades_off_with"],
    ];

    el.view.innerHTML = `
      <section class="hero-header" style="margin-bottom:14px;padding-bottom:12px">
        <p class="eyebrow">DETERMINISTIC 22-COLUMN 2D ARCHITECTURE GRAPH (X = CH.01–19 + PMIC + AMS + EDA · Y = 4 TRACKS)</p>
        <h1>Bản đồ Đồ thị Tọa độ 2D Toàn cục (10 Tầng · 22 Cột Không Chồng Lấn)</h1>
        <p>Mỗi thẻ được định vị tất định trên lưới <strong>(X = Chương 01–19 + Cột 20 PMIC + Cột 21 AMS + Cột 22 EDA Khép kín, Y = 4 Làn Vai trò Vật lý → Cấu trúc → Kỹ thuật → GitHub/Spectre Testbench)</strong>. Rê chuột lên thẻ để làm nổi bật mạng lân cận, <code>Shift + Nhấp</code> để ghim tâm, hoặc nhấp thẻ để đọc chi tiết.</p>
      </section>

      <section class="graph-panel">
        <div class="graph-toolbar">
          <div class="graph-filter-row" role="group" aria-label="Phạm vi đồ thị">
            ${scopeBtns
              .map(
                ([val, lbl]) =>
                  `<button type="button" class="pill ${state.graphScope === val ? "is-active" : ""}" data-gscope="${val}">${escapeHtml(lbl)}</button>`
              )
              .join("")}
          </div>
          <div class="graph-filter-row" role="group" aria-label="Điều khiển khung nhìn">
            <button type="button" class="btn-subtle" id="g-btn-fit">Vừa toàn khung</button>
            <button type="button" class="btn-subtle" id="g-btn-zout">-</button>
            <button type="button" class="btn-subtle" id="g-btn-z100">100%</button>
            <button type="button" class="btn-subtle" id="g-btn-zin">+</button>
            ${state.graphFocusNodeId ? `<button type="button" class="btn-primary" id="g-btn-unpin">Bỏ ghim (${escapeHtml(state.graphFocusNodeId)})</button>` : ""}
          </div>
        </div>
        <div class="graph-toolbar" style="padding-top:7px;padding-bottom:7px;background:var(--bg-canvas)">
          <div class="graph-filter-row" role="group" aria-label="Lọc loại cạnh">
            ${relBtns
              .map(([val, lbl]) => {
                const dot = EDGE_COLORS[val] ? `<i class="legend-dot" style="background:${EDGE_COLORS[val]}"></i>` : "";
                return `<button type="button" class="pill ${state.graphRel === val ? "is-active" : ""}" data-grel="${val}">${dot}${escapeHtml(lbl)}</button>`;
              })
              .join("")}
          </div>
          <div class="graph-filter-row" aria-label="Nhảy nhanh tới cột chương">
            <span style="font-size:11px;color:var(--ink-muted)">Nhảy cột:</span>
            ${[1, 3, 5, 8, 9, 10, 12, 13, 15, 16, 19, 20, 21, 22]
              .map((c) => {
                const lbl = c === 20 ? "PMIC" : c === 21 ? "AMS" : c === 22 ? "EDA" : `Ch.${c}`;
                return `<button type="button" class="clear-btn" data-gcol="${c}">${lbl}</button>`;
              })
              .join("")}
          </div>
        </div>
        <div class="graph-viewport full-height" id="global-graph-viewport"></div>
        <div class="graph-inspector" id="global-graph-inspector">
          <span>Rê chuột vào Node để soi vùng lân cận 1 bước; rê chuột vào Cạnh để đọc điều kiện <code>when</code> và chi phí đánh đổi <code>cost</code>.</span>
        </div>
      </section>
    `;

    mountInteractiveGraph(
      document.getElementById("global-graph-viewport"),
      document.getElementById("global-graph-inspector"),
      null,
      controls
    );

    for (const b of el.view.querySelectorAll("[data-gscope]")) {
      b.addEventListener("click", () => {
        state.graphScope = b.getAttribute("data-gscope") || "all";
        renderGlobalGraphView();
      });
    }
    for (const b of el.view.querySelectorAll("[data-grel]")) {
      b.addEventListener("click", () => {
        state.graphRel = b.getAttribute("data-grel") || "all";
        renderGlobalGraphView();
      });
    }
    for (const b of el.view.querySelectorAll("[data-gcol]")) {
      b.addEventListener("click", () => {
        controls.panToCol?.(Number(b.getAttribute("data-gcol")));
      });
    }
    document.getElementById("g-btn-fit")?.addEventListener("click", () => controls.fit?.());
    document.getElementById("g-btn-zin")?.addEventListener("click", () => controls.zoomBy?.(1.18));
    document.getElementById("g-btn-zout")?.addEventListener("click", () => controls.zoomBy?.(0.84));
    document.getElementById("g-btn-z100")?.addEventListener("click", () => controls.reset100?.());
    document.getElementById("g-btn-unpin")?.addEventListener("click", () => {
      state.graphFocusNodeId = null;
      renderGlobalGraphView();
    });
  }

  // ---------------- View 2: 19-Chapter Book Coordinate Navigator ----------------
  async function renderBookCoordsView() {
    if (!state.coords) {
      el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG TẢI TỌA ĐỘ 19 CHƯƠNG &amp; 20_INDEX</p><h2>Đang nạp book-coordinates.json…</h2></div>`;
      await ensureCoordsLoaded();
    }
    const coords = state.coords || { chapters: [], sections: [], equations: [], index_terms: [] };
    const parsed = parseCoordinateQuery(state.query);
    const qWords = foldWords(state.query);
    const qTokens = qWords ? qWords.split(/\s+/).filter(Boolean) : [];

    // Auto-switch sub-tab if user typed Eq. or Section
    let activeTab = state.coordsTab;
    if (parsed.type === "equation") activeTab = "equations";
    else if (parsed.type === "section") activeTab = "sections";

    let bodyHtml = "";

    if (activeTab === "sections") {
      const chaptersList = coords.chapters.length
        ? coords.chapters
        : (state.router.chapters || []).map((c) => ({ chapter: c.chapter, title_en: c.title_en, title_vi: c.title_vi }));

      const filteredSections = coords.sections.filter((s) => {
        if (state.filterChapter !== null && s.chapter !== state.filterChapter) return false;
        if (parsed.type === "section") {
          return s.section_id === parsed.section || s.section_id.startsWith(`${parsed.section}.`) || parsed.section.startsWith(`${s.section_id}.`);
        }
        if (parsed.type === "page") return pageMatchesRange(parsed.page, s.book_pages);
        if (parsed.type === "chapter") return s.chapter === parsed.chapter;
        if (qTokens.length > 0) return qTokens.every((t) => s.search_key.includes(t));
        return true;
      });

      const byCh = new Map();
      for (const s of filteredSections) {
        if (!byCh.has(s.chapter)) byCh.set(s.chapter, []);
        byCh.get(s.chapter).push(s);
      }

      const chapterBlocks = chaptersList
        .filter((ch) => state.filterChapter === null || ch.chapter === state.filterChapter)
        .filter((ch) => !state.query || byCh.has(ch.chapter))
        .map((ch) => {
          const chNum = Number(ch.chapter);
          const secs = byCh.get(chNum) || [];
          const isOpen = Boolean(state.query) || state.filterChapter !== null || state.expandedChapters.has(chNum);
          const pageSpan =
            ch.book_page_start && ch.book_page_end ? `Trang sách ${ch.book_page_start}–${ch.book_page_end}` : "";
          return `
            <div class="chapter-block">
              <button type="button" class="chapter-block-header" data-toggle-ch="${chNum}" aria-expanded="${isOpen}">
                <div>
                  <span class="badge badge-neutral">Chương ${String(chNum).padStart(2, "0")}</span>
                  <strong style="font-size:15.5px;margin-left:8px">${escapeHtml(ch.title_vi)}</strong>
                  <span style="font-size:13px;color:var(--ink-muted);margin-left:8px">${escapeHtml(ch.title_en)}</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;font-size:12px;color:var(--ink-muted)">
                  ${pageSpan ? `<span>${escapeHtml(pageSpan)}</span>` : ""}
                  <span class="nav-count">${secs.length} mục</span>
                  <span style="font-family:var(--font-mono);font-weight:700">${isOpen ? "−" : "+"}</span>
                </div>
              </button>
              ${
                isOpen && secs.length > 0
                  ? `<div class="section-table">
                      ${secs
                        .map(
                          (s) => `
                        <div class="section-row">
                          <div>
                            <code style="font-weight:700;color:var(--accent-ink)">§${escapeHtml(s.section_id)}</code>
                            ${s.book_pages ? `<div style="font-size:11px;color:var(--ink-muted);margin-top:2px">p.${escapeHtml(s.book_pages)}</div>` : ""}
                            ${s.pdf_pages ? `<div style="font-size:10.5px;color:var(--ink-muted)">PDF p.${escapeHtml(s.pdf_pages)}</div>` : ""}
                          </div>
                          <div>
                            <strong style="font-size:14px">${escapeHtml(s.title_vi || s.title_en)}</strong>
                            ${s.title_vi && s.title_en ? `<div style="font-size:12px;color:var(--ink-muted)">${escapeHtml(s.title_en)}</div>` : ""}
                            ${s.summary_vi ? `<div style="font-size:12.8px;color:var(--ink-secondary);margin-top:3px">${escapeHtml(s.summary_vi)}</div>` : ""}
                            ${
                              (s.key_equations || []).length || (s.key_figures || []).length
                                ? `<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px;font-size:11px;color:var(--ink-muted)">
                                    ${(s.key_equations || []).slice(0, 6).map((eq) => `<span class="badge badge-neutral">Eq ${escapeHtml(eq)}</span>`).join("")}
                                    ${(s.key_figures || []).slice(0, 4).map((fg) => `<span class="badge badge-neutral">${escapeHtml(fg)}</span>`).join("")}
                                  </div>`
                                : ""
                            }
                          </div>
                          <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-end">
                            ${renderNodePillsHtml(s.primary_nodes, 3)}
                          </div>
                        </div>`
                        )
                        .join("")}
                    </div>`
                  : ""
              }
            </div>
          `;
        })
        .join("");

      bodyHtml = `
        <div class="section-bar">
          <h2>Cây Mục lục Tọa độ chi tiết (${filteredSections.length} mục khớp)</h2>
          <div style="display:flex;gap:10px">
            <button type="button" class="link-btn" id="btn-expand-all-ch">Mở tất cả 19 chương</button>
            <button type="button" class="link-btn" id="btn-collapse-all-ch">Thu gọn</button>
          </div>
        </div>
        ${
          coords.sections.length === 0
            ? `<div class="status-card"><h3>Đang đồng bộ chỉ mục tọa độ chi tiết</h3><p>Chưa tìm thấy dữ liệu mục trong <code>kb/coordinates/book-coordinates.json</code>.</p></div>`
            : chapterBlocks
        }
      `;
    } else if (activeTab === "equations") {
      const eqMatches = coords.equations.filter((e) => {
        if (state.filterChapter !== null && e.chapter !== state.filterChapter) return false;
        if (parsed.type === "equation") return e.eq_num === parsed.eq || e.eq_num.startsWith(parsed.eq);
        if (parsed.type === "section") return e.section === parsed.section || e.section.startsWith(`${parsed.section}.`);
        if (parsed.type === "page") return Number(e.book_page) === parsed.page || pageMatchesRange(parsed.page, String(e.book_page));
        if (qTokens.length > 0) return qTokens.every((t) => e.search_key.includes(t));
        return true;
      });
      const slice = eqMatches.slice(0, state.eqLimit);

      bodyHtml = `
        <div class="section-bar">
          <h2>Phương trình Cột mốc Razavi 2nd Ed. (${eqMatches.length} phương trình)</h2>
          <span class="meta">Hiển thị ${slice.length} phương trình</span>
        </div>
        <div class="eq-grid">
          ${slice
            .map(
              (eq) => `
            <article class="eq-card">
              <div class="card-topline">
                <span class="badge badge-law">${escapeHtml(eq.eq_id)}</span>
                <span class="badge badge-neutral">Ch.${eq.chapter}${eq.section ? ` §${escapeHtml(eq.section)}` : ""}${eq.book_page ? ` · p.${escapeHtml(eq.book_page)}` : ""}</span>
              </div>
              ${eq.latex ? `<div class="math-display">${renderMathToken(eq.latex, true)}</div>` : ""}
              <p style="margin:0;font-size:13.5px;color:var(--ink-secondary)">${escapeHtml(eq.meaning_vi)}</p>
              <div style="margin-top:auto;padding-top:6px;display:flex;flex-wrap:wrap;gap:6px">
                ${renderNodePillsHtml(eq.node_ids, 3)}
              </div>
            </article>`
            )
            .join("")}
        </div>
        ${
          eqMatches.length > slice.length
            ? `<div style="margin-top:18px;text-align:center"><button type="button" class="btn-subtle" id="btn-more-eq">Hiện thêm 60 phương trình (${eqMatches.length - slice.length} còn lại)</button></div>`
            : ""
        }
      `;
    } else {
      const idxMatches = coords.index_terms.filter((it) => {
        if (state.filterChapter !== null && !(it.chapters || []).includes(state.filterChapter)) return false;
        if (parsed.type === "page") return pageMatchesRange(parsed.page, it.book_pages);
        if (qTokens.length > 0) return qTokens.every((t) => it.search_key.includes(t));
        return true;
      });
      const slice = idxMatches.slice(0, state.indexLimit);

      bodyHtml = `
        <div class="section-bar">
          <h2>Chỉ mục Chủ đề Cuối sách 20_Index.pdf (${idxMatches.length} mục)</h2>
          <span class="meta">Hiển thị ${slice.length} mục</span>
        </div>
        <div class="glossary-list">
          ${slice
            .map(
              (it) => `
            <article class="glossary-item">
              <div class="glossary-top">
                <div>
                  <strong style="font-size:15.5px">${escapeHtml(it.term_en)}</strong>
                  ${it.term_vi ? `<span style="font-size:13.5px;color:var(--ink-secondary);margin-left:8px">— ${escapeHtml(it.term_vi)}</span>` : ""}
                  <div style="font-size:12px;color:var(--ink-muted);margin-top:3px">Trang sách Razavi: <code>${escapeHtml(it.book_pages)}</code></div>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:5px">${renderNodePillsHtml(it.mapped_nodes, 3)}</div>
              </div>
            </article>`
            )
            .join("")}
        </div>
        ${
          idxMatches.length > slice.length
            ? `<div style="margin-top:18px;text-align:center"><button type="button" class="btn-subtle" id="btn-more-idx">Hiện thêm 80 mục chỉ mục (${idxMatches.length - slice.length} còn lại)</button></div>`
            : ""
        }
      `;
    }

    el.view.innerHTML = `
      <section class="hero-header" style="margin-bottom:18px;padding-bottom:16px">
        <p class="eyebrow">EXACT RAZAVI 2ND EDITION BOOK COORDINATES · CH.01–CH.19 + 20_INDEX</p>
        <h1>Mục lục Tọa độ Sách 19 Chương, Phương trình &amp; Chỉ mục Trang</h1>
        <p>Đối chiếu 1-1 từng mục <code>§1.1</code>..<code>§19.x</code>, số trang sách gốc, số trang tệp PDF, phương trình cột mốc và chỉ mục <code>20_Index.pdf</code> thẳng tới thẻ tri thức 6 khối tương ứng.</p>
      </section>

      <div class="sub-tabs" role="tablist">
        <button type="button" class="sub-tab ${activeTab === "sections" ? "is-active" : ""}" data-ctab="sections">Cây Mục lục 19 Chương (${coords.sections.length})</button>
        <button type="button" class="sub-tab ${activeTab === "equations" ? "is-active" : ""}" data-ctab="equations">Phương trình Cột mốc (${coords.equations.length})</button>
        <button type="button" class="sub-tab ${activeTab === "index" ? "is-active" : ""}" data-ctab="index">Chỉ mục 20_Index (${coords.index_terms.length})</button>
      </div>

      ${bodyHtml}
    `;

    for (const b of el.view.querySelectorAll("[data-ctab]")) {
      b.addEventListener("click", () => {
        state.coordsTab = b.getAttribute("data-ctab") || "sections";
        renderBookCoordsView();
      });
    }
    for (const hdr of el.view.querySelectorAll("[data-toggle-ch]")) {
      hdr.addEventListener("click", () => {
        const ch = Number(hdr.getAttribute("data-toggle-ch"));
        if (state.expandedChapters.has(ch)) state.expandedChapters.delete(ch);
        else state.expandedChapters.add(ch);
        renderBookCoordsView();
      });
    }
    document.getElementById("btn-expand-all-ch")?.addEventListener("click", () => {
      for (let c = 1; c <= 19; c++) state.expandedChapters.add(c);
      renderBookCoordsView();
    });
    document.getElementById("btn-collapse-all-ch")?.addEventListener("click", () => {
      state.expandedChapters.clear();
      renderBookCoordsView();
    });
    document.getElementById("btn-more-eq")?.addEventListener("click", () => {
      state.eqLimit += 60;
      renderBookCoordsView();
    });
    document.getElementById("btn-more-idx")?.addEventListener("click", () => {
      state.indexLimit += 80;
      renderBookCoordsView();
    });
  }

  // ---------------- View 3: GitHub Practical Skills Catalog ----------------
  async function renderGitHubSkillsView() {
    if (!state.catalog) {
      el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG TẢI KHO GITHUB ANALOG / EDA SKILLS</p><h2>Đang đồng bộ catalog.json…</h2></div>`;
      await ensureCatalogLoaded();
    }

    const repos = state.catalog?.repos || [];
    const qWords = foldWords(state.query);
    const qTokens = qWords ? qWords.split(/\s+/).filter(Boolean) : [];

    const categories = Array.from(new Set(repos.map((r) => r.category).filter(Boolean))).sort();

    const skillPlaybooks = (state.router.nodes || [])
      .filter(isSkillNode)
      .filter((n) => {
        if (state.filterChapter !== null && !(n.chapters || []).includes(state.filterChapter)) return false;
        if (qTokens.length > 0) {
          const ghText = (n.github_refs || []).map((g) => `${g.repo} ${g.use}`).join(" ");
          const hay = `${n.search_text || ""} ${foldWords(`${n.id} ${n.title_vi} ${n.title_en} ${ghText}`)}`;
          if (!qTokens.every((t) => hay.includes(t))) return false;
        }
        return true;
      });

    const filteredRepos = repos.filter((r) => {
      if (state.skillsCategory !== "all" && r.category !== state.skillsCategory) return false;
      if (qTokens.length > 0 && !qTokens.every((t) => r.search_key.includes(t))) return false;
      return true;
    });

    const showPlaybooks = state.skillsTab === "all" || state.skillsTab === "playbooks";
    const showRepos = state.skillsTab === "all" || state.skillsTab === "repos";

    el.view.innerHTML = `
      <section class="hero-header" style="margin-bottom:18px;padding-bottom:16px">
        <p class="eyebrow">LAYER 10 · CLOSED-LOOP CADENCE IC617, SPECTRERF, GM/ID LUT, PARETO OPTIMIZER &amp; 52 VETTED GITHUB REPOS</p>
        <h1>Kho Skills Tối ưu Khép kín Cadence–Codex &amp; 52 Kho GitHub Kiểm định</h1>
        <p>Kết nối trực tiếp <strong>${skillPlaybooks.length}</strong> thẻ Playbook thực chiến (<code>skill-*</code>) và <strong>${repos.length}</strong> kho mã nguồn mở Analog/PMIC/AMS/EDA đã kiểm định giấy phép, commit khóa cứng, độ tương thích Virtuoso IC617 / Spectre 15.1 (RHEL 6.5 Python 2.6.6) và liên kết ngược tới 10 tầng lý thuyết.</p>
      </section>

      <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-bottom:16px">
        <div class="sub-tabs" style="margin-bottom:0" role="tablist">
          <button type="button" class="sub-tab ${state.skillsTab === "all" ? "is-active" : ""}" data-stab="all">Tất cả Playbooks &amp; Repos</button>
          <button type="button" class="sub-tab ${state.skillsTab === "playbooks" ? "is-active" : ""}" data-stab="playbooks">Playbooks Thực chiến (${skillPlaybooks.length})</button>
          <button type="button" class="sub-tab ${state.skillsTab === "repos" ? "is-active" : ""}" data-stab="repos">Vetted GitHub Repos (${filteredRepos.length})</button>
        </div>
        ${
          categories.length > 1
            ? `<div class="role-pills">
                <button type="button" class="pill ${state.skillsCategory === "all" ? "is-active" : ""}" data-scat="all">Mọi nhóm</button>
                ${categories
                  .map(
                    (cat) =>
                      `<button type="button" class="pill ${state.skillsCategory === cat ? "is-active" : ""}" data-scat="${escapeHtml(cat)}">${escapeHtml(cat)}</button>`
                  )
                  .join("")}
              </div>`
            : ""
        }
      </div>

      ${
        showPlaybooks
          ? `
        <div class="section-bar">
          <h2>Thẻ Playbook Thực chiến 6 Khối (eda-and-github-skills)</h2>
          <span class="meta">${skillPlaybooks.length} thẻ thực chiến</span>
        </div>
        <div class="node-grid" style="margin-bottom:28px">
          ${skillPlaybooks.map(renderNodeCardHtml).join("")}
        </div>`
          : ""
      }

      ${
        showRepos
          ? `
        <div class="section-bar">
          <h2>Danh mục Kho GitHub Analog / EDA Đã Kiểm định (catalog.json)</h2>
          <span class="meta">${filteredRepos.length} repositories</span>
        </div>
        <div class="repo-grid">
          ${filteredRepos
            .map(
              (r) => `
            <article class="repo-card">
              <div class="card-topline">
                <span class="badge badge-skill">${escapeHtml(r.quality_tier)}</span>
                <div style="display:flex;gap:5px;flex-wrap:wrap">
                  <span class="badge badge-neutral">${escapeHtml(r.license)}</span>
                  ${r.stars !== null ? `<span class="badge badge-neutral">${escapeHtml(r.stars)} stars</span>` : ""}
                </div>
              </div>
              <h3 style="margin:2px 0;font-size:16px">
                <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.repo)} ↗</a>
              </h3>
              <div style="font-size:11.5px;font-family:var(--font-mono);color:var(--ink-muted)">
                ${escapeHtml(r.category)} · commit/ref: ${escapeHtml(String(r.pinned).slice(0, 16))}
              </div>
              <p style="margin:0;font-size:13.5px;color:var(--ink-secondary)">${escapeHtml(r.summary_vi)}</p>
              <div style="font-size:12px;background:var(--bg-canvas);border:1px solid var(--border-hairline);padding:8px 10px;border-radius:6px;color:var(--ink-secondary)">
                <strong style="color:var(--accent-ink)">IC617 / Spectre 15.1:</strong> ${escapeHtml(r.ic617_compatibility)}
              </div>
              ${
                r.key_techniques.length
                  ? `<div class="tag-cloud">${r.key_techniques
                      .slice(0, 4)
                      .map((kt) => `<span class="badge badge-neutral">${escapeHtml(kt.slice(0, 72))}${kt.length > 72 ? "…" : ""}</span>`)
                      .join("")}</div>`
                  : ""
              }
              <div class="card-footer">
                <span style="font-size:11px">Thẻ liên kết:</span>
                <div style="display:flex;flex-wrap:wrap;gap:4px">${renderNodePillsHtml(r.linked_nodes, 3)}</div>
              </div>
            </article>`
            )
            .join("")}
        </div>`
          : ""
      }
    `;

    for (const b of el.view.querySelectorAll("[data-stab]")) {
      b.addEventListener("click", () => {
        state.skillsTab = b.getAttribute("data-stab") || "all";
        renderGitHubSkillsView();
      });
    }
    for (const b of el.view.querySelectorAll("[data-scat]")) {
      b.addEventListener("click", () => {
        state.skillsCategory = b.getAttribute("data-scat") || "all";
        renderGitHubSkillsView();
      });
    }
    bindNodeCardClicks(el.view);
  }

  // ---------------- Node Detail 6-Block Reader ----------------
  async function renderNodeDetailView(nodeId) {
    const node = state.nodeMap.get(nodeId);
    if (!node) {
      el.view.innerHTML = `<div class="status-card"><h2>Không tìm thấy thẻ <code>${escapeHtml(nodeId)}</code></h2><p><a href="#overview">← Quay lại danh mục thẻ tri thức</a></p></div>`;
      return;
    }

    let mdRaw = state.markdownCache.get(nodeId);
    if (!mdRaw) {
      el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG TẢI THẺ CHI TIẾT</p><h2>${escapeHtml(node.title_vi)}</h2></div>`;
      const res = await fetch(kbUrl(node.raw_rel_path || node.path));
      mdRaw = res.ok ? await res.text() : "## Không thể tải nội dung thẻ.";
      state.markdownCache.set(nodeId, mdRaw);
    }

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
    const ghRefs = node.github_refs || [];

    // Find paired Practical Skill cards if viewing a Razavi card (or paired Razavi cards if viewing a Skill card)
    const neighborIds = Array.from(new Set([...inEdges.map((e) => e.from), ...outEdges.map((e) => e.to)]));
    const pairedSkills = neighborIds.filter((id) => state.nodeMap.has(id) && isSkillNode(state.nodeMap.get(id)));
    const c2d = node.coord_2d;
    const nodeStages = getNodeDesignStages(node);
    const cycleMap = new Map(getDesignCycleList().map((c) => [Number(c.stage), c]));

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
                ${isPmicNode(node) ? `<span class="badge badge-pmic">PMIC · Layer 8</span>` : ""}
                ${isAmsNode(node) ? `<span class="badge badge-ams">AMS · Layer 9</span>` : ""}
                <span class="badge badge-neutral">PDK-Agnostic · 180nm / 90nm / 65nm / 45nm</span>
                ${refsStr ? `<span class="badge badge-neutral">${escapeHtml(refsStr)}</span>` : ""}
                ${c2d ? `<span class="badge badge-neutral">Grid [Col ${c2d.grid_col}, Row ${c2d.grid_row}]</span>` : ""}
              </div>
            </div>
            <h1>${escapeHtml(node.title_vi)}</h1>
            <p class="en-title">${escapeHtml(node.title_en)}</p>
            <p class="reader-summary">${escapeHtml(node.summary)}</p>
            ${
              nodeStages.length > 0
                ? `<div style="margin-top:12px;display:flex;flex-wrap:wrap;gap:6px;align-items:center">
                    <span style="font-size:11px;font-weight:700;letter-spacing:0.06em;color:var(--ink-muted)">CHU TRÌNH 7 BƯỚC:</span>
                    ${nodeStages
                      .map((s) => {
                        const meta = cycleMap.get(Number(s));
                        return `<a class="node-ref-pill" href="#stage/${s}">${escapeHtml(meta ? meta.title_vi : `Stage ${s}`)}</a>`;
                      })
                      .join("")}
                  </div>`
                : ""
            }
            <div class="reader-actions">
              <button type="button" class="btn-primary" id="btn-copy-link">Sao chép liên kết #node</button>
              <button type="button" class="btn-subtle" id="btn-locate-2d">Định vị trên Đồ thị Tọa độ 2D</button>
              <button type="button" class="btn-subtle" id="btn-copy-cli">Chép lệnh Codex (kb_fetch.py)</button>
              <a class="btn-subtle" style="padding:6px 11px;border:1px solid var(--border-hairline);border-radius:5px;text-decoration:none" href="${escapeHtml(kbUrl(node.raw_rel_path || node.path))}" target="_blank" rel="noopener">Markdown gốc (.md)</a>
            </div>
          </header>

          ${
            ghRefs.length > 0
              ? `
            <section class="coord-hit-panel" style="margin-bottom:18px">
              <span class="eyebrow">NGUỒN THỰC CHIẾN GITHUB &amp; EDA REPOSITORIES THAM CHIẾU</span>
              <div class="coord-hit-grid">
                ${ghRefs
                  .map(
                    (g) => `
                  <div class="coord-hit-card">
                    <strong><a href="${escapeHtml(g.url || `https://github.com/${g.repo}`)}" target="_blank" rel="noopener">${escapeHtml(g.repo)} ↗</a></strong>
                    <div style="font-size:12.5px;color:var(--ink-secondary)">${escapeHtml(g.use || "")}</div>
                  </div>`
                  )
                  .join("")}
              </div>
            </section>`
              : pairedSkills.length > 0
              ? `
            <section class="bento-box" style="margin-bottom:18px">
              <h3>Playbook Thực chiến GitHub / Spectre Testbench Đi kèm</h3>
              <div style="display:flex;flex-wrap:wrap;gap:6px">${renderNodePillsHtml(pairedSkills, 6)}</div>
            </section>`
              : ""
          }

          ${
            diagUrl
              ? `
            <section class="schematic-panel" id="sec-schematic">
              <div class="panel-bar">
                <span>SƠ ĐỒ NGUYÊN LÝ &amp; LƯU ĐỒ VECTOR · ${escapeHtml(node.diagram.split("/").pop())}</span>
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
              <span>ĐỒ THỊ TIẾN HÓA &amp; PHỤ THUỘC LÂN CẬN (${inEdges.length} vào · ${outEdges.length} ra · Cuộn chuột Zoom, Nhấp Node chuyển thẻ)</span>
              <button type="button" class="link-btn" id="btn-open-full-graph">Mở Bản đồ Tọa độ 2D →</button>
            </div>
            <div class="graph-viewport" id="ego-graph-viewport"></div>
            <div class="graph-inspector" id="ego-graph-inspector">
              <span>Rê chuột lên mũi tên để đọc điều kiện nâng cấp (<code>when</code>) và đánh đổi (<code>cost</code>).</span>
              <div class="graph-legend">
                <span><i class="legend-dot" style="background:#1f6c9f"></i>upgrades_to</span>
                <span><i class="legend-dot" style="background:#346538"></i>fixes</span>
                <span><i class="legend-dot" style="background:#956400"></i>compensated_by</span>
                <span><i class="legend-dot" style="background:#5b3b8c"></i>requires</span>
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
                <span class="meta">Độc lập tiến trình 180nm / 90nm / 65nm / 45nm</span>
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

    mountInteractiveGraph(
      document.getElementById("ego-graph-viewport"),
      document.getElementById("ego-graph-inspector"),
      nodeId
    );

    const openMainSvg = () => openSvgModal(diagUrl, node.title_vi);
    document.getElementById("btn-zoom-main-svg")?.addEventListener("click", openMainSvg);
    document.getElementById("main-schematic-stage")?.addEventListener("click", openMainSvg);
    for (const fig of el.view.querySelectorAll("[data-zoom-svg]")) {
      fig.addEventListener("click", () => {
        openSvgModal(fig.getAttribute("data-zoom-svg"), fig.getAttribute("data-zoom-title") || node.title_vi);
      });
    }

    document.getElementById("btn-open-full-graph")?.addEventListener("click", () => {
      state.graphFocusNodeId = nodeId;
      location.hash = "#graph";
    });
    document.getElementById("btn-locate-2d")?.addEventListener("click", () => {
      state.graphFocusNodeId = nodeId;
      state.graphScope = "all";
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

  // ---------------- View 4: Symptom Diagnostics & 16 Multi-Process Checklists ----------------
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
                  ? `<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:5px">${renderNodePillsHtml(c.related_nodes, 5)}</div>`
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
    el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG TẢI HỆ THỐNG CHẨN ĐOÁN &amp; ${list.length} CHECKLIST</p><h2>Đang đồng bộ quy tắc bất biến…</h2></div>`;

    await Promise.all(
      list.map(async (item) => {
        if (!state.checklistCache.has(item.checklist_id)) {
          const r = await fetch(kbUrl(item.path));
          if (r.ok) state.checklistCache.set(item.checklist_id, await r.json());
        }
      })
    );

    const qWords = foldWords(state.query);
    const qTokens = qWords ? qWords.split(/\s+/).filter(Boolean) : [];

    // Symptom Diagnostics Matrix from router.symptom_map
    const symEntries = Object.entries(state.router.symptom_map || {}).filter(([sym, nids]) => {
      if (state.filterChapter !== null) {
        if (!nids.some((id) => (state.nodeMap.get(id)?.chapters || []).includes(state.filterChapter))) return false;
      }
      if (qTokens.length > 0) {
        const blob = foldWords(`${sym} ${nids.join(" ")}`);
        if (!qTokens.every((t) => blob.includes(t))) return false;
      }
      return true;
    });

    const loadedChecklists = list
      .map((item) => state.checklistCache.get(item.checklist_id))
      .filter(Boolean)
      .filter((cl) => {
        if (qTokens.length === 0) return true;
        const blob = foldWords(JSON.stringify(cl));
        return qTokens.every((t) => blob.includes(t));
      });

    const showSymptoms = state.diagTab === "all" || state.diagTab === "symptoms";
    const showCl = state.diagTab === "all" || state.diagTab === "checklists";
    const visibleSymptoms = state.diagTab === "symptoms" ? symEntries.slice(0, 90) : symEntries.slice(0, 18);

    el.view.innerHTML = `
      <section class="hero-header" style="margin-bottom:18px;padding-bottom:16px">
        <p class="eyebrow">SYMPTOM-TO-FIX FAULT DIAGNOSTICS &amp; ${list.length} PDK-AGNOSTIC CHECKLISTS</p>
        <h1>Chẩn đoán Triệu chứng Lỗi Mạch &amp; ${list.length} Bảng kiểm Đa Tiến trình</h1>
        <p>Tra cứu ngược từ hiện tượng hỏng mô phỏng (mất dự trữ pha, sập độ lợi, lệch không lớn, khóa chết $I=0$, nhiễu giật ngược comparator, tạp phổ spur PLL, Latch-up/ESD) tới đúng cấu trúc nâng cấp và bảng kiểm bất biến trên 180nm / 90nm / 65nm / 45nm.</p>
      </section>

      <div class="sub-tabs" role="tablist">
        <button type="button" class="sub-tab ${state.diagTab === "all" ? "is-active" : ""}" data-dtab="all">Tổng hợp Chẩn đoán &amp; Checklist</button>
        <button type="button" class="sub-tab ${state.diagTab === "symptoms" ? "is-active" : ""}" data-dtab="symptoms">Ma trận Chẩn đoán Triệu chứng (${symEntries.length})</button>
        <button type="button" class="sub-tab ${state.diagTab === "checklists" ? "is-active" : ""}" data-dtab="checklists">${list.length} Bảng kiểm Bất biến (${loadedChecklists.length})</button>
      </div>

      ${
        showSymptoms
          ? `
        <div class="section-bar">
          <h2>Chẩn đoán Nhanh Triệu chứng Lỗi → Thẻ Khắc phục</h2>
          <span class="meta">Hiển thị ${visibleSymptoms.length} / ${symEntries.length} triệu chứng</span>
        </div>
        <div class="symptom-grid">
          ${visibleSymptoms
            .map(
              ([sym, nids]) => `
            <div class="symptom-card">
              <code style="font-size:12px;color:var(--tag-red-ink);font-weight:600">${escapeHtml(sym)}</code>
              <div style="display:flex;flex-wrap:wrap;gap:5px">${renderNodePillsHtml(nids, 4)}</div>
            </div>`
            )
            .join("")}
        </div>`
          : ""
      }

      ${
        showCl
          ? `
        <div class="section-bar">
          <h2>${loadedChecklists.length} Bảng kiểm Bất biến Cấu trúc</h2>
        </div>
        ${loadedChecklists.map((cl) => renderChecklistCardHtml(cl)).join("")}`
          : ""
      }
    `;

    for (const b of el.view.querySelectorAll("[data-dtab]")) {
      b.addEventListener("click", () => {
        state.diagTab = b.getAttribute("data-dtab") || "all";
        renderChecklistsView();
      });
    }

    if (state.activeChecklistId) {
      document.getElementById(`cl-${state.activeChecklistId}`)?.scrollIntoView({ behavior: "smooth" });
    }
  }

  // ---------------- View 5: CLB 2,280 Bilingual Glossary ----------------
  async function renderGlossaryView() {
    if (!state.glossary) {
      el.view.innerHTML = `<div class="status-card"><p class="eyebrow">ĐANG NẠP KHO THUẬT NGỮ CLB</p><h2>Đang tải 2.280 mục T001–T2280…</h2></div>`;
      await ensureGlossaryLoaded();
    }

    const qRaw = state.query.trim();
    const qWords = foldWords(qRaw);
    const qTokens = qWords ? qWords.split(/\s+/).filter(Boolean) : [];
    const codeMatch = qRaw.match(/^t0*(\d+)$/i);

    const matches = [];
    for (const term of state.glossary || []) {
      if (state.filterChapter !== null && !(term.chapters || []).includes(state.filterChapter)) continue;
      if (!qWords) {
        matches.push({ term, rank: 5 });
        continue;
      }
      if (codeMatch && Number(term.id.slice(1)) === Number(codeMatch[1])) {
        matches.push({ term, rank: 0 });
        continue;
      }
      const enF = foldWords(term.en);
      const viF = foldWords(term.vi);
      const key = term.search_key || `${enF} ${viF}`;
      if (enF === qWords || viF === qWords) matches.push({ term, rank: 1 });
      else if (enF.startsWith(qWords) || viF.startsWith(qWords)) matches.push({ term, rank: 2 });
      else if (enF.includes(qWords) || viF.includes(qWords)) matches.push({ term, rank: 3 });
      else if (qTokens.every((tok) => key.includes(tok))) matches.push({ term, rank: 4 });
    }

    matches.sort((a, b) => a.rank - b.rank || Number(a.term.id.slice(1)) - Number(b.term.id.slice(1)));
    const slice = matches.slice(0, state.glossaryLimit);
    const totalTerms = (state.glossary || []).length || 2280;

    el.view.innerHTML = `
      <section class="hero-header">
        <p class="eyebrow">CHUẨN DỊCH THUẬT CLB VI MẠCH · T001 – T2280</p>
        <h1>Kho ${totalTerms} Thuật ngữ Song ngữ Anh – Việt Chuẩn hóa</h1>
        <p>Đồng bộ nguyên bản 2.134 mục đã hiệu đính của CLB Vi Mạch (Ch.01–Ch.12) cùng 146 thuật ngữ mở rộng chuẩn xác cho Ch.13–Ch.19, Quản lý Nguồn PMIC (Buck, Boost, Buck-Boost, Capless LDO, POR/UVLO/OCP) và Vi mạch Hỗn hợp AMS (CFIA, Tow-Thomas, $G_m\\text{-}C$, DAC, $\\Delta\\Sigma$, Pipeline MDAC &amp; Central Bias Bus).</p>
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
          ? `<div style="margin-top:18px;text-align:center"><button type="button" class="btn-subtle" id="btn-more-glossary">Hiện thêm 60 thuật ngữ (${matches.length - slice.length} còn lại)</button></div>`
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
      state.glossaryLimit += 60;
      renderGlossaryView();
    });
  }

  // ---------------- Lightbox Modal & Routing ----------------
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
    state.glossaryLimit = 50;
    state.eqLimit = 60;
    state.indexLimit = 80;
    if (state.mode === "detail" && q) {
      state.mode = "nodes";
    }
    renderActiveView();
  }

  function applyRouteFromHash() {
    if (!state.router) return;
    const h = decodeURIComponent(location.hash || "").replace(/^#/, "");
    state.activeChecklistId = null;

    if (h.startsWith("node/")) {
      state.activeNodeId = h.slice(5).trim();
      state.mode = "detail";
    } else if (h.startsWith("checklist/")) {
      state.activeChecklistId = h.slice(10).trim();
      state.diagTab = "checklists";
      state.mode = "checklists";
    } else if (h === "checklists") {
      state.mode = "checklists";
    } else if (h.startsWith("coords")) {
      state.mode = "coords";
      const sub = h.slice(7).trim();
      if (sub) {
        state.query = sub;
        el.search.value = sub;
        el.clearSearch.hidden = false;
      }
    } else if (h.startsWith("skills")) {
      state.mode = "skills";
    } else if (h.startsWith("domain/")) {
      state.filterDomain = h.slice(7).trim() || "all";
      state.mode = "nodes";
    } else if (h.startsWith("stage/")) {
      const s = Number(h.slice(6));
      state.filterStage = s >= 1 && s <= 7 ? s : null;
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

  function bindGlobalEvents() {
    let debounceTimer = null;
    el.search.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        setSearchQuery(el.search.value);
      }, 85);
    });

    el.search.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        const q = el.search.value.trim();
        if (state.nodeMap.has(q)) {
          location.hash = `#node/${q}`;
          return;
        }
        const { nodes } = filterNodes();
        if (nodes.length === 1) {
          location.hash = `#node/${nodes[0].id}`;
        }
      }
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
        else if (m === "coords") location.hash = "#coords";
        else if (m === "skills") location.hash = "#skills";
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
      state.filterStage = null;
      state.graphScope = "all";
      state.graphRel = "all";
      state.graphFocusNodeId = null;
      setSearchQuery("");
      if (state.mode === "detail") location.hash = "#overview";
    });

    el.sidebarToggle.addEventListener("click", () => {
      el.sidebar.classList.toggle("is-open");
    });

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
      window.addEventListener("load", () => {
        if (state.mode === "detail" && state.activeNodeId) {
          renderNodeDetailView(state.activeNodeId);
        } else if (state.mode === "coords" && state.coordsTab === "equations") {
          renderBookCoordsView();
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
