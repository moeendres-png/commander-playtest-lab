(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.StudioCombatPreviewUX = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  "use strict";

  const COMBAT_STEPS = new Set([
    "begin_combat",
    "declare_attackers",
    "declare_blockers",
    "first_combat_damage",
    "combat_damage"
  ]);

  const COMPLEX_COMBAT_PATTERNS = [
    { re: /\bprevent\b[^.\n]{0,80}\bdamage\b/i, reason: "Schadensverhinderung im Kartentext" },
    { re: /\bverhinder[nt]?\b[^.\n]{0,80}\bschad/i, reason: "Schadensverhinderung im Kartentext" },
    { re: /\bassigns? no combat damage\b/i, reason: "Modifizierte Kampfschadens-Zuweisung" },
    { re: /\binstead\b[^.\n]{0,80}\bdamage\b/i, reason: "Ersatzeffekt für Kampfschaden" },
    { re: /\bwhenever\b[^.\n]{0,100}\b(?:attacks?|blocks?|becomes? blocked|deals? combat damage)\b/i, reason: "Kampf-Auslöser (Trigger) im Kartentext" },
    { re: /\bimmer wenn\b[^.\n]{0,100}\b(?:angreift|blockt|geblockt wird|kampfschaden)\b/i, reason: "Kampf-Auslöser (Trigger) im Kartentext" },
    { re: /\bprotection from\b|\bschutz vor\b/i, reason: "Schutz-Fähigkeit im Kartentext" },
    { re: /\b(?:infect|wither|toxic\s+\d+|poisonous\s+\d+|annihilator\s+\d+|bushido\s+\d+|flanking|exalted|dethrone|melee|myriad|prowess|afflict\s+\d+|regenerate)\b/i, reason: "Spezielle Kampf-Fähigkeit (z. B. Infekt/Verwelken/Auslöser)" },
    { re: /\b(?:damage can't be prevented|combat damage can't be prevented)\b/i, reason: "Spezielle Schadensregel im Kartentext" },
    { re: /\bassign combat damage (?:rather than|using|as though)\b/i, reason: "Abweichende Kampfschadens-Formel" }
  ];

  function asText(value) {
    return typeof value === "string" ? value.trim() : "";
  }

  function isFaceDownCard(card) {
    return Boolean(card && (card.face_down || card.name === "(verdeckt)"));
  }

  function cardRulesText(card) {
    if (!card || typeof card !== "object" || isFaceDownCard(card)) return "";
    const parts = [];
    for (const key of ["oracle_text", "rules_text", "text", "rules"]) {
      const val = card[key];
      if (typeof val === "string" && val.trim()) parts.push(val.trim());
      else if (Array.isArray(val) && val.length) parts.push(val.filter((item) => typeof item === "string").join("\n"));
    }
    if (Array.isArray(card.keywords) && card.keywords.length) {
      parts.push(card.keywords.filter((item) => typeof item === "string").join(", "));
    }
    return parts.join("\n");
  }

  function buildPilotStateCardMap(pendingDecision) {
    const map = new Map();
    const psPlayers = pendingDecision && pendingDecision.pilot_state && Array.isArray(pendingDecision.pilot_state.players)
      ? pendingDecision.pilot_state.players
      : [];
    for (const player of psPlayers) {
      if (!player || !Array.isArray(player.battlefield)) continue;
      for (const card of player.battlefield) {
        if (card && typeof card.object_id === "string" && card.object_id) {
          map.set(card.object_id, card);
        }
      }
    }
    return map;
  }

  function enrichCard(card, psCardById, facts) {
    if (!card || typeof card !== "object") return card;
    const psCard = card.object_id && psCardById ? psCardById.get(card.object_id) : null;
    if (isFaceDownCard(card) || isFaceDownCard(psCard)) {
      return Object.assign({}, card, { face_down: true });
    }
    const merged = Object.assign({}, card);
    if (psCard) {
      for (const key of ["oracle_text", "rules_text", "text", "rules", "keywords", "types", "type_line", "is_land", "face_down"]) {
        if (merged[key] === undefined && psCard[key] !== undefined) {
          merged[key] = psCard[key];
        }
      }
    }
    const name = asText(merged.name);
    const fact = name && facts && typeof facts === "object" ? facts[name] : null;
    if (fact && typeof fact === "object") {
      if (merged.oracle_text === undefined && typeof fact.oracle_text === "string") {
        merged.oracle_text = fact.oracle_text;
      }
      if (merged.type_line === undefined && typeof fact.type_line === "string") {
        merged.type_line = fact.type_line;
      }
      if (merged.keywords === undefined && Array.isArray(fact.keywords)) {
        merged.keywords = fact.keywords;
      }
    }
    return merged;
  }

  /**
   * Extrahiert Standard-Kampfschlüsselwörter ausschließlich aus offenen Feldern.
   */
  function extractKeywords(card) {
    const empty = {
      firstStrike: false,
      doubleStrike: false,
      deathtouch: false,
      trample: false,
      lifelink: false,
      indestructible: false,
      flying: false,
      menace: false,
      reach: false
    };
    if (!card || typeof card !== "object" || isFaceDownCard(card)) return empty;
    const raw = cardRulesText(card).toLowerCase();
    if (!raw) return empty;
    return {
      firstStrike: /\bfirst strike\b|\berstschlag\b/.test(raw),
      doubleStrike: /\bdouble strike\b|\bdoppelschlag\b/.test(raw),
      deathtouch: /\bdeathtouch\b|\btodesberührung\b/.test(raw),
      trample: /\btrample\b|\btrampelschaden\b/.test(raw),
      lifelink: /\blifelink\b|\blebensverknüpfung\b/.test(raw),
      indestructible: /\bindestructible\b|\bunzerstörbar\b/.test(raw),
      flying: /\bflying\b|\bfliegend\b/.test(raw),
      menace: /\bmenace\b|\bbedrohlich\b/.test(raw),
      reach: /\breach\b|\breichweite\b/.test(raw)
    };
  }

  /**
   * Prüft auf Kampffähigkeiten/Trigger/Prävention, die reine P/T-Arithmetik unsicher machen.
   */
  function detectComplexCombatText(card) {
    if (!card || typeof card !== "object") return { complex: true, reasons: ["Kreaturdaten fehlen"] };
    if (isFaceDownCard(card)) return { complex: true, reasons: ["Verdeckte Kreatur (Werte unbekannt)"] };
    const power = Number(card.power);
    const toughness = Number(card.toughness);
    if (!Number.isFinite(power) || !Number.isFinite(toughness)) {
      return { complex: true, reasons: [`Variable oder unbekannte Stärke/Widerstandskraft (${card.name || "?"})`] };
    }
    const rules = cardRulesText(card);
    if (!rules) return { complex: false, reasons: [] };
    const reasons = [];
    for (const rule of COMPLEX_COMBAT_PATTERNS) {
      if (rule.re.test(rules) && !reasons.includes(rule.reason)) {
        reasons.push(rule.reason);
      }
    }
    return { complex: reasons.length > 0, reasons };
  }

  function countOpenManaSources(player, isLandFn, psCardById, facts) {
    if (!player || typeof player !== "object") return 0;
    const battlefield = Array.isArray(player.battlefield) ? player.battlefield : [];
    let count = 0;
    for (const rawCard of battlefield) {
      const card = enrichCard(rawCard, psCardById, facts);
      if (!card || card.tapped || isFaceDownCard(card)) continue;
      const name = asText(card.name);
      const isLandCard = Boolean(
        card.is_land ||
        (Array.isArray(card.types) && card.types.some((t) => /land/i.test(String(t)))) ||
        (typeof card.type_line === "string" && /\bLand\b/i.test(card.type_line)) ||
        (typeof isLandFn === "function" && isLandFn(name, card))
      );
      if (isLandCard) {
        count += 1;
        continue;
      }
      const txt = cardRulesText(card);
      if (txt && /(?:\{T\}|tap):?\s*add\b/i.test(txt)) {
        count += 1;
      }
    }
    if (player.mana_pool && typeof player.mana_pool === "object") {
      for (const amt of Object.values(player.mana_pool)) {
        const n = Number(amt);
        if (Number.isFinite(n) && n > 0) count += n;
      }
    }
    return count;
  }

  /**
   * Bewertet, ob offene Handkarten + ungetapptes Mana eines Mitspielers einen
   * Combat-Trick oder Flash-Blocker wahrscheinlich machen.
   */
  function detectHiddenCombatTrickRisk(frame, actorSeat, options) {
    const players = Array.isArray(frame && frame.players) ? frame.players : [];
    const opts = options && typeof options === "object" ? options : {};
    const seatNameFn = typeof opts.seatName === "function" ? opts.seatName : (s) => `Sitz ${s + 1}`;
    const isLandFn = typeof opts.isLand === "function" ? opts.isLand : null;
    const psCardById = opts.psCardById || null;
    const facts = opts.facts || null;
    const focusSeats = Array.isArray(opts.defenderSeats) && opts.defenderSeats.length ? new Set(opts.defenderSeats) : null;
    const risks = [];

    for (const player of players) {
      if (!player || player.lost || player.seat === actorSeat) continue;
      if (focusSeats && !focusSeats.has(player.seat)) continue;
      const handCount = Number.isFinite(Number(player.hand_count))
        ? Number(player.hand_count)
        : (Array.isArray(player.hand) ? player.hand.length : 0);
      if (handCount <= 0) continue;
      const openMana = countOpenManaSources(player, isLandFn, psCardById, facts);
      if (openMana > 0) {
        risks.push({
          seat: player.seat,
          handCount,
          openMana,
          label: `${seatNameFn(player.seat)}: ${handCount} ${handCount === 1 ? "Handkarte" : "Handkarten"} + ${openMana} offenes Mana`
        });
      }
    }
    return {
      risk: risks.length > 0,
      seats: risks.map((r) => r.seat),
      items: risks,
      reasons: risks.map((r) => `Mögliche verdeckte Tricks/Reaktionen (${r.label})`)
    };
  }

  function resolveDefenderSeat(defenderRef, players, seatNameFn, psPlayers) {
    if (defenderRef === null || defenderRef === undefined) return null;
    if (typeof defenderRef === "number" && Number.isInteger(defenderRef)) return defenderRef;
    const raw = String(defenderRef).trim();
    if (!raw) return null;
    const candidates = Array.isArray(psPlayers) && psPlayers.length ? [...players, ...psPlayers] : players;
    for (const player of candidates) {
      if (!player) continue;
      const s = player.seat;
      if (
        (player.player_id && raw === String(player.player_id)) ||
        raw === `p${s}` ||
        raw === `Sitz ${s + 1}` ||
        raw === `Full Game Seat ${s + 1}` ||
        raw === `Seat ${s + 1}` ||
        raw === `Seat ${s}` ||
        raw === seatNameFn(s)
      ) {
        return s;
      }
    }
    return null;
  }

  function findCardAcrossBoard(frame, objectId, fallbackName, psCardById, facts) {
    const players = Array.isArray(frame && frame.players) ? frame.players : [];
    for (const player of players) {
      if (!player) continue;
      for (const card of (player.battlefield || [])) {
        if (!card) continue;
        if (objectId && card.object_id === objectId) {
          return { card: enrichCard(card, psCardById, facts), seat: player.seat };
        }
      }
    }
    if (fallbackName) {
      for (const player of players) {
        if (!player) continue;
        for (const card of (player.battlefield || [])) {
          if (card && card.name === fallbackName) {
            return { card: enrichCard(card, psCardById, facts), seat: player.seat };
          }
        }
      }
    }
    return null;
  }

  function isLethalDamage(damageDealt, hasDeathtouch, remainingToughness, isIndestructible) {
    if (isIndestructible || damageDealt <= 0) return false;
    if (hasDeathtouch) return true;
    return damageDealt >= Math.max(0, remainingToughness);
  }

  function simulateOneVsOne(attCard, blkCard) {
    const attKw = extractKeywords(attCard);
    const blkKw = extractKeywords(blkCard);
    const attP = Math.max(0, Number(attCard.power));
    const attT = Number(attCard.toughness);
    const attPrevDmg = Number(attCard.damage) || 0;
    const blkP = Math.max(0, Number(blkCard.power));
    const blkT = Number(blkCard.toughness);
    const blkPrevDmg = Number(blkCard.damage) || 0;

    let attTaken = attPrevDmg;
    let blkTaken = blkPrevDmg;
    let attDies = false;
    let blkDies = false;
    let attDealtTotal = 0;
    let blkDealtTotal = 0;
    let trampleDamage = 0;

    const attHitsFirst = attKw.firstStrike || attKw.doubleStrike;
    const attHitsSecond = !attKw.firstStrike || attKw.doubleStrike;
    const blkHitsFirst = blkKw.firstStrike || blkKw.doubleStrike;
    const blkHitsSecond = !blkKw.firstStrike || blkKw.doubleStrike;

    function assignAttackerHit() {
      if (attP <= 0) return;
      if (blkDies) {
        if (attKw.trample) {
          trampleDamage += attP;
          attDealtTotal += attP;
        }
        return;
      }
      const blkRemaining = Math.max(0, blkT - blkTaken);
      const lethalNeed = attKw.deathtouch ? 1 : blkRemaining;
      const toBlocker = attKw.trample ? Math.min(attP, lethalNeed) : attP;
      const overflow = attKw.trample ? Math.max(0, attP - lethalNeed) : 0;
      blkTaken += toBlocker;
      attDealtTotal += toBlocker + overflow;
      trampleDamage += overflow;
    }

    function assignBlockerHit() {
      if (blkP <= 0) return;
      attTaken += blkP;
      blkDealtTotal += blkP;
    }

    function runDamageStep(attStrikes, blkStrikes) {
      const attActs = attStrikes && !attDies;
      const blkActs = blkStrikes && !blkDies;
      if (attActs) assignAttackerHit();
      if (blkActs) assignBlockerHit();
      // State-based actions apply after all damage in the step is dealt simultaneously.
      if (isLethalDamage(blkTaken, attKw.deathtouch, blkT, blkKw.indestructible)) {
        blkDies = true;
      }
      if (isLethalDamage(attTaken, blkKw.deathtouch, attT, attKw.indestructible)) {
        attDies = true;
      }
    }

    if (attHitsFirst || blkHitsFirst) {
      runDamageStep(attHitsFirst, blkHitsFirst);
    }
    if (attHitsSecond || blkHitsSecond) {
      runDamageStep(attHitsSecond, blkHitsSecond);
    }

    return {
      attackerDies: attDies,
      blockerDies: blkDies,
      trampleDamage,
      attackerLifelinkGain: attKw.lifelink ? attDealtTotal : 0,
      blockerLifelinkGain: blkKw.lifelink ? blkDealtTotal : 0,
      damageToBlocker: Math.max(0, blkTaken - blkPrevDmg),
      damageToAttacker: Math.max(0, attTaken - attPrevDmg),
      attKw,
      blkKw
    };
  }

  function makeCreatureOutcome(card, dies, uncertain, dmgDealt, note) {
    if (uncertain) {
      return { outcome: "uncertain", icon: "?", text: note || "Ungewiss" };
    }
    if (dies) {
      return { outcome: "dies", icon: "💀", text: note || "Stirbt" };
    }
    return { outcome: "survives", icon: "🛡️", text: note || (dmgDealt > 0 ? `Überlebt (${dmgDealt} Schaden)` : "Überlebt") };
  }

  function addHoverTargetIfNeeded(attacks, blocks, pending, hoveredTarget, drag, frame, players, seatNameFn, psCardById, facts) {
    if (!pending) return;
    const cls = pending.decision_class;
    if (cls === "declare_attacker" && drag && drag.kind === "attacker" && hoveredTarget && hoveredTarget.type === "seat") {
      const exists = attacks.some((a) => a.attackerId && a.attackerId === drag.objectId);
      if (!exists) {
        const found = findCardAcrossBoard(frame, drag.objectId, drag.name, psCardById, facts);
        attacks.push({
          attackerId: drag.objectId,
          attackerName: (found && found.card.name) || drag.name || "Angreifer",
          attackerSeat: found ? found.seat : pending.seat,
          defenderSeat: hoveredTarget.seat,
          defenderLabel: seatNameFn(hoveredTarget.seat),
          staged: true,
          hovered: true
        });
      }
    } else if (cls === "declare_blocker" && drag && drag.kind === "blocker" && hoveredTarget && hoveredTarget.type === "object") {
      const attackerFound = findCardAcrossBoard(frame, hoveredTarget.id, null, psCardById, facts);
      const blockerFound = findCardAcrossBoard(frame, drag.objectId, drag.name, psCardById, facts);
      if (attackerFound && blockerFound) {
        const dup = blocks.some((b) => b.blockerId === drag.objectId && b.attackerId === hoveredTarget.id);
        if (!dup) {
          blocks.push({
            attackerId: hoveredTarget.id,
            attackerName: attackerFound.card.name,
            blockerId: drag.objectId,
            blockerName: blockerFound.card.name,
            blockerSeat: blockerFound.seat,
            staged: true,
            hovered: true
          });
        }
      }
    }
  }

  /**
   * Berechnet eine schreibgeschützte Kampf-Vorschau ausschließlich aus offenen
   * Brettinformationen und der noch nicht abgeschickten Auswahl des Menschen.
   */
  function evaluateCombatPreview(frame, pendingDecision, options) {
    const empty = {
      visible: false,
      certainty: "certain",
      uncertaintyReasons: [],
      trickRisk: { risk: false, seats: [], items: [], reasons: [] },
      clashes: [],
      creatureOutcomes: {},
      seatEffects: {}
    };
    if (!frame || typeof frame !== "object") return empty;
    const players = Array.isArray(frame.players) ? frame.players : [];
    const opts = options && typeof options === "object" ? options : {};
    const seatNameFn = typeof opts.seatName === "function" ? opts.seatName : (s) => `Sitz ${s + 1}`;
    const selectedOptions = Array.isArray(opts.selectedOptions) ? opts.selectedOptions : [];
    const ownCombat = opts.ownCombat && Array.isArray(opts.ownCombat.entries) ? opts.ownCombat : null;
    const psPlayers = pendingDecision && pendingDecision.pilot_state && Array.isArray(pendingDecision.pilot_state.players)
      ? pendingDecision.pilot_state.players
      : [];
    const psCardById = buildPilotStateCardMap(pendingDecision);
    const facts = opts.facts && typeof opts.facts === "object" ? opts.facts : null;
    const step = asText(frame.step);
    const inCombatStep = COMBAT_STEPS.has(step) || (pendingDecision && (pendingDecision.decision_class === "declare_attacker" || pendingDecision.decision_class === "declare_blocker"));
    const psCombat = pendingDecision && pendingDecision.pilot_state && pendingDecision.pilot_state.combat ? pendingDecision.pilot_state.combat : null;
    const combatSrc = (frame.combat && ((frame.combat.attacks || []).length || (frame.combat.blocks || []).length)) ? frame.combat : psCombat;
    const committedAttacks = combatSrc && Array.isArray(combatSrc.attacks) ? combatSrc.attacks : [];
    const committedBlocks = combatSrc && Array.isArray(combatSrc.blocks) ? combatSrc.blocks : [];

    if (!inCombatStep && !committedAttacks.length) return empty;

    const attacks = [];
    const blocks = [];

    for (const atk of committedAttacks) {
      if (!atk) continue;
      const found = findCardAcrossBoard(frame, atk.attacker_id || null, atk.attacker, psCardById, facts);
      attacks.push({
        attackerId: atk.attacker_id || (found && found.card.object_id) || null,
        attackerName: atk.attacker || (found && found.card.name) || "Angreifer",
        attackerSeat: found ? found.seat : (Number.isInteger(frame.active_seat) ? frame.active_seat : frame.seat),
        defenderSeat: resolveDefenderSeat(atk.target, players, seatNameFn, psPlayers),
        defenderLabel: atk.target ? String(atk.target) : "Unbekannt",
        staged: false
      });
    }

    for (const blk of committedBlocks) {
      if (!blk) continue;
      const blkFound = findCardAcrossBoard(frame, blk.blocker_id || null, blk.blocker, psCardById, facts);
      const atkFound = findCardAcrossBoard(frame, blk.attacker_id || null, blk.attacker, psCardById, facts);
      blocks.push({
        attackerId: blk.attacker_id || (atkFound && atkFound.card.object_id) || null,
        attackerName: blk.attacker || (atkFound && atkFound.card.name) || "Angreifer",
        blockerId: blk.blocker_id || (blkFound && blkFound.card.object_id) || null,
        blockerName: blk.blocker || (blkFound && blkFound.card.name) || "Blocker",
        blockerSeat: blkFound ? blkFound.seat : null,
        staged: false
      });
    }

    if (ownCombat && inCombatStep) {
      for (const entry of ownCombat.entries) {
        if (!entry) continue;
        if (entry.kind === "attacker" && entry.objectId) {
          const dup = attacks.some((a) => a.attackerId === entry.objectId);
          if (!dup) {
            const found = findCardAcrossBoard(frame, entry.objectId, null, psCardById, facts);
            const defSeat = resolveDefenderSeat(entry.defenderId, players, seatNameFn, psPlayers);
            attacks.push({
              attackerId: entry.objectId,
              attackerName: (found && found.card.name) || entry.text || "Angreifer",
              attackerSeat: found ? found.seat : frame.active_seat,
              defenderSeat: defSeat,
              defenderLabel: defSeat !== null ? seatNameFn(defSeat) : (entry.defenderId || "Verteidiger"),
              staged: false
            });
          }
        } else if (entry.kind === "blocker" && entry.attackerId && entry.blockerId) {
          const dup = blocks.some((b) => b.blockerId === entry.blockerId && b.attackerId === entry.attackerId);
          if (!dup) {
            const blkFound = findCardAcrossBoard(frame, entry.blockerId, null, psCardById, facts);
            const atkFound = findCardAcrossBoard(frame, entry.attackerId, null, psCardById, facts);
            blocks.push({
              attackerId: entry.attackerId,
              attackerName: (atkFound && atkFound.card.name) || "Angreifer",
              blockerId: entry.blockerId,
              blockerName: (blkFound && blkFound.card.name) || entry.text || "Blocker",
              blockerSeat: blkFound ? blkFound.seat : null,
              staged: false
            });
          }
        }
      }
    }

    if (pendingDecision && Array.isArray(pendingDecision.legal_options)) {
      const byId = new Map(pendingDecision.legal_options.map((o) => [o.option_id, o]));
      if (pendingDecision.decision_class === "declare_attacker") {
        for (const optId of selectedOptions) {
          const opt = byId.get(optId);
          if (!opt || opt.option_type === "hold_attacker") continue;
          const meta = opt.metadata && typeof opt.metadata === "object" ? opt.metadata : {};
          const objId = meta.object_id || null;
          if (objId && attacks.some((a) => a.attackerId === objId)) continue;
          const found = findCardAcrossBoard(frame, objId, meta.name, psCardById, facts);
          const defSeat = resolveDefenderSeat(meta.defender_id, players, seatNameFn, psPlayers);
          attacks.push({
            attackerId: objId,
            attackerName: (found && found.card.name) || meta.name || opt.label || "Angreifer",
            attackerSeat: found ? found.seat : pendingDecision.seat,
            defenderSeat: defSeat,
            defenderLabel: defSeat !== null ? seatNameFn(defSeat) : (meta.defender_id ? String(meta.defender_id) : "Verteidiger"),
            staged: true
          });
        }
      } else if (pendingDecision.decision_class === "declare_blocker") {
        const blkMeta = pendingDecision.metadata && typeof pendingDecision.metadata === "object" ? pendingDecision.metadata : {};
        for (const optId of selectedOptions) {
          const opt = byId.get(optId);
          if (!opt) continue;
          const meta = opt.metadata && typeof opt.metadata === "object" ? opt.metadata : {};
          const attackerId = meta.attacker_id || opt.option_id || null;
          const blockerId = meta.blocker_id || blkMeta.blocker_id || null;
          const atkFound = findCardAcrossBoard(frame, attackerId, null, psCardById, facts);
          const blkFound = findCardAcrossBoard(frame, blockerId, null, psCardById, facts);
          const dup = blocks.some((b) =>
            (blockerId && b.blockerId === blockerId && attackerId && b.attackerId === attackerId) ||
            (!blockerId && b.attackerName === (atkFound && atkFound.card.name))
          );
          if (!dup) {
            blocks.push({
              attackerId,
              attackerName: (atkFound && atkFound.card.name) || opt.label || "Angreifer",
              blockerId,
              blockerName: (blkFound && blkFound.card.name) || "Gewählter Blocker",
              blockerSeat: blkFound ? blkFound.seat : pendingDecision.seat,
              staged: true
            });
          }
        }
      }
    }

    addHoverTargetIfNeeded(attacks, blocks, pendingDecision, opts.hoveredTarget, opts.drag, frame, players, seatNameFn, psCardById, facts);

    if (!attacks.length) return empty;

    const actorSeat = Number.isInteger(attacks[0].attackerSeat) ? attacks[0].attackerSeat : (Number.isInteger(frame.active_seat) ? frame.active_seat : frame.seat);
    const defenderSeats = [...new Set(attacks.map((a) => a.defenderSeat).filter((s) => Number.isInteger(s)))];
    const trickRisk = detectHiddenCombatTrickRisk(frame, actorSeat, {
      seatName: seatNameFn,
      isLand: opts.isLand,
      defenderSeats: defenderSeats.length ? defenderSeats : null,
      psCardById,
      facts
    });

    const clashes = [];
    const creatureOutcomes = {};
    const seatEffects = {};
    const globalReasons = new Set(trickRisk.reasons);

    function ensureSeatEffect(seat) {
      if (!Number.isInteger(seat)) return null;
      if (!seatEffects[seat]) {
        const pl = players.find((p) => p && p.seat === seat);
        seatEffects[seat] = {
          seat,
          label: seatNameFn(seat),
          currentLife: pl && typeof pl.life === "number" ? pl.life : null,
          delta: 0,
          incomingDamage: 0,
          lifelinkGain: 0,
          newLife: pl && typeof pl.life === "number" ? pl.life : null,
          lethal: false,
          certain: true
        };
      }
      return seatEffects[seat];
    }

    for (const atk of attacks) {
      const atkFound = findCardAcrossBoard(frame, atk.attackerId, atk.attackerName, psCardById, facts);
      const atkCard = atkFound ? atkFound.card : null;
      const matchedBlocks = blocks.filter((b) =>
        (atk.attackerId && b.attackerId && b.attackerId === atk.attackerId) ||
        (!b.attackerId && b.attackerName === atk.attackerName)
      );

      const atkCheck = detectComplexCombatText(atkCard);
      const blkChecks = matchedBlocks.map((b) => {
        const blkFound = findCardAcrossBoard(frame, b.blockerId, b.blockerName, psCardById, facts);
        return {
          block: b,
          card: blkFound ? blkFound.card : null,
          check: detectComplexCombatText(blkFound ? blkFound.card : null)
        };
      });

      const clashReasons = [];
      if (atkCheck.complex) atkCheck.reasons.forEach((r) => clashReasons.push(r));
      for (const bc of blkChecks) {
        if (bc.check.complex) bc.check.reasons.forEach((r) => clashReasons.push(r));
      }
      if (blkChecks.length > 1) {
        clashReasons.push(`Mehrfachblock (${blkChecks.length} Blocker): Schadensaufteilung offen`);
      }
      if (trickRisk.risk) {
        trickRisk.reasons.forEach((r) => clashReasons.push(r));
      }
      const uniqueClashReasons = [...new Set(clashReasons)];
      uniqueClashReasons.forEach((r) => globalReasons.add(r));

      const hasKnownStats = !atkCheck.complex && blkChecks.every((bc) => !bc.check.complex);
      const isDeterministicPair = hasKnownStats && blkChecks.length <= 1;
      const isCertain = isDeterministicPair && !trickRisk.risk;

      let clashData;
      if (!isDeterministicPair) {
        const approxDmg = !atkCheck.complex && blkChecks.length === 0 ? Math.max(0, Number(atkCard.power)) : null;
        if (atk.attackerId) {
          creatureOutcomes[atk.attackerId] = makeCreatureOutcome(atkCard, false, true, 0, "Ungewiss");
        }
        for (const bc of blkChecks) {
          if (bc.block.blockerId) {
            creatureOutcomes[bc.block.blockerId] = makeCreatureOutcome(bc.card, false, true, 0, "Ungewiss");
          }
        }
        if (Number.isInteger(atk.defenderSeat)) {
          const eff = ensureSeatEffect(atk.defenderSeat);
          if (eff) eff.certain = false;
        }
        if (Number.isInteger(atk.attackerSeat)) {
          const eff = ensureSeatEffect(atk.attackerSeat);
          if (eff) eff.certain = false;
        }
        clashData = {
          attackerId: atk.attackerId,
          attackerName: atk.attackerName,
          attackerPt: atkCard && Number.isFinite(Number(atkCard.power)) ? `${atkCard.power}/${atkCard.toughness}` : "?/?",
          attackerSeat: atk.attackerSeat,
          defenderSeat: atk.defenderSeat,
          defenderLabel: atk.defenderLabel,
          blockers: blkChecks.map((bc) => ({
            blockerId: bc.block.blockerId,
            blockerName: bc.block.blockerName,
            pt: bc.card && Number.isFinite(Number(bc.card.power)) ? `${bc.card.power}/${bc.card.toughness}` : "?/?",
            dies: null,
            outcome: makeCreatureOutcome(bc.card, false, true, 0, "Ungewiss")
          })),
          unblocked: blkChecks.length === 0,
          staged: Boolean(atk.staged || blkChecks.some((bc) => bc.block.staged)),
          certainty: "uncertain",
          reasons: uniqueClashReasons,
          playerDamage: approxDmg,
          attackerOutcome: makeCreatureOutcome(atkCard, false, true, 0, "Ungewiss"),
          summaryText: blkChecks.length > 1
            ? `${atk.attackerName} vs. ${blkChecks.length} Blocker → ungewiss (Mehrfachblock)`
            : `${atk.attackerName} → ${atk.defenderLabel} (ungewiss)`
        };
      } else if (blkChecks.length === 0) {
        const kw = extractKeywords(atkCard);
        const hits = kw.doubleStrike ? 2 : 1;
        const dmg = Math.max(0, Number(atkCard.power)) * hits;
        const lifelinkGain = kw.lifelink ? dmg : 0;

        if (Number.isInteger(atk.defenderSeat)) {
          const defEff = ensureSeatEffect(atk.defenderSeat);
          if (defEff) {
            defEff.incomingDamage += dmg;
            defEff.delta -= dmg;
            if (!isCertain) defEff.certain = false;
          }
        }
        if (lifelinkGain > 0 && Number.isInteger(atk.attackerSeat)) {
          const atkEff = ensureSeatEffect(atk.attackerSeat);
          if (atkEff) {
            atkEff.lifelinkGain += lifelinkGain;
            atkEff.delta += lifelinkGain;
            if (!isCertain) atkEff.certain = false;
          }
        }
        const atkOut = makeCreatureOutcome(atkCard, false, !isCertain, 0, isCertain ? "Überlebt" : "Überlebt? (offene Tricks möglich)");
        if (atk.attackerId) creatureOutcomes[atk.attackerId] = atkOut;
        const dmgPrefix = isCertain ? "" : "≈ ";
        clashData = {
          attackerId: atk.attackerId,
          attackerName: atk.attackerName,
          attackerPt: `${atkCard.power}/${atkCard.toughness}`,
          attackerSeat: atk.attackerSeat,
          defenderSeat: atk.defenderSeat,
          defenderLabel: atk.defenderLabel,
          blockers: [],
          unblocked: true,
          staged: Boolean(atk.staged),
          certainty: isCertain ? "certain" : "uncertain",
          reasons: uniqueClashReasons,
          playerDamage: dmg,
          attackerOutcome: atkOut,
          summaryText: `${atk.attackerName} (${atkCard.power}/${atkCard.toughness}) ungeblockt → ${dmgPrefix}${dmg} Schaden an ${atk.defenderLabel}`
        };
      } else {
        const blk = blkChecks[0];
        const sim = simulateOneVsOne(atkCard, blk.card);
        if (sim.trampleDamage > 0 && Number.isInteger(atk.defenderSeat)) {
          const defEff = ensureSeatEffect(atk.defenderSeat);
          if (defEff) {
            defEff.incomingDamage += sim.trampleDamage;
            defEff.delta -= sim.trampleDamage;
            if (!isCertain) defEff.certain = false;
          }
        }
        if (sim.attackerLifelinkGain > 0 && Number.isInteger(atk.attackerSeat)) {
          const atkEff = ensureSeatEffect(atk.attackerSeat);
          if (atkEff) {
            atkEff.lifelinkGain += sim.attackerLifelinkGain;
            atkEff.delta += sim.attackerLifelinkGain;
            if (!isCertain) atkEff.certain = false;
          }
        }
        if (sim.blockerLifelinkGain > 0 && Number.isInteger(blk.block.blockerSeat)) {
          const blkEff = ensureSeatEffect(blk.block.blockerSeat);
          if (blkEff) {
            blkEff.lifelinkGain += sim.blockerLifelinkGain;
            blkEff.delta += sim.blockerLifelinkGain;
            if (!isCertain) blkEff.certain = false;
          }
        }
        const bothDie = sim.attackerDies && sim.blockerDies;
        const atkNote = sim.attackerDies
          ? (bothDie ? "Stirbt (Tausch)" : "Stirbt")
          : (sim.damageToAttacker > 0 ? `Überlebt (${sim.damageToAttacker} Schaden)` : "Überlebt");
        const blkNote = sim.blockerDies
          ? (bothDie ? "Stirbt (Tausch)" : "Stirbt")
          : (sim.damageToBlocker > 0 ? `Überlebt (${sim.damageToBlocker} Schaden)` : "Überlebt");
        const atkOut = makeCreatureOutcome(
          atkCard,
          sim.attackerDies,
          !isCertain,
          sim.damageToAttacker,
          isCertain ? atkNote : `${atkNote}? (offene Tricks möglich)`
        );
        const blkOut = makeCreatureOutcome(
          blk.card,
          sim.blockerDies,
          !isCertain,
          sim.damageToBlocker,
          isCertain ? blkNote : `${blkNote}? (offene Tricks möglich)`
        );
        if (atk.attackerId) creatureOutcomes[atk.attackerId] = atkOut;
        if (blk.block.blockerId) creatureOutcomes[blk.block.blockerId] = blkOut;

        const outcomeText = bothDie
          ? "Tausch (beide sterben)"
          : (sim.blockerDies && !sim.attackerDies
            ? `${blk.block.blockerName} stirbt, ${atk.attackerName} überlebt`
            : (sim.attackerDies && !sim.blockerDies
              ? `${atk.attackerName} stirbt, ${blk.block.blockerName} überlebt`
              : "Beide überleben"));
        const trampleTxt = sim.trampleDamage > 0 ? ` + ${sim.trampleDamage} Trampel an ${atk.defenderLabel}` : "";
        clashData = {
          attackerId: atk.attackerId,
          attackerName: atk.attackerName,
          attackerPt: `${atkCard.power}/${atkCard.toughness}`,
          attackerSeat: atk.attackerSeat,
          defenderSeat: atk.defenderSeat,
          defenderLabel: atk.defenderLabel,
          blockers: [{
            blockerId: blk.block.blockerId,
            blockerName: blk.block.blockerName,
            pt: `${blk.card.power}/${blk.card.toughness}`,
            dies: sim.blockerDies,
            outcome: blkOut
          }],
          unblocked: false,
          staged: Boolean(atk.staged || blk.block.staged),
          certainty: isCertain ? "certain" : "uncertain",
          reasons: uniqueClashReasons,
          playerDamage: sim.trampleDamage,
          attackerOutcome: atkOut,
          summaryText: `${atk.attackerName} (${atkCard.power}/${atkCard.toughness}) vs. ${blk.block.blockerName} (${blk.card.power}/${blk.card.toughness}) → ${outcomeText}${trampleTxt}`
        };
      }
      clashes.push(clashData);
    }

    for (const eff of Object.values(seatEffects)) {
      if (eff.currentLife !== null) {
        eff.newLife = eff.currentLife + eff.delta;
        eff.lethal = eff.newLife <= 0;
      }
    }

    const overallCertainty = clashes.some((c) => c.certainty === "uncertain") || trickRisk.risk ? "uncertain" : "certain";
    return {
      visible: clashes.length > 0,
      certainty: overallCertainty,
      uncertaintyReasons: [...globalReasons],
      trickRisk,
      clashes,
      creatureOutcomes,
      seatEffects
    };
  }

  return {
    COMBAT_STEPS,
    extractKeywords,
    detectComplexCombatText,
    detectHiddenCombatTrickRisk,
    evaluateCombatPreview,
    simulateOneVsOne
  };
});
