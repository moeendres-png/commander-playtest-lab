#!/usr/bin/env python3
"""Immutable, evidence-bound C079 + 20 new EDHREC captures in separate SQLite.

Manual, review-only import. Does NOT replace Studio observations or backfill C079 UTC.
Stdlib-only so it runs without credentials, third-party APIs or installed packages.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

CAPTURE_PREFIX = 'https://json.edhrec.com/pages/commanders/chulane-teller-of-tales'
URL_PATTERN = re.compile(re.escape(CAPTURE_PREFIX) + r'(?:/[a-z0-9-]+)?\.json\Z')
EVENT_PATTERN = re.compile(r'EDHREC_NEW_[0-9a-f]{24}\Z')
PINNED_C079_SHA256 = 'd2a24a01b9b32378ae0fde2c0e81fb61108a659a789dc8702ff0b05cc7ff2feb'
FULL = {'events': 20, 'cards': 4945, 'historical': 1379, 'missing_utc': 1304,
        'exact_utc': 75, 'matched': 1298, 'not_listed': 6}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS edhrec_capture_event (
      event_id TEXT PRIMARY KEY, url TEXT NOT NULL, request_start_utc TEXT NOT NULL,
      response_complete_utc TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
      http_status INTEGER NOT NULL CHECK(http_status=200),
      raw_json BLOB NOT NULL, response_http_date TEXT,
      source_kind TEXT NOT NULL CHECK(source_kind='NEW_HTTP_CAPTURED'),
      UNIQUE(url, response_complete_utc)
    )""",
    """CREATE TABLE IF NOT EXISTS edhrec_capture_card (
      event_id TEXT NOT NULL REFERENCES edhrec_capture_event(event_id),
      card_name_key TEXT NOT NULL, card_name TEXT NOT NULL, edhrec_cardview_id TEXT,
      original_headers TEXT NOT NULL, numerator INTEGER NOT NULL,
      denominator INTEGER NOT NULL, inclusion_pct_derived REAL,
      lift_as_source REAL, oracle_id TEXT,
      value_kind TEXT NOT NULL CHECK(value_kind='ORIGINAL_COUNTS_AND_DERIVED_INCLUSION'),
      PRIMARY KEY(event_id, card_name_key)
    )""",
    """CREATE TABLE IF NOT EXISTS edhrec_c079_historical_audit (
      source_csv_line INTEGER PRIMARY KEY, card_id TEXT NOT NULL, oracle_id TEXT,
      card_name TEXT NOT NULL, theme TEXT NOT NULL, url TEXT NOT NULL,
      numerator INTEGER, denominator INTEGER, inclusion_pct_as_source REAL,
      lift_as_source REAL, snapshot_utc TEXT, exact_utc_proven INTEGER NOT NULL,
      html_metric_proof TEXT NOT NULL, capture_evidence TEXT NOT NULL,
      provenance_kind TEXT NOT NULL CHECK(provenance_kind='LEGACY_C079'),
      CHECK((exact_utc_proven=1 AND snapshot_utc IS NOT NULL) OR
            (exact_utc_proven=0 AND snapshot_utc IS NULL))
    )""",
    """CREATE TABLE IF NOT EXISTS edhrec_c079_fresh_link (
      source_csv_line INTEGER PRIMARY KEY REFERENCES edhrec_c079_historical_audit(source_csv_line),
      event_id TEXT NOT NULL REFERENCES edhrec_capture_event(event_id),
      card_name_key TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
        ('NEW_CAPTURE_MATCHED_EXACT_NAME','NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN')),
      CHECK(status != 'NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN' OR event_id IS NOT NULL)
    )""",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def utc(value: str) -> datetime:
    expect(isinstance(value, str) and value.endswith('Z'), 'UTC must end with Z')
    try:
        value_dt = datetime.fromisoformat(value[:-1] + '+00:00')
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid capture UTC') from exc
    expect(value_dt.tzinfo is not None and value_dt.utcoffset() == timedelta(0), 'UTC offset not zero')
    return value_dt


def safe_member(name: str) -> str:
    expect(bool(name) and not name.startswith('/') and '\\' not in name and '..' not in Path(name).parts,
           'Invalid ZIP member name')
    return name


def csv_rows(data: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    rows = list(reader)
    expect(bool(rows) and all(None not in row for row in rows), 'Empty or malformed CSV')
    return rows


def dec(value: str | None) -> Decimal | None:
    if value is None or str(value).strip() == '':
        return None
    try:
        d = Decimal(str(value).strip())
        expect(d.is_finite(), 'Non-finite numeric value')
        return d
    except InvalidOperation as exc:
        raise ValueError(f'Invalid decimal {value!r}') from exc


def db_nullable(value: str | None) -> float | None:
    d = dec(value)
    return float(d) if d is not None else None


def name_key(name: str) -> str:
    expect(bool(name and name.strip()), 'Empty card name')
    return name.strip().casefold()


def load_captures(source: Path | io.BytesIO) -> tuple[list[dict], list[tuple]]:
    """Validate ALL capture sources before any database writes."""
    if isinstance(source, Path) and source.is_dir():
        base = source.resolve()

        def read(n):
            candidate = (base / safe_member(n)).resolve()
            expect(candidate.is_relative_to(base), 'Capture manifest escapes input directory')
            return candidate.read_bytes()
    else:
        archive = zipfile.ZipFile(source)
        expect(archive.testzip() is None, 'Corrupt ZIP')
        entries = set(archive.namelist())
        expect(all(safe_member(n) for n in entries), 'Unsafe archive path')

        def read(n):
            expect(n in entries, f'Missing evidence {n}')
            return archive.read(safe_member(n))

    manifest = json.loads(read('manifest.json'))
    records = manifest.get('records')
    expect(isinstance(records, list) and bool(records), 'Capture manifest has no records')
    events: list[dict] = []
    cards: list[tuple] = []
    seen: set[str] = set()
    seen_url: set[str] = set()
    for record in records:
        event_id, url = record['event_id'], record['url']
        expect(bool(EVENT_PATTERN.fullmatch(event_id)) and bool(URL_PATTERN.fullmatch(url)),
               'Event ID or public API URL invalid')
        expect(event_id not in seen and url not in seen_url, 'Duplicate event or URL')
        seen.add(event_id)
        seen_url.add(url)
        raw = read(record['raw'])
        metadata = json.loads(read(record['metadata']))
        digest = sha(raw)
        expect(len(raw) <= 4_000_000, 'Raw response exceeds documented capture limit')
        expect(digest == record['sha256'] == metadata['raw_response_sha256'] and
               len(raw) == metadata['raw_size_bytes'], 'Raw SHA/length mismatch')
        expect(metadata['url'] == url and metadata['event_id'] == event_id and
               record['observed_utc'] == metadata['response_complete_utc'],
               'Record and source metadata disagree')
        expect(metadata['http_status'] == 200 and metadata['automatic_import'] is False and
               metadata['historical_C079_timestamp_backfilled'] is False,
               'Non-HTTP200 or unsafe provenance flags')
        began, ended = utc(metadata['request_start_utc']), utc(metadata['response_complete_utc'])
        expect(began <= ended, 'HTTP time order invalid')
        identity = sha((url + '\n' + metadata['request_start_utc'] + '\n' + digest).encode())[:24]
        expect(event_id == 'EDHREC_NEW_' + identity, 'Event id is not bound to URL/time/SHA')
        body = json.loads(raw)
        lists = body['container']['json_dict']['cardlists']
        expect(isinstance(lists, list) and len(lists) > 0, 'No source cardlists')
        grouped: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for cardlist in lists:
            header = cardlist['header']
            expect(isinstance(header, str), 'Invalid cardlist header')
            for view in cardlist.get('cardviews', []):
                expect(isinstance(view, dict) and isinstance(view.get('name'), str), 'Invalid cardview')
                numer, denom = view.get('num_decks'), view.get('potential_decks')
                expect(type(numer) is int and type(denom) is int and 0 <= numer <= denom,
                       'Invalid source numerator/denominator')
                lift = dec(view.get('lift'))
                grouped[name_key(view['name'])].append((header, view))
        for key, variants in grouped.items():
            signatures = {(v['num_decks'], v['potential_decks'], str(dec(v.get('lift'))))
                          for _, v in variants}
            expect(len(signatures) == 1, 'Conflicting duplicate cardview names')
            view = variants[0][1]
            numer, denom = view['num_decks'], view['potential_decks']
            cards.append((event_id, key, view['name'], str(view.get('id') or ''),
                          ' | '.join(h for h, _ in variants), numer, denom,
                          float(Decimal(100) * numer / denom) if denom else None,
                          db_nullable(view.get('lift')), None,
                          'ORIGINAL_COUNTS_AND_DERIVED_INCLUSION'))
        events.append(dict(event_id=event_id, url=url,
                           began=metadata['request_start_utc'], ended=metadata['response_complete_utc'],
                           sha=digest, raw=raw, date=metadata.get('response_http_date_header_NOT_ORIGIN_TIME')))
    if not (isinstance(source, Path) and source.is_dir()):
        archive.close()
    return events, cards


def validate_review_bundle(package: Path) -> tuple[list[dict], list[tuple], list[tuple], list[tuple]]:
    """Validate the full 24-file sealed archive and every historical crosswalk reference."""
    with zipfile.ZipFile(package) as outer:
        expect(outer.testzip() is None, 'Invalid review package CRC')
        names = set(outer.namelist())
        expect(all(safe_member(x) for x in names), 'Unsafe package entry')
        manifest = json.loads(outer.read('00_LIEFER_MANIFEST_SHA256_REVIEW.json'))
        expect(manifest['automatic_import'] is False and manifest['classification'] == 'REVIEW',
               'Review package wrongly marked as active')
        for entry in manifest['files']:
            path = safe_member(entry['filename'])
            expect(path in names and sha(outer.read(path)) == entry['sha256'] and
                   len(outer.read(path)) == entry['bytes'], f'Package integrity fail: {path}')
        expect(sha(outer.read('C079_EDHREC_ORIGINAL_1379.csv')) == PINNED_C079_SHA256,
               'C079 original primary CSV has wrong SHA')
        captured = outer.read('EDHREC_20_NEUE_HTTP_BELEGE_2026-11-11.zip')
        raw_path = io.BytesIO(captured)
        raw_path.name = 'fresh.zip'
        events, cards = load_captures(raw_path)
        clean = csv_rows(outer.read('STUDIO_EDHREC_1379_PROVENIENZ_GEREINIGT.csv'))
        historical = csv_rows(outer.read('EDHREC_1379_HERKUNFT_UND_ZEITBEWEIS_V2.csv'))
        cross = csv_rows(outer.read('EDHREC_1304_HISTORISCH_VS_NEU_ABGLEICH.csv'))
        fresh = csv_rows(outer.read('EDHREC_20_NEUE_SNAPSHOTS_ALLE_4945_KARTEN.csv'))
        event_table = csv_rows(outer.read('EDHREC_20_NEUE_HTTP_SNAPSHOTS_PROVENIENZ.csv'))
        expect(len(clean) == len(historical) == FULL['historical'] and
               len(cross) == FULL['missing_utc'] and
               len(events) == len(event_table) == FULL['events'] and
               len(cards) == len(fresh) == FULL['cards'], 'Full-review row counts differ')
        keyed = {(card[0], card[1]): card for card in cards}
        expect(len(keyed) == len(cards), 'Duplicate new source page/card pair')
        ev = {event['event_id']: event for event in events}
        evurl = {event['url']: event for event in events}
        expect(len(evurl) == FULL['events'], 'Duplicate event URL')
        for row in fresh:
            key = (row['source_event_id'], name_key(row['card_name']))
            expect(key in keyed, 'Normalized source card not found in raw response')
            card = keyed[key]
            expect(row['source_url'] == ev[key[0]]['url'] and
                   row['raw_body_sha256'] == ev[key[0]]['sha'] and
                   row['new_captured_utc'] == ev[key[0]]['ended'] and
                   row['num_decks'] == str(card[5]) and row['potential_decks'] == str(card[6]) and
                   (dec(row['lift_AS_SOURCE']) is None and card[8] is None or
                    dec(row['lift_AS_SOURCE']) is not None and card[8] is not None and
                    abs(dec(row['lift_AS_SOURCE']) - Decimal(str(card[8]))) <= Decimal('0.000000000001')) and
                   row['automatic_import'] == 'false',
                   'Normalized source card/metric evidence mismatch')
        source_rows: list[tuple] = []
        exact = 0
        lacking = 0
        for origin, audit in zip(clean, historical, strict=True):
            expect(origin['card_id'] == audit['card_id'] and
                   origin['oracle_id'] == audit['oracle_id'] and
                   origin['card_name'] == audit['card_name'] and
                   origin['theme'] == audit['theme'] and origin['url'] == audit['source_url'] and
                   origin['num_decks'] == audit['num_decks'] and
                   origin['potential_decks'] == audit['potential_decks'] and
                   dec(origin['inclusion_pct']) == dec(audit['inclusion_pct']) and
                   dec(origin['lift']) == dec(audit['lift']),
                   'Historical audit does not match cleaned source')
            proof = audit['historical_exact_utc_proven'] == 'true'
            expect(audit['historical_exact_utc_proven'] in ('true','false') and
                   audit['historical_snapshot_utc_UNMODIFIED'] == origin['snapshot_utc'],
                   'Historical UTC proof status mismatch')
            if proof:
                utc(origin['snapshot_utc'])
                exact += 1
            else:
                expect(origin['snapshot_utc'] == '' and audit['safe_timestamp_action'] ==
                       'KEEP_NULL_AND_PRESERVE_SOURCE', 'Invented old timestamp')
                lacking += 1
            source_rows.append((int(audit['source_C079_csv_line']), audit['card_id'],
                  audit['oracle_id'] or None, audit['card_name'], audit['theme'], audit['source_url'],
                  int(audit['num_decks']) if audit['num_decks'] else None,
                  int(audit['potential_decks']) if audit['potential_decks'] else None,
                  db_nullable(audit['inclusion_pct']), db_nullable(audit['lift']),
                  origin['snapshot_utc'] or None, int(proof),
                  audit['C079_HTML_original_metric_proof'], audit['C079_exact_HTTP200_source_evidence'],
                  'LEGACY_C079'))
        expect(exact == FULL['exact_utc'] and lacking == FULL['missing_utc'],
               '75 exact / 1304 unknown historical UTC invariant failed')
        id_map = {(r[1], r[4], r[5]): r[0] for r in source_rows if r[11] == 0}
        expect(len(id_map) == lacking, 'Historical references not unique')
        links: list[tuple] = []
        states = Counter()
        for row in cross:
            key = (row['historical_card_id_UNCHANGED'], row['theme'], row['source_url'])
            expect(key in id_map and row['historical_backfill_allowed'] == 'false' and
                   row['automatic_import'] == 'false' and
                   row['HISTORICAL_original_snapshot_utc_BLANK'] == '',
                   'Crosswalk references unknown row or fabricates historical UTC')
            event = evurl[row['source_url']]
            expect(row['FRESH_source_event_id'] == event['event_id'] and
                   row['FRESH_capture_utc_DO_NOT_BACKFILL'] == event['ended'] and
                   row['FRESH_raw_response_sha256'] == event['sha'],
                   'Crosswalk fresh capture reference mismatch')
            status = row['FRESH_match_status']
            hit = keyed.get((event['event_id'], name_key(row['card_name'])))
            if status == 'NEW_CAPTURE_MATCHED_EXACT_NAME':
                expect(hit is not None and row['FRESH_num_decks'] == str(hit[5]) and
                       row['FRESH_potential_decks'] == str(hit[6]),
                       'Fresh crosswalk count mismatch')
            elif status == 'NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN':
                expect(hit is None and not row['FRESH_num_decks'] and not row['FRESH_potential_decks']
                       and not row['FRESH_inclusion_pct_DERIVED_from_counts'],
                       'Absent new card wrongly treated as zero')
            else:
                raise ValueError(f'Unexpected crosswalk status {status!r}')
            states[status] += 1
            links.append((id_map[key], event['event_id'], name_key(row['card_name']), status))
        expect(len({x[0] for x in links}) == lacking, 'Missing/duplicate crosswalk references')
        expect(states == {'NEW_CAPTURE_MATCHED_EXACT_NAME': FULL['matched'],
                          'NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN': FULL['not_listed']},
               'Historical-to-fresh source match counts changed')
        return events, cards, source_rows, links


def connect(db_path: Path) -> sqlite3.Connection:
    target = db_path.expanduser().resolve()
    expect(target.name.lower() != 'studio.sqlite3', 'Refusing to modify the production Studio database')
    # Deny accidental database creation in the checked-out repository.
    roots = [p for p in Path(__file__).resolve().parents if (p / 'pyproject.toml').is_file() and (p / 'src').is_dir()]
    expect(not any(target.is_relative_to(repo) for repo in roots), 'Evidence database must live outside Git')
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.execute('PRAGMA foreign_keys=ON')
    known = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if {'source', 'inventory', 'observation'} & known:
        conn.close()
        raise ValueError('Refusing to alter a Studio production or mixed database')
    return conn


def import_validated(conn: sqlite3.Connection, events: list[dict], cards: list[tuple],
                     historical: list[tuple] | None = None,
                     links: list[tuple] | None = None) -> dict:
    # Validate all source material before starting the write transaction.
    expect(bool(events) and len(cards) >= 1, 'Missing captured source values')
    conn.execute('BEGIN IMMEDIATE')
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        for event in events:
            conn.execute('INSERT OR IGNORE INTO edhrec_capture_event VALUES (?,?,?,?,?,?,?,?,?)',
                         (event['event_id'], event['url'], event['began'], event['ended'],
                          event['sha'], 200, event['raw'], event['date'], 'NEW_HTTP_CAPTURED'))
            actual = conn.execute('SELECT url, request_start_utc, response_complete_utc, raw_sha256, '
                                  'raw_json FROM edhrec_capture_event WHERE event_id=?',
                                  (event['event_id'],)).fetchone()
            expect(actual == (event['url'], event['began'], event['ended'], event['sha'], event['raw']),
                   'Existing immutable event has conflicting payload')
        conn.executemany('INSERT OR IGNORE INTO edhrec_capture_card VALUES (?,?,?,?,?,?,?,?,?,?,?)', cards)
        for card in cards:
            actual = conn.execute('SELECT card_name, numerator, denominator, inclusion_pct_derived, '
                                  'lift_as_source, edhrec_cardview_id FROM edhrec_capture_card '
                                  'WHERE event_id=? AND card_name_key=?', (card[0], card[1])).fetchone()
            expect(actual[0] == card[2] and actual[1:5] == card[5:9] and actual[5] == card[3],
                   'Existing source card has conflicting metrics')
        if historical is not None:
            conn.executemany('INSERT OR IGNORE INTO edhrec_c079_historical_audit VALUES '
                             '(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', historical)
            for row in historical:
                actual = conn.execute('SELECT * FROM edhrec_c079_historical_audit '
                                      'WHERE source_csv_line=?', (row[0],)).fetchone()
                expect(tuple(actual) == row, 'Conflict with immutable C079 historical audit')
        if links is not None:
            conn.executemany('INSERT OR IGNORE INTO edhrec_c079_fresh_link VALUES (?,?,?,?)', links)
            for link in links:
                actual = conn.execute('SELECT * FROM edhrec_c079_fresh_link WHERE source_csv_line=?',
                                      (link[0],)).fetchone()
                expect(tuple(actual) == link, 'Conflict with immutable C079/fresh crosswalk')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return summary(conn)


def summary(conn: sqlite3.Connection) -> dict:
    def n(table: str, where: str = '') -> int:
        return conn.execute(f'SELECT count(*) FROM {table} {where}').fetchone()[0]
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'edhrec_capture_event' not in existing:
        return dict(archive_imported=False, events=0, new_cards=0, historical=0, historical_exact=0,
                    historical_unknown=0, matched=0, absent_current_unknown=0,
                    original_historical_timestamp_changed=0)
    historical = n('edhrec_c079_historical_audit')
    return dict(archive_imported=historical > 0,
                events=n('edhrec_capture_event'), new_cards=n('edhrec_capture_card'),
                historical=historical,
                historical_exact=n('edhrec_c079_historical_audit','WHERE exact_utc_proven=1'),
                historical_unknown=n('edhrec_c079_historical_audit','WHERE exact_utc_proven=0'),
                matched=n('edhrec_c079_fresh_link',"WHERE status='NEW_CAPTURE_MATCHED_EXACT_NAME'"),
                absent_current_unknown=n('edhrec_c079_fresh_link',
                    "WHERE status='NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN'"),
                original_historical_timestamp_changed=0, automatic_import=False)


def evidence_for_card(conn: sqlite3.Connection, card: str) -> dict:
    key = name_key(card)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='edhrec_capture_card'").fetchone():
        return {'card_name': card, 'historical': [], 'fresh': []}
    fresh = [dict(event_id=r[0], card_name=r[1], numerator=r[2], denominator=r[3],
                  inclusion_pct_derived=r[4], lift_as_source=r[5], source_url=r[6],
                  captured_utc=r[7], data_origin='NEW_HTTP_CAPTURED') for r in conn.execute(
                      'SELECT c.event_id,c.card_name,c.numerator,c.denominator,c.inclusion_pct_derived,'
                      'c.lift_as_source,e.url,e.response_complete_utc FROM edhrec_capture_card c '
                      'JOIN edhrec_capture_event e ON c.event_id=e.event_id WHERE c.card_name_key=? '
                      'ORDER BY e.response_complete_utc', (key,))]
    historical = [dict(card_name=r[0], theme=r[1], source_url=r[2], numerator=r[3],
                       denominator=r[4], inclusion_pct_as_source=r[5], lift_as_source=r[6],
                       snapshot_utc=r[7], exact_utc_proven=bool(r[8]),
                       data_origin='LEGACY_C079') for r in conn.execute(
                           'SELECT card_name,theme,url,numerator,denominator,inclusion_pct_as_source,'
                           'lift_as_source,snapshot_utc,exact_utc_proven '
                           'FROM edhrec_c079_historical_audit WHERE lower(card_name)=? '
                           'ORDER BY theme', (key,))]
    return {'card_name': card, 'historical': historical, 'fresh': fresh}


def cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True, help='Private SQLite path OUTSIDE repository')
    sub = p.add_subparsers(dest='command', required=True)
    new = sub.add_parser('import-new', help='Import captured HTTP200 raw folder or ZIP only')
    new.add_argument('source', type=Path)
    full = sub.add_parser('import-review', help='Atomic import of sealed C079+new 24-file ZIP')
    full.add_argument('source', type=Path)
    sub.add_parser('status')
    card = sub.add_parser('card', help='Show separate historic and new card/page observations')
    card.add_argument('name')
    args = p.parse_args(argv)
    if args.command == 'import-new':
        events, cards = load_captures(args.source)
    elif args.command == 'import-review':
        events, cards, historical, links = validate_review_bundle(args.source)
    conn = connect(args.db)
    try:
        if args.command == 'import-new':
            value = import_validated(conn, events, cards)
        elif args.command == 'import-review':
            value = import_validated(conn, events, cards, historical, links)
        elif args.command == 'status':
            value = summary(conn)
        else:
            value = evidence_for_card(conn, args.name)
        print(json.dumps(value, indent=2, ensure_ascii=False))
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(cli())
