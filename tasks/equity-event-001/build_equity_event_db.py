#!/usr/bin/env python3
"""Build market.db for equity-event-001 from the real-data fixtures in data/.

The database physically contains every row, including disclosures that only become
public later in the 2026-04-29 shift.  Every row carries an ``available_at_s`` column
(business seconds since 2026-04-29 15:00 ET).  The workflow controller's data service
filters on that column at query time, so the agent can never read private future rows.

Data provenance: SEC EDGAR (CIK 1652044 and the peer CIKs), Yahoo Finance daily bars,
and the two consensus estimates quoted by the Zacks article referenced in ILE task O19.
All values are real; no synthetic numbers are introduced by this build.
"""
import csv
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
WORKSPACE = os.path.join(BASE, 'environment', 'initial_workspace')
DB_PATH = os.path.join(WORKSPACE, 'market.db')
EPOCH = datetime(2026, 4, 29, 19, 0, 0, tzinfo=timezone.utc)  # 15:00 ET (EDT)
SHIFT_END_S = 23400  # 21:30 ET

PEERS = [
    ('MSFT', 'Microsoft Corp', '789019', 'Information Technology'),
    ('META', 'Meta Platforms, Inc.', '1326801', 'Communication Services'),
    ('AMZN', 'Amazon.com, Inc.', '1018724', 'Consumer Discretionary'),
    ('AAPL', 'Apple Inc.', '320193', 'Information Technology'),
    ('NVDA', 'NVIDIA Corp', '1045810', 'Information Technology'),
    ('TSLA', 'Tesla, Inc.', '1318605', 'Consumer Discretionary'),
    ('ORCL', 'Oracle Corp', '1341439', 'Information Technology'),
    ('INTC', 'Intel Corp', '50863', 'Information Technology'),
]

# doc_id, source csv key, doc_type, title, SEC url path component inside the filing dir
DOCS = [
    ('googl-8k-20260429-ex991', '000043_ex99_1', 'ex99_1',
     'Alphabet Q1 2026 earnings press release (8-K EX-99.1)'),
    ('googl-8k-20260429', '000043_primary', 'primary', 'Form 8-K, 2026-04-29'),
    ('googl-10q-20260331', '000048_primary', 'primary', 'Form 10-Q, quarter ended 2026-03-31'),
    ('googl-10k-20251231', '000018_primary', 'primary', 'Form 10-K, fiscal year 2025'),
    ('googl-8k-20260410', '000034_primary', 'primary', 'Form 8-K, 2026-04-10'),
    ('googl-8k-20260402', '000031_primary', 'primary', 'Form 8-K, 2026-04-02'),
]


def ts(value):
    return datetime.strptime(value.replace('Z', '+0000'), '%Y-%m-%dT%H:%M:%S%z')


def avail(value):
    """business seconds since 15:00 ET; disclosures before the shift are visible at t=0."""
    seconds = int((ts(value) - EPOCH).total_seconds())
    return max(0, seconds)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(name):
    with open(os.path.join(DATA, name), newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def build():
    os.makedirs(WORKSPACE, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript('''
        CREATE TABLE issuers (
            issuer_id TEXT PRIMARY KEY, ticker TEXT, name TEXT, cik TEXT,
            sector TEXT, is_subject INTEGER);
        CREATE TABLE filings (
            filing_id TEXT PRIMARY KEY, issuer_id TEXT, form TEXT, accession TEXT,
            accepted_at_utc TEXT, period_end TEXT, fiscal_period TEXT, title TEXT,
            source_url TEXT, available_at_s INTEGER);
        CREATE TABLE filing_documents (
            doc_id TEXT PRIMARY KEY, filing_id TEXT, doc_type TEXT, title TEXT,
            chars INTEGER, source_url TEXT, available_at_s INTEGER, content TEXT);
        CREATE TABLE xbrl_facts (
            fact_id TEXT PRIMARY KEY, issuer_id TEXT, concept TEXT, unit TEXT,
            start_date TEXT, end_date TEXT, fiscal_year INTEGER, fiscal_period TEXT,
            form TEXT, filed_at_utc TEXT, value TEXT, available_at_s INTEGER);
        CREATE TABLE consensus_estimates (
            estimate_id TEXT PRIMARY KEY, issuer_id TEXT, metric TEXT,
            fiscal_period TEXT, value REAL, unit TEXT, source TEXT,
            as_of_utc TEXT, available_at_s INTEGER);
        CREATE TABLE prices (
            symbol TEXT, trade_date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume INTEGER, available_at_s INTEGER,
            PRIMARY KEY (symbol, trade_date));
        CREATE TABLE issuer_events (
            event_id TEXT PRIMARY KEY, issuer_id TEXT, form TEXT, event_date TEXT,
            summary TEXT, published_at_utc TEXT, document_id TEXT,
            available_at_s INTEGER);
        CREATE INDEX idx_filings_avail ON filings(available_at_s);
        CREATE INDEX idx_docs_avail ON filing_documents(available_at_s);
        CREATE INDEX idx_xbrl_avail ON xbrl_facts(available_at_s);
        CREATE INDEX idx_prices_avail ON prices(available_at_s);
        CREATE INDEX idx_events_avail ON issuer_events(available_at_s);
    ''')

    # -- issuers ------------------------------------------------------------
    cur.execute('INSERT INTO issuers VALUES (?,?,?,?,?,?)',
                ('GOOGL', 'GOOGL', 'Alphabet Inc.', '1652044', 'Communication Services', 1))
    for ticker, name, cik, sector in PEERS:
        cur.execute('INSERT INTO issuers VALUES (?,?,?,?,?,?)',
                    (ticker, ticker, name, cik, sector, 0))

    # -- filings ------------------------------------------------------------
    filings = read_csv('filings.csv')
    accession_avail = {}
    for row in filings:
        available = avail(row['accepted_at_utc'])
        accession_avail[row['accession']] = available
        period = row['period'] or ''
        cur.execute('INSERT INTO filings VALUES (?,?,?,?,?,?,?,?,?,?)', (
            row['accession'], 'GOOGL', row['form'], row['accession'],
            row['accepted_at_utc'], period,
            quarter_label(period, row['form']), row['title'], row['filing_url'], available))
    for row in read_csv('peers.csv'):
        available = avail(row['accepted_at_utc'])
        cur.execute('INSERT INTO filings VALUES (?,?,?,?,?,?,?,?,?,?)', (
            row['accession'], row['ticker'], row['form'], row['accession'],
            row['accepted_at_utc'], row['period'],
            quarter_label(row['period'], row['form']), row['title'],
            row['filing_url'], available))

    # -- filing documents (real text extracted from the EDGAR primary docs) --
    doc_meta = {row['doc_id']: row for row in read_csv('filing_documents.csv')}
    filing_by_id = {row['accession']: row for row in filings}
    for row in read_csv('peers.csv'):
        filing_by_id.setdefault(row['accession'], row)
    acc_by_key = {
        '000043': '0001652044-26-000043', '000048': '0001652044-26-000048',
        '000018': '0001652044-26-000018', '000034': '0001652044-26-000034',
        '000031': '0001652044-26-000031',
    }
    for doc_id, source_key, doc_type, title in DOCS:
        meta = doc_meta[source_key]
        accession = acc_by_key[source_key.split('_')[0]]
        filing = filing_by_id[accession]
        text_path = os.path.join(BASE, meta['text_path'])
        content = open(text_path, encoding='utf-8').read()
        cur.execute('INSERT INTO filing_documents VALUES (?,?,?,?,?,?,?,?)', (
            doc_id, accession, doc_type, title, len(content),
            filing['filing_url'], avail(filing['accepted_at_utc']), content))

    # -- peer filing documents (real press releases shipped as information-flow noise) --
    EXTRA_DOCS = [
        ('peer-msft-8k-20260429-ex991', '0001193125-26-191457', 'ex99_1',
         'Microsoft FY2026 Q3 earnings press release (8-K EX-99.1)',
         'data/docs/peer-msft-8k-20260429-ex991.txt',
         'https://www.sec.gov/Archives/edgar/data/789019/000119312526191457/msft-ex99_1.htm'),
        ('peer-meta-8k-20260429-ex991', '0001628280-26-028364', 'ex99_1',
         'Meta 2026 Q1 earnings press release (8-K EX-99.1)',
         'data/docs/peer-meta-8k-20260429-ex991.txt',
         'https://www.sec.gov/Archives/edgar/data/1326801/000162828026028364/meta-03312026xexhibit991.htm'),
        ('peer-amzn-8k-20260429-ex991', '0001018724-26-000012', 'ex99_1',
         'Amazon 2026 Q1 earnings press release (8-K EX-99.1)',
         'data/docs/peer-amzn-8k-20260429-ex991.txt',
         'https://www.sec.gov/Archives/edgar/data/1018724/000101872426000012/amzn-20260331xex991.htm'),
    ]
    for doc_id, accession, doc_type, title, text_path, source_url in EXTRA_DOCS:
        filing = filing_by_id[accession]
        content = open(os.path.join(BASE, text_path), encoding='utf-8').read()
        cur.execute('INSERT INTO filing_documents VALUES (?,?,?,?,?,?,?,?)', (
            doc_id, accession, doc_type, title, len(content),
            source_url, avail(filing['accepted_at_utc']), content))

    # -- xbrl facts (full real us-gaap population, 2012-2026, no post-event facts)
    facts = read_csv('xbrl_facts.csv')
    for index, row in enumerate(facts):
        accession = row['accession']
        if accession in accession_avail:
            available = accession_avail[accession]
        else:
            # companyfacts only gives a filed date; fall back to publication time and
            # clamp anything already public before the shift to t=0 (future facts stay hidden).
            filed = row['filed_utc']
            available = max(0, int((ts(filed) - EPOCH).total_seconds()))
        value = row['val']
        cur.execute('INSERT INTO xbrl_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
            'x%05d' % index, 'GOOGL', row['concept'], row['unit'],
            row['period_start'] or row['period_end'], row['period_end'],
            int(row['fiscal_year']) if row['fiscal_year'] else None,
            row['fiscal_period'], row['form'], row['filed_utc'], value, available))

    # -- consensus estimates (frozen pre-cutoff Zacks figures, real) --------
    for index, row in enumerate(read_csv('consensus.csv'), 1):
        cur.execute('INSERT INTO consensus_estimates VALUES (?,?,?,?,?,?,?,?,?)', (
            'est-%02d' % index, 'GOOGL', row['metric'], row['period'],
            float(row['value']), row['unit'], row['source'],
            row['as_of_utc'], avail(row['as_of_utc'])))

    # -- daily prices (real Yahoo bars; bars after the shift stay hidden) ---
    for row in read_csv('prices.csv'):
        cur.execute('INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)', (
            row['symbol'], row['date'], float(row['open']), float(row['high']),
            float(row['low']), float(row['close']), int(float(row['volume'])),
            avail(row['available_at_utc'])))

    # -- issuer events (EDGAR monitoring feed built from real filing metadata)
    for row in read_csv('peers.csv'):
        if '2.02' not in (row['items'] or ''):
            continue
        event_id = 'event-' + row['accession']
        cur.execute('INSERT INTO issuer_events VALUES (?,?,?,?,?,?,?,?)', (
            event_id, row['ticker'], row['form'], row['period'] or '',
            '%s filed an 8-K reporting quarterly results (Item 2.02)' % row['company'],
            row['accepted_at_utc'], None, avail(row['accepted_at_utc'])))
    for row in filings:
        event_id = 'event-' + row['accession']
        cur.execute('INSERT INTO issuer_events VALUES (?,?,?,?,?,?,?,?)', (
            event_id, 'GOOGL', row['form'], row['period'] or '',
            'Alphabet filed %s' % row['form'], row['accepted_at_utc'],
            row['accession'], avail(row['accepted_at_utc'])))

    con.commit()
    counts = {table: cur.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
              for table in ('issuers', 'filings', 'filing_documents', 'xbrl_facts',
                            'consensus_estimates', 'prices', 'issuer_events')}
    con.close()

    provenance = {
        'case_id': 'equity-event-001',
        'subject': 'Alphabet Inc. (GOOGL, CIK 1652044) Q1 2026 earnings evening',
        'built_for_shift_utc': '2026-04-29T15:00:00-04:00',
        'epoch_utc': EPOCH.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'shift_end_s': SHIFT_END_S,
        'availability_rule': 'available_at_s = max(0, seconds between source publication time and 2026-04-29T19:00:00Z); tool filters rows with available_at_s <= business_time_s',
        'sources': {
            'filings_and_documents': 'SEC EDGAR filings for CIK 1652044 (acceptance timestamps from data.sec.gov submissions)',
            'xbrl_facts': 'SEC companyfacts CIK0001652044 (us-gaap facts, period_end <= 2026-03-31; 622 post-event facts excluded upstream)',
            'prices': 'Yahoo Finance chart API daily bars for GOOGL',
            'consensus': 'Zacks consensus figures (91.69 USD bn net revenue, 2.76 USD EPS) as quoted in ILE task O19 news document, published 2026-03-17',
            'peers': 'SEC EDGAR submissions for 8 large-cap peers (filings metadata only)',
        },
        'counts': counts,
        'data_files': {name: sha256(os.path.join(DATA, name)) for name in sorted(os.listdir(DATA))
                       if os.path.isfile(os.path.join(DATA, name))},
        'db_sha256': sha256(DB_PATH),
        'db_bytes': os.path.getsize(DB_PATH),
    }
    with open(os.path.join(BASE, 'build_provenance.json'), 'w', encoding='utf-8') as handle:
        json.dump(provenance, handle, indent=1, ensure_ascii=False)
    print(json.dumps(counts, indent=1))
    print('market.db bytes:', os.path.getsize(DB_PATH))
    print('db sha256:', provenance['db_sha256'])


def quarter_label(period, form):
    if not period:
        return ''
    if form in ('10-Q', '10-Q/A'):
        return '%sQ%d' % (period[:4], (int(period[5:7]) - 1) // 3 + 1)
    if form in ('10-K', '10-K/A'):
        return '%sFY' % period[:4]
    return 'EVENT'


if __name__ == '__main__':
    sys.exit(build())
