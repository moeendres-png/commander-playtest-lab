"use strict";
// What a recorded game is called on the pages (Issue #1662): a simulated game, a game a human
// played, or a game whose origin is not known. Pure helpers: no network, no DOM, no rules. The
// value comes from the server (`cohort` and `played_seats` of /api/games, /api/games/{id} and
// /api/play/{id}, which read the game log header); nothing is derived from other fields here.
// A missing or unrecognised value is "unknown" and is never worded as a simulation.
const StudioCohort = (() => {
  const SIMULATED = "SIMULATED_RESULT";
  const PLAYED = "PLAYED_GAME";
  const UNKNOWN = "UNKNOWN";

  const seatName = (seat) => `Sitz ${seat + 1}`;

  // The 0-based seat numbers the server named, in order, each once; anything else is dropped.
  function playedSeats(record) {
    const raw = record && Array.isArray(record.played_seats) ? record.played_seats : [];
    return [...new Set(raw.filter((seat) => Number.isInteger(seat) && seat >= 0))].sort((a, b) => a - b);
  }

  // The cohort the server reported; anything but the two named cohorts is UNKNOWN.
  function cohortOf(record) {
    const value = record ? record.cohort : null;
    return value === SIMULATED || value === PLAYED ? value : UNKNOWN;
  }

  // The pill in the header of the Partie page. record: a game record of the server, or null while
  // no game is open or its record has not arrived yet (then the wording claims nothing).
  function pill(record) {
    if (!record) {
      return {
        cohort: null,
        cls: "pill",
        text: "Herkunft noch nicht bekannt",
        title: "Ob diese Partie simuliert oder von einem Menschen gespielt wurde, steht im Spielprotokoll; es ist noch nicht geladen."
      };
    }
    const cohort = cohortOf(record);
    if (cohort === PLAYED) {
      const seats = playedSeats(record);
      const where = seats.length ? `Mensch an ${seats.map(seatName).join(", ")}` : "Mensch";
      return {
        cohort,
        cls: "pill good",
        text: `gespielt (${where}), zählt in keiner Simulationszahl`,
        title: "Eine von einem Menschen gespielte Partie (PLAYED_GAME): keine Simulation, nie in einer Simulationszahl, keiner Kartenauswertung und keinem Deck-Vergleich. Sie zeigt, was in dieser Partie passiert ist."
      };
    }
    if (cohort === SIMULATED) {
      return {
        cohort,
        cls: "pill warn",
        text: "simuliert (KI auf allen Plätzen)",
        title: "Eine einzelne simulierte Partie: ein Seed, KI auf allen Plätzen. Sie zeigt, was in dieser Partie passiert ist, nicht wie stark ein Deck ist."
      };
    }
    return {
      cohort,
      cls: "pill warn",
      text: "Herkunft unbekannt, nicht als Simulation gewertet",
      title: "Das Spielprotokoll sagt nicht lesbar, ob diese Partie simuliert oder von einem Menschen gespielt wurde. Sie zählt weder als Simulation noch als gespielte Partie."
    };
  }

  // The mark in a list of single games: null for a simulated game (nothing to add), a short text
  // for a game a human played and for one whose origin is not known.
  function mark(record) {
    const cohort = cohortOf(record);
    if (cohort === SIMULATED) return null;
    if (cohort === PLAYED) {
      const seats = playedSeats(record);
      return {
        cohort,
        text: "gespielt (Mensch)",
        title: `${seats.length ? `Mensch an ${seats.map(seatName).join(", ")}. ` : ""}Von einem Menschen gespielt (PLAYED_GAME): keine Simulation, in keiner Simulationszahl.`
      };
    }
    return {
      cohort,
      text: "Herkunft unbekannt",
      title: "Das Spielprotokoll sagt nicht lesbar, ob diese Partie simuliert oder gespielt wurde; sie zählt in keiner Simulationszahl."
    };
  }

  return { SIMULATED, PLAYED, UNKNOWN, cohortOf, playedSeats, pill, mark };
})();
if (typeof module !== "undefined") module.exports = StudioCohort;
