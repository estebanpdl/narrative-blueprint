"""Durable per-occurrence generation outcomes, separate from vector storage."""

import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from narrative_blueprint.corpus.contracts import SPACE_FIELDS, digest, encoded
from narrative_blueprint.corpus.validation import document_signature
from narrative_blueprint.databases.database import Database


class GenerationIncomplete(RuntimeError):
    """Generation has terminal failures; no downstream success is implied."""


class OutcomeLedger:
    def __init__(self, path, uuids, texts, recipe):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects previous receipts, including interrupted runs.
        with self.path.open("xb"):
            pass
        self.db = sqlite3.connect(self.path)
        self.generation_id = str(uuid4())
        try:
            self.db.executescript('''
                PRAGMA synchronous=FULL;
                CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE outcomes (
                    ordinal INTEGER PRIMARY KEY,occurrence_id TEXT UNIQUE NOT NULL,
                    source_uuid TEXT NOT NULL,text_hash TEXT NOT NULL,
                    state TEXT NOT NULL,reason TEXT,response_hash TEXT
                );
                CREATE INDEX outcomes_state ON outcomes(state,ordinal);
            ''')
            self.db.executemany("INSERT INTO metadata VALUES (?,?)", [
                ("schema", "generation-ledger-1"), ("status", "running"),
                ("generation_id", self.generation_id), ("recipe", json.dumps(recipe)),
            ])
            for ordinal, (uuid, text) in enumerate(zip(uuids, texts, strict=True), 1):
                if not isinstance(uuid, str) or not uuid.strip() or not isinstance(text, str) or not text.strip():
                    raise ValueError("Generation requires nonempty string UUIDs and texts")
                occurrence = digest(encoded([self.generation_id, ordinal, uuid]))
                self.db.execute("INSERT INTO outcomes VALUES (?,?,?,?, 'pending', NULL, NULL)",
                                (ordinal, occurrence, uuid, digest(text.encode("utf-8"))))
            self.db.commit()
        except BaseException:
            self.db.close()
            raise

    def fail_request(self, count):
        self.db.execute('''UPDATE outcomes SET state='provider_failed',reason='provider_failure'
            WHERE ordinal IN (SELECT ordinal FROM outcomes WHERE state='pending' ORDER BY ordinal LIMIT ?)''', (count,))
        self.db.commit()

    def finish(self, failed=False, interrupted=False):
        state = "interrupted" if interrupted else "not_attempted"
        self.db.execute("UPDATE outcomes SET state=?,reason='generation_aborted' WHERE state='pending'", (state,))
        self.db.execute("UPDATE outcomes SET state='storage_failed',reason='unconfirmed_storage' WHERE state='received'")
        counts = dict(self.db.execute("SELECT state,count(*) FROM outcomes GROUP BY state"))
        complete = not failed and not interrupted and all(key == "stored" for key in counts)
        self.db.execute("UPDATE metadata SET value=? WHERE key='status'", ("complete" if complete else "incomplete",))
        self.db.commit()
        return complete

    def close(self):
        self.db.close()


class LedgerStorage(Database):
    """Store a successful response once; confirm only after backend finalization."""

    def __init__(self, storage, ledger):
        self.storage, self.ledger = storage, ledger

    def insert_one(self, document):
        self.insert_many([document])

    def insert_many(self, documents):
        if not documents:
            return
        db = self.ledger.db
        pending = db.execute("SELECT ordinal,occurrence_id,source_uuid,text_hash FROM outcomes WHERE state='pending' ORDER BY ordinal LIMIT ?", (len(documents),)).fetchall()
        if len(pending) != len(documents):
            raise GenerationIncomplete("Unexpected or replayed generation response")
        decorated = []
        for document, (ordinal, occurrence, uuid, text_hash) in zip(documents, pending):
            if document.get("uuid") != uuid or digest(str(document.get("text")).encode("utf-8")) != text_hash:
                raise GenerationIncomplete("Response identity/order mismatch")
            decorated.append({**document, "occurrence_id": occurrence, "generation_id": self.ledger.generation_id})
            db.execute("UPDATE outcomes SET state='received',response_hash=? WHERE ordinal=?",
                       (document_signature(document), ordinal))
        db.commit()
        try:
            self.storage.insert_many(decorated)
        except BaseException:
            db.executemany("UPDATE outcomes SET state='storage_failed',reason='store_failure' WHERE ordinal=?",
                           ((item[0],) for item in pending))
            db.commit()
            raise
        db.executemany("UPDATE outcomes SET state='stored_pending_finalize' WHERE ordinal=?", ((item[0],) for item in pending))
        db.commit()

    def fail_request(self, count):
        self.ledger.fail_request(count)

    def finalize(self):
        db = self.ledger.db
        try:
            self.storage.finalize()
        except BaseException:
            db.execute("UPDATE outcomes SET state='storage_failed',reason='finalize_failure' WHERE state='stored_pending_finalize'")
            db.commit()
            raise
        db.execute("UPDATE outcomes SET state='stored' WHERE state='stored_pending_finalize'")
        db.commit()

    def get_documents(self):
        return self.storage.get_documents()

    def get_collected_uuids(self):
        return self.storage.get_collected_uuids()

    def test_access(self):
        return self.storage.test_access()


def run_generation(model, storage, uuids, texts, path):
    recipe = {field: getattr(model, field, None) for field in SPACE_FIELDS}
    ledger = OutcomeLedger(path, uuids, texts, recipe)
    tracked = LedgerStorage(storage, ledger)
    try:
        try:
            model.compute_embeddings(uuids=uuids, data=texts, storage=tracked)
        except BaseException as exc:
            try:
                tracked.finalize()
            finally:
                ledger.finish(failed=True, interrupted=isinstance(exc, (KeyboardInterrupt, SystemExit)))
            raise
        try:
            tracked.finalize()
        except BaseException:
            ledger.finish(failed=True)
            raise
        if not ledger.finish():
            raise GenerationIncomplete("Incomplete generation; inspect the outcome ledger before partial analysis")
        return ledger.generation_id
    finally:
        ledger.close()
