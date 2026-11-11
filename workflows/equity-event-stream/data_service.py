"""Read-only, time-gated data service over the full market.db.

The on-disk database physically contains every row, including disclosures that
only become public later in the shift.  This service materialises an in-memory
database containing *only* rows whose available_at_s <= business time, so an
agent's SQL can never observe private future information.
"""
import sqlite3

EXPOSED = {
    'issuers': 'issuer_id, ticker, name, cik, sector, is_subject',
    'filings': ('filing_id, issuer_id, form, accession, accepted_at_utc, period_end, '
                'fiscal_period, title, source_url, available_at_s'),
    'documents': 'doc_id, filing_id, doc_type, title, chars, source_url, available_at_s',
    'xbrl_facts': ('fact_id, issuer_id, concept, unit, start_date, end_date, fiscal_year, '
                   'fiscal_period, form, filed_at_utc, value, available_at_s'),
    'consensus_estimates': ('estimate_id, issuer_id, metric, fiscal_period, value, unit, '
                            'source, as_of_utc, available_at_s'),
    'prices': 'symbol, trade_date, open, high, low, close, volume, available_at_s',
    'issuer_events': ('event_id, issuer_id, form, event_date, summary, published_at_utc, '
                      'document_id, available_at_s'),
}
FORBIDDEN = ('attach', 'detach', 'pragma', 'insert', 'update', 'delete', 'create', 'drop',
             'alter', 'vacuum', 'replace', 'load_extension', 'readfile', 'writefile',
             'sqlite_master', 'sqlite_schema', 'sqlite_temp_master',
             'sqlite_temp_schema', 'src.')
MAX_ROWS = 100


class DataRejected(Exception):
    pass


class DataService:
    def __init__(self, db_path, clock):
        self.db_path = str(db_path)
        self.clock = clock
        self._built_at = None
        self._mem = None

    # -- visibility ---------------------------------------------------------
    def _build(self, now):
        mem = sqlite3.connect(':memory:')
        mem.execute('ATTACH DATABASE ? AS src', (self.db_path,))
        try:
            for table, cols in EXPOSED.items():
                if table == 'documents':
                    source = 'SELECT %s FROM src.filing_documents WHERE available_at_s <= ?' % cols
                elif table == 'issuers':
                    source = 'SELECT %s FROM src.issuers' % cols
                    mem.execute('CREATE TABLE %s AS %s' % (table, source))
                    continue
                else:
                    source = 'SELECT %s FROM src.%s WHERE available_at_s <= ?' % (cols, table)
                mem.execute('CREATE TABLE %s AS %s' % (table, source), (now,))
            mem.execute('CREATE INDEX IF NOT EXISTS idx_docs_doc ON documents(doc_id)')
            mem.execute('CREATE INDEX IF NOT EXISTS idx_filings_fil ON filings(filing_id)')
        finally:
            mem.execute('DETACH DATABASE src')
        self._mem = mem
        self._built_at = now
        return mem

    def _visible(self):
        now = int(self.clock())
        if self._mem is None or self._built_at != now:
            return self._build(now)
        return self._mem

    def invalidate(self):
        self._mem = None
        self._built_at = None

    # -- agent tool implementations ----------------------------------------
    def query(self, sql):
        if not isinstance(sql, str) or not sql.strip():
            raise DataRejected('Nonempty SQL string required')
        text = sql.strip()
        lowered = text.lower()
        if any(word in lowered for word in FORBIDDEN):
            raise DataRejected('Only read-only SELECT queries over published tables are allowed')
        if not (lowered.startswith('select') or lowered.startswith('with')):
            raise DataRejected('Only SELECT queries are allowed')
        if ';' in text:
            raise DataRejected('One statement only')
        mem = self._visible()
        allowed = set(EXPOSED)
        allowed.add('sqlite_master')

        def authorizer(code, arg1, arg2, dbname, source):
            if code == sqlite3.SQLITE_SELECT:
                return sqlite3.SQLITE_OK
            if code == sqlite3.SQLITE_FUNCTION:
                return sqlite3.SQLITE_OK
            if code == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if arg1 in allowed else sqlite3.SQLITE_DENY
            if code == sqlite3.SQLITE_RECURSIVE:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        steps = {'n': 0}

        def progress():
            steps['n'] += 1
            return 1 if steps['n'] > 200000 else 0

        mem.set_authorizer(authorizer)
        mem.set_progress_handler(progress, 10000)
        try:
            cursor = mem.execute(text)
            rows = cursor.fetchmany(MAX_ROWS)
            columns = [d[0] for d in (cursor.description or [])]
            result = [dict(zip(columns, row)) for row in rows]
            return {'columns': columns, 'rows': result,
                    'row_count': len(result), 'truncated': len(result) >= MAX_ROWS,
                    'business_time_s': int(self.clock())}
        except sqlite3.Error as exc:
            raise DataRejected('SQL error: %s' % exc)
        finally:
            mem.set_authorizer(None)
            mem.set_progress_handler(None, 0)

    def catalog(self):
        mem = self._visible()
        tables = []
        for table in EXPOSED:
            info = mem.execute('PRAGMA table_info(%s)' % table).fetchall()
            count = mem.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
            tables.append({'table': table,
                           'columns': [{'name': r[1], 'type': r[2]} for r in info],
                           'row_count': count})
        return {'tables': tables, 'business_time_s': int(self.clock())}

    def read(self, doc_id):
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise DataRejected('doc_id required')
        now = int(self.clock())
        con = sqlite3.connect('file:%s?mode=ro' % self.db_path, uri=True)
        try:
            row = con.execute('SELECT content, title, available_at_s FROM filing_documents '
                              'WHERE doc_id = ?', (doc_id.strip(),)).fetchone()
        finally:
            con.close()
        if not row:
            raise DataRejected('Unknown document id: %s' % doc_id)
        content, title, available = row
        if available > now:
            raise DataRejected('Document is not published at the current business time')
        return {'doc_id': doc_id, 'title': title, 'chars': len(content),
                'content': content, 'business_time_s': now}
