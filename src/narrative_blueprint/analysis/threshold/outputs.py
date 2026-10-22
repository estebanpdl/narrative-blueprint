"""Streaming evidence tables, induced community statistics and validation."""

import csv
import hashlib
import io
import itertools
import os

from .contracts import AnalysisRefused
from .snapshot_input import checked_hash


HEADERS = {
    "assignments.csv": ("run_id", "occurrence_id", "source_uuid", "source_ordinal", "text_hash", "community_id", "outcome"),
    "edges.csv": ("source_occurrence_id", "target_occurrence_id", "cosine", "source_community_id", "target_community_id", "classification"),
    "communities.csv": ("community_id", "occurrence_count", "unique_text_count", "internal_edge_count", "mean_internal_edge_similarity", "incident_bridge_count"),
    "rejections.csv": ("occurrence_id", "source_uuid", "source_ordinal", "status", "stage", "reason"),
}


class Exports:
    """Account exact UTF-8 bytes before writing, including headers."""

    def __init__(self, scratch):
        self.scratch = scratch
        self.bytes = 0
        self.files = {}

    def write_csv(self, name, rows):
        path = self.scratch.directory / name
        count = 0
        hasher = hashlib.sha256()
        with path.open("xb") as stream:
            pending = bytearray()

            def flush():
                self.scratch.disk(len(pending) + 65536)
                stream.write(pending)
                pending.clear()

            for values in itertools.chain((HEADERS[name],), rows):
                buffer = io.StringIO(newline="")
                csv.writer(buffer).writerow(values)
                data = buffer.getvalue().encode("utf-8")
                self.scratch.budget.limits.check("max_record_bytes", len(data))
                self.scratch.budget.limits.check("max_export_bytes", self.bytes + len(data))
                if pending and len(pending) + len(data) > 65536:
                    flush()
                pending.extend(data)
                if len(pending) >= 65536:
                    flush()
                hasher.update(data)
                self.bytes += len(data)
                count += 1
            if pending:
                flush()
            stream.flush()
            os.fsync(stream.fileno())
        self.files[name] = {"rows": count - 1, "bytes": path.stat().st_size, "sha256": hasher.hexdigest()}


def assignment_rows(scratch, run_id):
    for row in scratch.db.execute("SELECT occurrence_id,source_uuid,source_ordinal,text_hash,community,outcome FROM nodes ORDER BY node"):
        yield (run_id, *row)


def edge_rows(scratch):
    for source, target, weight, left, right in scratch.db.execute('''
        SELECT a.occurrence_id,b.occurrence_id,e.weight,a.community,b.community
        FROM edges e JOIN nodes a ON a.node=e.i JOIN nodes b ON b.node=e.j ORDER BY e.i,e.j
    '''):
        yield source, target, format(weight, ".17g"), left, right, "internal" if left == right else "bridge"


def rejection_rows(snapshot):
    for row in snapshot.execute("SELECT occurrence_id,source_uuid,source_ordinal,status,reason FROM records WHERE status!='valid' ORDER BY ordinal"):
        yield (*row[:4], "validation", row[4])


def community_rows(scratch):
    yield from scratch.db.execute("SELECT community,occurrences,unique_texts,internal_edges,mean_internal,incident_bridges FROM communities ORDER BY community")


def write_tables(scratch, snapshot, run_id, result):
    if scratch.db.execute("SELECT count(*) FROM nodes WHERE community IS NULL OR outcome IS NULL").fetchone()[0]:
        raise AnalysisRefused("assignment_missing")
    exports = Exports(scratch)
    scratch.db.execute('''CREATE TABLE communities (community INTEGER PRIMARY KEY,
        occurrences INTEGER, unique_texts INTEGER, internal_edges INTEGER,
        mean_internal REAL, incident_bridges INTEGER)''')
    scratch.db.execute("CREATE INDEX nodes_community_text ON nodes(community,text_hash)")
    counts = list(scratch.db.execute("SELECT community,count(*),count(DISTINCT text_hash) FROM nodes GROUP BY community ORDER BY community"))
    # One edge traversal computes internal statistics and bridge incidence while
    # emitting each retained edge exactly once. No text/vector payload on edges.
    stats = {community: [0, 0.0, 0] for community, _, _ in counts}
    totals = {"internal_edges": 0, "bridge_edges": 0}

    def annotated_edges():
        for row in edge_rows(scratch):
            _, _, weight, left, right, kind = row
            totals[kind + "_edges"] += 1
            if kind == "internal":
                stats[left][0] += 1
                stats[left][1] += float(weight)
            else:
                stats[left][2] += 1
                stats[right][2] += 1
            yield row

    exports.write_csv("assignments.csv", assignment_rows(scratch, run_id))
    exports.write_csv("edges.csv", annotated_edges())
    for community, occurrences, unique_texts in counts:
        internal, weight_sum, bridges = stats[community]
        scratch.db.execute("INSERT INTO communities VALUES (?,?,?,?,?,?)",
                           (community, occurrences, unique_texts, internal,
                            weight_sum / internal if internal else None, bridges))
    scratch.db.commit()
    exports.write_csv("communities.csv", community_rows(scratch))
    exports.write_csv("rejections.csv", rejection_rows(snapshot))
    if sum(totals.values()) != result["edges"]:
        raise AnalysisRefused("edge_counts")
    return exports, totals


def validate_tables(exports, snapshot, run_id, result):
    """Re-read every output and compare its source joins, rows and checksum."""
    scratch = exports.scratch
    generators = {"assignments.csv": assignment_rows(scratch, run_id),
                  "edges.csv": edge_rows(scratch), "communities.csv": community_rows(scratch),
                  "rejections.csv": rejection_rows(snapshot)}
    expected_counts = {"assignments.csv": result["nodes"], "edges.csv": result["edges"],
                       "communities.csv": result["communities"]}
    sentinel = object()
    for name, expected in generators.items():
        path = scratch.directory / name
        budget = scratch.budget
        if checked_hash(path, budget) != exports.files[name]["sha256"]:
            raise AnalysisRefused("output_checksum")
        count = 0
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            if tuple(next(reader)) != HEADERS[name]:
                raise AnalysisRefused("output_schema")
            for actual, row in itertools.zip_longest(reader, expected, fillvalue=sentinel):
                if actual is sentinel or row is sentinel or actual != ["" if value is None else str(value) for value in row]:
                    raise AnalysisRefused("output_join")
                count += 1
                if count % 256 == 0:
                    budget.tick()
        budget.tick()
        if count != exports.files[name]["rows"] or count != expected_counts.get(name, count):
            raise AnalysisRefused("output_counts")
    selected = snapshot.execute("SELECT count(*) FROM records").fetchone()[0]
    if exports.files["assignments.csv"]["rows"] + exports.files["rejections.csv"]["rows"] != selected:
        raise AnalysisRefused("selection_counts")
