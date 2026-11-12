"use strict";
// Commander Studio: which commander the pages work on. Source-deck figures, EDHREC values and
// simulations are bound to one commander on the server; the pages always name it.

const StudioCommander = (() => {
  const KEY = "studio-commander";
  const FALLBACK = "Chulane, Teller of Tales";
  function stored() {
    try { return localStorage.getItem(KEY); } catch (error) { return null; }
  }
  const current = new URLSearchParams(location.search).get("commander") || stored() || FALLBACK;
  const shortName = (name) => name.split(",")[0];
  function choose(name) {
    try { localStorage.setItem(KEY, name); } catch (error) { /* view setting only */ }
    const address = new URL(location.href);
    address.searchParams.set("commander", name);
    location.href = address.toString();
  }
  // Fills the select with the commanders the Studio knows; the current one is always listed.
  async function fill(select) {
    let known = [];
    try {
      const response = await fetch("/api/commanders?collection=true");
      if (response.ok) known = await response.json();
    } catch (error) { /* the current commander stays selectable */ }
    if (!known.some((item) => item.name === current)) known.push({ name: current, unknown: true, in_collection: null, has_data: false, source_decks: null, saved_decks: 0 });
    known.sort((a, b) => a.name.localeCompare(b.name));
    const entry = (item) => {
      const option = document.createElement("option");
      option.value = item.name;
      option.selected = item.name === current;
      const decks = item.has_data && item.source_decks !== null ? ` · ${item.source_decks} Quelldecks` : "";
      option.textContent = (item.has_data ? shortName(item.name) : item.name) + decks + (item.unknown ? " · dem Studio unbekannt" : item.in_collection ? "" : " · nicht in der Sammlung");
      option.title = item.name;
      return option;
    };
    const group = (label, items) => {
      const box = document.createElement("optgroup");
      box.label = label;
      box.append(...items.map(entry));
      return box;
    };
    const withData = known.filter((item) => item.has_data || item.name === current);
    const others = known.filter((item) => !item.has_data && item.name !== current);
    select.replaceChildren(group("Mit Decks oder Quelldaten", withData), ...(others.length ? [group("Weitere aus der Sammlung (noch ohne Daten)", others)] : []));
    select.addEventListener("change", () => choose(select.value));
  }
  return { current, shortName, choose, fill, query: "commander=" + encodeURIComponent(current) };
})();
