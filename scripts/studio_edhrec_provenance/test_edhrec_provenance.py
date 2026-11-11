"""Strict, stdlib-only tests for immutable EDHREC research imports."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('edhrec_provenance', Path(__file__).with_name('edhrec_provenance.py'))
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

URL = 'https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/blink.json'
START = '2026-11-11T12:55:00.000Z'
END = '2026-11-11T12:55:00.200Z'
BODY = {'container': {'json_dict': {'cardlists': [
    {'header': 'High Synergy Cards', 'cardviews': [
        {'name': 'Test Cloud', 'id': 'NOT-ORACLE', 'num_decks': 8, 'potential_decks': 16, 'lift': 1.6},
        {'name': 'Uncounted', 'id': 'NOT-ORACLE-2', 'num_decks': 0, 'potential_decks': 0},
    ]},
    {'header': 'Duplicate Listing', 'cardviews': [
        {'name': 'Test Cloud', 'id': 'NOT-ORACLE', 'num_decks': 8, 'potential_decks': 16, 'lift': 1.6}
    ]},
]}}}


def build_archive(path: Path, *, bad_digest: bool = False, bad_url: bool = False,
                  conflicting_card: bool = False) -> None:
    body = json.loads(json.dumps(BODY))
    if conflicting_card:
        body['container']['json_dict']['cardlists'][1]['cardviews'][0]['num_decks'] = 7
    raw = json.dumps(body, separators=(',', ':')).encode()
    digest = hashlib.sha256(raw).hexdigest()
    url = URL if not bad_url else 'https://example.org/private-data.json'
    identity = hashlib.sha256((url + '\n' + START + '\n' + digest).encode()).hexdigest()[:24]
    event_id = 'EDHREC_NEW_' + identity
    meta = {'event_id': event_id, 'url': url, 'http_status': 200, 'request_start_utc': START,
            'response_complete_utc': END, 'raw_response_sha256': digest,
            'raw_size_bytes': len(raw), 'response_http_date_header_NOT_ORIGIN_TIME': 'fake header',
            'automatic_import': False, 'historical_C079_timestamp_backfilled': False}
    rec = {'event_id': event_id, 'url': url, 'raw': f'raw/{event_id}.json',
           'metadata': f'observations/{event_id}.json', 'sha256': 'a' * 64 if bad_digest else digest,
           'observed_utc': END}
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('manifest.json', json.dumps({'records': [rec]}))
        z.writestr(rec['raw'], raw)
        z.writestr(rec['metadata'], json.dumps(meta))


class ProvenanceTest(unittest.TestCase):
    def test_production_studio_database_is_always_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError, 'production Studio database'):
                mod.connect(Path(t) / 'studio.sqlite3')
            path = Path(t) / 'renamed.sqlite3'
            conn = sqlite3.connect(path)
            conn.execute('CREATE TABLE observation (id INTEGER)')
            conn.commit()
            conn.close()
            with self.assertRaisesRegex(ValueError, 'Studio production or mixed database'):
                mod.connect(path)

    def test_capture_import_is_idempotent_and_derived_is_separate(self):
        with tempfile.TemporaryDirectory() as t:
            archive = Path(t) / 'capture.zip'
            dbfile = Path(t) / 'out.sqlite3'
            build_archive(archive)
            for _ in range(2):
                events, cards = mod.load_captures(archive)
                with mod.connect(dbfile) as db:
                    out = mod.import_validated(db, events, cards)
                self.assertEqual((out['events'], out['new_cards']), (1, 2))
                self.assertEqual(out['historical_unknown'], 0)
            with mod.connect(dbfile) as db:
                values = db.execute('SELECT numerator,denominator,inclusion_pct_derived,oracle_id '
                                    'FROM edhrec_capture_card WHERE card_name_key=?',
                                    ('test cloud',)).fetchone()
                self.assertEqual(values, (8, 16, 50.0, None))
                empty = db.execute('SELECT inclusion_pct_derived FROM edhrec_capture_card '
                                   'WHERE card_name_key=?', ('uncounted',)).fetchone()
                self.assertIsNone(empty[0])
                self.assertEqual(mod.evidence_for_card(db, 'Test Cloud')['fresh'][0]['captured_utc'], END)
                self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='observation'").fetchone())

    def test_bad_sha_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'bad.zip'
            build_archive(src, bad_digest=True)
            with self.assertRaisesRegex(ValueError, 'Raw SHA'):
                mod.load_captures(src)
            self.assertFalse((Path(t) / 'out.sqlite3').exists())

    def test_bad_url_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'bad.zip'
            build_archive(src, bad_url=True)
            with self.assertRaisesRegex(ValueError, 'URL invalid'):
                mod.load_captures(src)

    def test_conflicting_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'bad.zip'
            build_archive(src, conflicting_card=True)
            with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
                mod.load_captures(src)

    def test_event_mismatch_rolls_back_insert(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'source.zip'
            dbfile = Path(t) / 'out.sqlite3'
            build_archive(src)
            events, cards = mod.load_captures(src)
            with mod.connect(dbfile) as conn:
                mod.import_validated(conn, events, cards)
                conn.execute('UPDATE edhrec_capture_card SET numerator=1 '
                             "WHERE card_name_key='test cloud'")
                conn.commit()
                with self.assertRaisesRegex(ValueError, 'conflicting metrics'):
                    mod.import_validated(conn, events, cards)
                self.assertEqual(conn.execute('SELECT numerator FROM edhrec_capture_card '
                                              "WHERE card_name_key='test cloud'").fetchone()[0], 1)

    def test_no_historical_timestamp_backfill_even_when_importing_capture(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'source.zip'
            build_archive(src)
            events, cards = mod.load_captures(src)
            with mod.connect(Path(t) / 'out.sqlite3') as conn:
                mod.import_validated(conn, events, cards)
                self.assertEqual(mod.summary(conn)['historical'], 0)
                self.assertEqual(mod.summary(conn)['original_historical_timestamp_changed'], 0)
                self.assertTrue(conn.execute('SELECT raw_json FROM edhrec_capture_event').fetchone()[0])


if __name__ == '__main__':
    unittest.main()
