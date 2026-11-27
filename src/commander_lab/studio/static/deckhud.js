/* Deck-Cockpit HUD, visual stack/curve view, drag-and-drop, and quick-add palette for BUILD. */
const StudioDeckHud = (() => {
  const MIME = "text/x-studio-card";
  const PIP_KEYS = ["W", "U", "B", "R", "G", "C"];
  const PIP_LABELS = { W: "Weiß", U: "Blau", B: "Schwarz", R: "Rot", G: "Grün", C: "Farblos" };

  let lastTotal = null;
  let didSetup = false;
  let draggingSource = "";
  let paletteEl = null;
  let paletteInput = null;
  let paletteList = null;
  let paletteMatches = [];
  let paletteIndex = 0;
  let paletteReturnFocus = null;
  let latestDeps = null;
  // Command mode (query starts with ">"): the Werkbank supplies the commands.
  let actionProvider = null;
  let paletteMode = "cards";

  function formatNum(value, decimals = 0) {
    if (typeof StudioUI !== "undefined" && typeof StudioUI.num === "function") {
      return StudioUI.num(value, decimals);
    }
    return String(value);
  }

  function kidsList(items) {
    return items.filter((item) => item !== null && item !== undefined && item !== false);
  }

  function parsePips(manaCost) {
    const counts = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
    if (!manaCost) return counts;
    const matches = String(manaCost).match(/\{([^}]+)\}/g);
    if (!matches) return counts;
    for (const token of matches) {
      const inner = token.slice(1, -1).toUpperCase();
      const parts = inner.split("/");
      for (const part of parts) {
        if (part in counts) counts[part] += 1;
      }
    }
    return counts;
  }

  function summarize(cards, qtyOf) {
    const curve = [0, 0, 0, 0, 0, 0, 0, 0];
    const types = {};
    const pips = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
    let total = 0;
    let lands = 0;
    let nonLands = 0;
    let mvSum = 0;

    for (const card of cards || []) {
      if (!card) continue;
      const q = typeof qtyOf === "function" ? Number(qtyOf(card.card_id)) || 0 : 1;
      if (q <= 0) continue;
      total += q;
      const grp = card.group || "Other";
      types[grp] = (types[grp] || 0) + q;
      if (grp === "Land") {
        lands += q;
      } else {
        nonLands += q;
        const mv = Number.isFinite(Number(card.mana_value)) ? Math.max(0, Number(card.mana_value)) : 0;
        mvSum += mv * q;
        const bucket = Math.min(7, Math.floor(mv));
        curve[bucket] += q;
      }
      const cardPips = parsePips(card.mana_cost);
      for (const k of PIP_KEYS) {
        pips[k] += cardPips[k] * q;
      }
    }

    return {
      total,
      lands,
      nonLands,
      curve,
      avgMv: nonLands > 0 ? mvSum / nonLands : null,
      types,
      pips,
    };
  }

  function rankMatches(pool, query, limit = 12, excludeIds = []) {
    const excluded = excludeIds instanceof Set ? excludeIds : new Set(excludeIds || []);
    const q = String(query || "").trim().toLowerCase();
    const candidates = (pool || []).filter((card) => card && !excluded.has(card.card_id));
    if (!q) {
      return candidates
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .slice(0, limit);
    }
    const scored = [];
    for (const card of candidates) {
      const name = String(card.name || "");
      const lower = name.toLowerCase();
      const idx = lower.indexOf(q);
      if (idx === -1) continue;
      let tier = 2;
      if (idx === 0) {
        tier = 0;
      } else {
        const prev = lower[idx - 1];
        if (prev === " " || prev === "-" || prev === "'" || prev === ",") {
          tier = 1;
        }
      }
      scored.push([tier, name, card]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1]));
    return scored.slice(0, limit).map((item) => item[2]);
  }

  function render(deps) {
    latestDeps = deps;
    const host = document.getElementById("deck-hud");
    if (!host) return;
    const { h, state, deckCards, deckTotal, cardImageUrl, GROUPS, GROUP_NAMES } = deps;
    const cards = deckCards();
    const summary = summarize(cards, deps.qty);
    const total = deckTotal();
    const fillPct = Math.min(100, Math.max(0, total));
    const ringClass = total === 100 ? "good" : total > 100 ? "bad" : "warn";

    const cmdId = state.commanderIds && state.commanderIds[0];
    const cmdCard = cmdId ? state.byId.get(cmdId) : null;
    const bannerChildren = [];
    if (cmdCard && cmdCard.has_image) {
      const img = h("img", {
        class: "hud-banner-img",
        alt: cmdCard.name,
        loading: "lazy",
        referrerpolicy: "no-referrer",
        src: cardImageUrl(cmdCard, "front"),
      });
      img.addEventListener("error", () => img.remove(), { once: true });
      bannerChildren.push(img);
    }
    bannerChildren.push(
      h("div", { class: "hud-banner-scrim" }),
      h(
        "div",
        { class: "hud-banner-meta" },
        h("span", { class: "hud-banner-role" }, "Commander"),
        h("strong", { class: "hud-banner-name" }, cmdCard ? cmdCard.name : "Kein Commander")
      )
    );
    const banner = h("div", { class: "hud-banner" }, ...bannerChildren);

    const ring = h(
      "div",
      {
        class: `hud-ring ${ringClass}`,
        role: "status",
        title: `Deckgröße: ${formatNum(total, 0)} von 100 Karten`,
      },
      h(
        "div",
        { class: "hud-ring-inner" },
        h("strong", { class: "hud-ring-num" }, formatNum(total, 0)),
        h("span", { class: "hud-ring-den" }, "/ 100")
      )
    );
    ring.style.setProperty("--fill", `${fillPct}%`);
    if (lastTotal !== null && lastTotal !== total) {
      ring.classList.add("bump");
      ring.addEventListener("animationend", () => ring.classList.remove("bump"), { once: true });
    }
    lastTotal = total;

    const maxCurve = Math.max(1, ...summary.curve);
    const curveLabels = ["0", "1", "2", "3", "4", "5", "6", "7+"];
    const curveBars = h(
      "div",
      { class: "hud-curve" },
      h(
        "div",
        { class: "hud-curve-head" },
        h("span", {}, `Manakurve · ${formatNum(summary.nonLands, 0)} Nicht-Länder`)
      ),
      h(
        "div",
        { class: "bars hud-bars" },
        summary.curve.map((val, idx) => {
          const pct = Math.max(0, Math.min(100, Math.round((100 * val) / maxCurve)));
          return h(
            "div",
            {
              class: `bh-${pct}`,
              title: `Manawert ${curveLabels[idx]}: ${formatNum(val, 0)} von ${formatNum(summary.nonLands, 0)} Nicht-Ländern`,
            },
            h("span", {}, val ? formatNum(val, 0) : "")
          );
        })
      ),
      h("div", { class: "axis hud-axis" }, curveLabels.map((lbl) => h("span", {}, lbl)))
    );

    const typeDenom = Math.max(1, summary.total || 99);
    const typeSegments = GROUPS.filter((g) => summary.types[g] > 0).map((g) => {
      const c = summary.types[g];
      const pct = Math.max(2, Math.round((1000 * c) / typeDenom) / 10);
      const seg = h("span", {
        class: `hud-type-seg grp-${g}`,
        title: `${GROUP_NAMES[g] || g}: ${formatNum(c, 0)} von ${formatNum(summary.total, 0)}`,
      });
      seg.style.setProperty("--w", `${pct}%`);
      return seg;
    });
    const typeStrip = h(
      "div",
      { class: "hud-types", title: "Typ-Verteilung (gezählt aus der Deckliste)" },
      typeSegments.length ? typeSegments : h("span", { class: "hud-type-empty" })
    );

    const pipChips = PIP_KEYS.map((k) =>
      h(
        "span",
        {
          class: `hud-pip${summary.pips[k] ? "" : " dim"}`,
          title: `${PIP_LABELS[k]}-Manasymbole in Nicht-Land-Kosten: ${formatNum(summary.pips[k], 0)}`,
        },
        h("span", { class: `ms ms-${k}` }, k),
        h("span", { class: "num" }, formatNum(summary.pips[k], 0))
      )
    );

    const chips = h(
      "div",
      { class: "hud-chips" },
      h(
        "span",
        { class: "pill", title: "Gezählte Länder in der 99-Karten-Liste" },
        `Länder ${formatNum(summary.lands, 0)} von 99`
      ),
      h(
        "span",
        { class: "pill", title: "Durchschnittlicher Manawert der Nicht-Länder" },
        `Ø Manawert ${summary.avgMv === null ? "–" : formatNum(summary.avgMv, 1)}`
      )
    );

    const topRow = h("div", { class: "hud-top" }, ring, curveBars);
    const metaRow = h(
      "div",
      { class: "hud-meta" },
      typeStrip,
      h("div", { class: "hud-pips" }, ...pipChips),
      chips,
      h("div", { class: "hud-footnote muted" }, "gezählt aus der Deckliste")
    );

    host.replaceChildren(...kidsList([banner, topRow, metaRow]));
  }

  function makeStackCard(card, deps) {
    const { h, qty, maxCopies, add, remove, openCard, cardImageUrl, mana, hoverPreview } = deps;
    const count = qty(card.card_id);
    const faceChildren = [];
    if (card.has_image) {
      const img = h("img", {
        loading: "lazy",
        referrerpolicy: "no-referrer",
        alt: card.name,
        src: cardImageUrl(card, "front"),
      });
      img.addEventListener("error", () => {
        img.replaceWith(
          h("div", { class: "stack-fallback" }, h("b", {}, card.name), mana(card.mana_cost), h("span", { class: "muted" }, card.type_line))
        );
      }, { once: true });
      faceChildren.push(img);
    } else {
      faceChildren.push(
        h("div", { class: "stack-fallback" }, h("b", {}, card.name), mana(card.mana_cost), h("span", { class: "muted" }, card.type_line))
      );
    }

    const actions = h(
      "div",
      { class: "stack-actions" },
      h("button", {
        type: "button",
        class: "small",
        title: "Kopie hinzufügen",
        "aria-label": `${card.name} hinzufügen`,
        disabled: count >= maxCopies(card),
        onclick: (e) => {
          e.stopPropagation();
          add(card);
        },
      }, "+"),
      h("button", {
        type: "button",
        class: "small",
        title: "Kopie entfernen",
        "aria-label": `${card.name} entfernen`,
        disabled: count <= 0,
        onclick: (e) => {
          e.stopPropagation();
          remove(card);
        },
      }, "−")
    );

    const el = h(
      "div",
      {
        class: "stack-card",
        tabindex: "0",
        draggable: "true",
        dataset: { cardId: card.card_id },
        "aria-label": `${card.name} (${formatNum(count, 0)}×)`,
        onclick: () => openCard(card),
        onkeydown: (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openCard(card);
          }
        },
        ondragstart: (e) => {
          draggingSource = "deck";
          if (e.dataTransfer) {
            e.dataTransfer.setData(MIME, card.card_id);
            e.dataTransfer.effectAllowed = "move";
          }
        },
        ondragend: () => {
          draggingSource = "";
        },
      },
      ...faceChildren,
      count > 1 ? h("span", { class: "stack-qty" }, `${formatNum(count, 0)}×`) : null,
      actions
    );
    hoverPreview(el, card);
    return el;
  }

  function renderStacks(body, deps, mode) {
    latestDeps = deps;
    const { h, deckCards, qty, GROUPS, GROUP_NAMES } = deps;
    const cards = deckCards();
    if (!cards.length) {
      body.append(h("p", { class: "muted" }, "Noch keine Karten. Wähle links Karten aus deiner Sammlung aus oder drücke Strg+K."));
      return;
    }

    const columns = [];
    if (mode === "curve") {
      const buckets = [
        ["0", "MV 0", []],
        ["1", "MV 1", []],
        ["2", "MV 2", []],
        ["3", "MV 3", []],
        ["4", "MV 4", []],
        ["5", "MV 5", []],
        ["6", "MV 6", []],
        ["7+", "MV 7+", []],
        ["land", "Länder", []],
      ];
      for (const card of cards) {
        if (card.group === "Land") {
          buckets[8][2].push(card);
        } else {
          const mv = Number.isFinite(Number(card.mana_value)) ? Math.max(0, Number(card.mana_value)) : 0;
          const idx = Math.min(7, Math.floor(mv));
          buckets[idx][2].push(card);
        }
      }
      for (const [key, label, items] of buckets) {
        if (!items.length) continue;
        items.sort((a, b) => a.name.localeCompare(b.name));
        columns.push({ key, label, items });
      }
    } else {
      for (const group of GROUPS) {
        const items = cards
          .filter((card) => card.group === group)
          .sort((a, b) => a.mana_value - b.mana_value || a.name.localeCompare(b.name));
        if (!items.length) continue;
        columns.push({ key: group, label: GROUP_NAMES[group] || group, items });
      }
    }

    const board = h(
      "div",
      { class: "stack-board", dataset: { mode } },
      columns.map((col) => {
        const colCount = col.items.reduce((sum, c) => sum + qty(c.card_id), 0);
        return h(
          "div",
          { class: "stack-col" },
          h(
            "div",
            { class: "stack-col-head" },
            h("span", { class: "stack-col-title" }, col.label),
            h("span", { class: "pill" }, formatNum(colCount, 0))
          ),
          h(
            "div",
            { class: "stack-col-cards" },
            col.items.map((card) => makeStackCard(card, deps))
          )
        );
      })
    );
    body.append(board);
  }

  function flashPoolTile(cardId) {
    const poolBody = document.getElementById("pool-body");
    if (!poolBody || !cardId) return;
    for (const node of poolBody.querySelectorAll(".tile")) {
      if (node.dataset && node.dataset.cardId === cardId) {
        node.classList.remove("added");
        void node.offsetWidth;
        node.classList.add("added");
        const clear = () => node.classList.remove("added");
        node.addEventListener("animationend", clear, { once: true });
        setTimeout(clear, 750);
      }
    }
  }

  function ensurePalette(deps) {
    if (paletteEl) return paletteEl;
    const { h } = deps;
    paletteInput = h("input", {
      type: "search",
      id: "quick-add-input",
      "aria-label": "Karte schnell suchen",
      placeholder: "Kartenname suchen… (↑↓ wählen, Enter hinzufügen, Umschalt+Enter entfernen, Esc schließen)",
      autocomplete: "off",
      oninput: () => {
        paletteIndex = 0;
        renderPaletteList();
      },
      onkeydown: (e) => {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          if (paletteMatches.length) {
            paletteIndex = (paletteIndex + 1) % paletteMatches.length;
            renderPaletteList();
          }
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          if (paletteMatches.length) {
            paletteIndex = (paletteIndex - 1 + paletteMatches.length) % paletteMatches.length;
            renderPaletteList();
          }
        } else if (e.key === "Enter" && paletteMode === "actions") {
          e.preventDefault();
          runAction(paletteMatches[paletteIndex]);
        } else if (e.key === "Enter") {
          e.preventDefault();
          const card = paletteMatches[paletteIndex];
          if (!card || !latestDeps) return;
          const d = latestDeps;
          const cur = d.qty(card.card_id);
          if (e.shiftKey) {
            if (cur > 0) {
              d.remove(card);
              d.toast(`${card.name} entfernt (${formatNum(d.deckTotal(), 0)} / 100)`);
              renderPaletteList();
            }
          } else if (cur < d.maxCopies(card)) {
            d.add(card);
            d.toast(`${card.name} hinzugefügt (${formatNum(d.deckTotal(), 0)} / 100)`);
            flashPoolTile(card.card_id);
            renderPaletteList();
          } else {
            d.toast("Maximale Kopienzahl erreicht");
          }
        } else if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          closePalette();
        }
      },
    });
    paletteList = h("div", {
      id: "quick-add-list",
      role: "listbox",
      "aria-label": "Suchergebnisse",
    });
    const panel = h(
      "div",
      {
        class: "quick-add-panel",
        role: "dialog",
        "aria-modal": "true",
        "aria-label": "Karte schnell hinzufügen",
        onclick: (e) => e.stopPropagation(),
      },
      h(
        "div",
        { class: "quick-add-head" },
        paletteInput,
        h("button", { type: "button", class: "ghost", onclick: closePalette }, "Esc")
      ),
      paletteList,
      h(
        "div",
        { class: "quick-add-foot muted" },
        "Enter: hinzufügen · Umschalt+Enter: entfernen · ↑↓: wählen · Esc: schließen · > am Anfang: Befehle"
      )
    );
    paletteEl = h("div", {
      id: "quick-add",
      hidden: true,
      onclick: closePalette,
    }, panel);
    document.body.append(paletteEl);
    return paletteEl;
  }

  function runAction(action) {
    if (!action || typeof action.run !== "function") return;
    closePalette();
    action.run();
  }

  function renderActionList() {
    const { h } = latestDeps;
    const q = paletteInput ? paletteInput.value : "";
    const all = actionProvider ? actionProvider() : [];
    const ranked = typeof StudioWorkbench !== "undefined" ? StudioWorkbench.rankActions(all, q) : all;
    paletteMatches = ranked.slice(0, 40);
    if (paletteIndex >= paletteMatches.length) paletteIndex = Math.max(0, paletteMatches.length - 1);
    if (!paletteMatches.length) {
      paletteList.replaceChildren(h("div", { class: "quick-add-empty muted" }, "Kein passender Befehl."));
      return;
    }
    const rows = paletteMatches.map((action, idx) => {
      const selected = idx === paletteIndex;
      return h(
        "div",
        {
          class: `quick-add-row is-action${selected ? " is-selected" : ""}`,
          role: "option",
          "aria-selected": selected ? "true" : "false",
          onclick: () => runAction(action),
        },
        h("span", { class: "quick-add-thumb action-icon", "aria-hidden": "true" }, action.icon || "›"),
        h(
          "div",
          { class: "quick-add-main" },
          h("div", { class: "quick-add-name" }, action.label),
          h("div", { class: "quick-add-sub muted" }, [action.group, action.hint].filter(Boolean).join(" · "))
        ),
        action.keys ? h("kbd", { class: "action-keys" }, action.keys) : null
      );
    });
    paletteList.replaceChildren(...kidsList(rows));
    const sel = paletteList.children[paletteIndex];
    if (sel && typeof sel.scrollIntoView === "function") {
      sel.scrollIntoView({ block: "nearest" });
    }
  }

  function renderPaletteList() {
    if (!paletteList || !latestDeps) return;
    const q = paletteInput ? paletteInput.value : "";
    paletteMode = actionProvider && q.trimStart().startsWith(">") ? "actions" : "cards";
    if (paletteEl) paletteEl.classList.toggle("is-commands", paletteMode === "actions");
    if (paletteMode === "actions") {
      renderActionList();
      return;
    }
    const { h, state, qty, maxCopies, add, cardImageUrl, mana, toast, deckTotal } = latestDeps;
    paletteMatches = rankMatches(state.pool, q, 12, state.commanderIds);
    if (paletteIndex >= paletteMatches.length) paletteIndex = Math.max(0, paletteMatches.length - 1);

    if (!paletteMatches.length) {
      paletteList.replaceChildren(h("div", { class: "quick-add-empty muted" }, "Keine passende Karte im Pool."));
      return;
    }

    const rows = paletteMatches.map((card, idx) => {
      const cur = qty(card.card_id);
      const atMax = cur >= maxCopies(card);
      const selected = idx === paletteIndex;
      const thumb = card.has_image
        ? h("img", { class: "quick-add-thumb", alt: "", loading: "lazy", referrerpolicy: "no-referrer", src: cardImageUrl(card, "front") })
        : h("span", { class: "quick-add-thumb placeholder" }, "?");
      const row = h(
        "div",
        {
          class: `quick-add-row${selected ? " is-selected" : ""}${atMax ? " at-max" : ""}`,
          role: "option",
          "aria-selected": selected ? "true" : "false",
          onmouseenter: () => {
            if (paletteIndex !== idx) {
              paletteIndex = idx;
              for (const child of paletteList.children) {
                child.classList.remove("is-selected");
                child.setAttribute("aria-selected", "false");
              }
              row.classList.add("is-selected");
              row.setAttribute("aria-selected", "true");
            }
          },
          onclick: () => {
            paletteIndex = idx;
            if (!atMax) {
              add(card);
              toast(`${card.name} hinzugefügt (${formatNum(deckTotal(), 0)} / 100)`);
              flashPoolTile(card.card_id);
              renderPaletteList();
            } else {
              toast("Maximale Kopienzahl erreicht");
            }
            if (paletteInput) paletteInput.focus();
          },
        },
        thumb,
        h(
          "div",
          { class: "quick-add-main" },
          h("div", { class: "quick-add-name" }, card.name),
          h("div", { class: "quick-add-sub muted" }, card.type_line)
        ),
        mana(card.mana_cost),
        h("span", { class: "pill" }, `im Deck ${formatNum(cur, 0)}`),
        h("span", { class: "pill" }, `frei ${formatNum(card.available, 0)}`),
        atMax ? h("span", { class: "pill warn" }, "max.") : null
      );
      return row;
    });
    paletteList.replaceChildren(...kidsList(rows));
    const sel = paletteList.children[paletteIndex];
    if (sel && typeof sel.scrollIntoView === "function") {
      sel.scrollIntoView({ block: "nearest" });
    }
  }

  function openPalette(prefix) {
    if (!latestDeps) return;
    ensurePalette(latestDeps);
    if (paletteEl.hidden) paletteReturnFocus = document.activeElement;
    paletteEl.hidden = false;
    paletteIndex = 0;
    if (paletteInput) {
      paletteInput.value = typeof prefix === "string" ? prefix : "";
      renderPaletteList();
      paletteInput.focus();
    }
  }

  function closePalette() {
    if (!paletteEl || paletteEl.hidden) return;
    paletteEl.hidden = true;
    if (paletteReturnFocus && typeof paletteReturnFocus.focus === "function") {
      paletteReturnFocus.focus();
    }
    paletteReturnFocus = null;
  }

  function setup(deps) {
    latestDeps = deps;
    if (didSetup) return;
    didSetup = true;

    const openBtn = document.getElementById("quick-add-open");
    if (openBtn) openBtn.addEventListener("click", () => openPalette());

    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (paletteEl && !paletteEl.hidden) closePalette();
        else openPalette();
        return;
      }
      if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const active = document.activeElement;
        const tag = active ? active.tagName : "";
        if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT" && !(active && active.isContentEditable)) {
          e.preventDefault();
          openPalette();
        }
      }
    });

    const deckEl = document.getElementById("deck");
    const poolEl = document.getElementById("pool");
    const hasMime = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes(MIME);

    if (deckEl) {
      deckEl.addEventListener("dragover", (e) => {
        if (!hasMime(e) || draggingSource === "deck") return;
        e.preventDefault();
        if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
        deckEl.classList.add("drop-ready");
      });
      deckEl.addEventListener("dragleave", (e) => {
        if (!deckEl.contains(e.relatedTarget)) deckEl.classList.remove("drop-ready");
      });
      deckEl.addEventListener("drop", (e) => {
        deckEl.classList.remove("drop-ready");
        if (!hasMime(e) || draggingSource === "deck" || !latestDeps) return;
        e.preventDefault();
        const cardId = e.dataTransfer.getData(MIME);
        const card = latestDeps.state.byId.get(cardId);
        if (!card) return;
        if (latestDeps.qty(cardId) < latestDeps.maxCopies(card)) {
          latestDeps.add(card);
          flashPoolTile(cardId);
          latestDeps.toast(`${card.name} hinzugefügt`);
        } else {
          latestDeps.toast("Maximale Kopienzahl erreicht");
        }
      });
    }

    if (poolEl) {
      poolEl.addEventListener("dragover", (e) => {
        if (!hasMime(e) || draggingSource !== "deck") return;
        e.preventDefault();
        if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
        poolEl.classList.add("drop-ready");
      });
      poolEl.addEventListener("dragleave", (e) => {
        if (!poolEl.contains(e.relatedTarget)) poolEl.classList.remove("drop-ready");
      });
      poolEl.addEventListener("drop", (e) => {
        poolEl.classList.remove("drop-ready");
        if (!hasMime(e) || draggingSource !== "deck" || !latestDeps) return;
        e.preventDefault();
        const cardId = e.dataTransfer.getData(MIME);
        const card = latestDeps.state.byId.get(cardId);
        if (!card) return;
        if (latestDeps.qty(cardId) > 0) {
          latestDeps.remove(card);
          latestDeps.toast(`${card.name} entfernt`);
        }
      });
    }
  }

  function setDraggingSource(src) {
    draggingSource = src || "";
  }

  function setActionProvider(fn) {
    actionProvider = typeof fn === "function" ? fn : null;
  }

  return { MIME, summarize, rankMatches, render, renderStacks, setup, setDraggingSource, setActionProvider, open: openPalette, close: closePalette };
})();

if (typeof module !== "undefined") module.exports = StudioDeckHud;
