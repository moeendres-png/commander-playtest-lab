"use strict";
// Comparison groups that name the same set of source decks are shown once. The server says
// which ones (`same_as` on a row of /api/cohorts, read on the decks of the commander); this
// file only hides the later names and puts them in the label of the first. A pure helper, so
// it can be tested alone. Nothing here changes a count.

const StudioCohorts = (() => {
  // later group -> the group it repeats
  function aliasMap(shapes) {
    const map = new Map();
    for (const row of shapes || []) for (const alias of row.same_as || []) map.set(alias, row.cohort);
    return map;
  }
  // the entries ([key, size]) without the groups that repeat an earlier one
  function visible(entries, shapes) {
    const alias = aliasMap(shapes);
    return entries.filter(([key]) => !alias.has(key));
  }
  const joined = (names) => names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} und ${names[names.length - 1]}`;
  // "alle Quelldecks (zugleich Community und Commander Chulane)"; a group of its own keeps its name
  function label(key, shapes, nameOf) {
    const row = (shapes || []).find((item) => item.cohort === key);
    const same = row && row.same_as ? row.same_as : [];
    return same.length ? `${nameOf(key)} (zugleich ${joined(same.map(nameOf))})` : nameOf(key);
  }
  return { aliasMap, visible, label };
})();
if (typeof module !== "undefined") module.exports = StudioCohorts;
