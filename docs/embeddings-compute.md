# nblue embeddings compute

Generate vectors and store them. By default, computation is followed by the
legacy projector/similarity/Excel workflow over the current generation. `--skip-analysis`
stops after vector storage. This command can make paid provider requests and
does not run blueprint generation.

| Group | Option | Default / behavior |
|---|---|---|
| Input | `--input FILE` (alias `--narrative-path`) | Required CSV/XLSX/JSON with `uuid` and `narrative` |
| Input | `--max-input-bytes N` | 268435456; whole-file admission before loading |
| Input | `--max-input-records N` | 1000000; row cap after loading |
| Receipt | `--generation-ledger FILE` | New SQLite receipt; default unique file beside vector destination |
| Provider | `--model MODEL` | `text-embedding-3-small` |
| Provider | `--gemini-task-type TYPE` | Gemini only; `SEMANTIC_SIMILARITY`; case normalized to uppercase |
| Vector destination | `--vectors-file FILE` (aliases `--embeddings-output`, `--embedding-output`) | Local `.csv`, `.parquet`, `.db`, `.sqlite`, `.sqlite3`; no default |
| Vector destination | `--mongo-db-name NAME` | Required with collection when no vector file |
| Vector destination | `--mongo-collection-name NAME` | Required with database when no vector file |
| Analysis output | `--analysis-dir DIRECTORY` (aliases `-o`, `--output`) | Required unless skipping analysis |
| Analysis output | `--threshold SCORE` | `0.75`; legacy compute behavior is retained |
| Mode | `--skip-analysis` | Off; when present compute/store only |
| Help | `-h`, `--help` | Show help without provider setup |

Model choices: `text-embedding-3-small`, `text-embedding-3-large`,
`text-embedding-ada-002`, `gemini-embedding-001`. Gemini task choices:
`SEMANTIC_SIMILARITY`, `CLASSIFICATION`, `CLUSTERING`, `RETRIEVAL_DOCUMENT`,
`RETRIEVAL_QUERY`, `CODE_RETRIEVAL_QUERY`, `QUESTION_ANSWERING`, `FACT_VERIFICATION`.
Supplying the task option with an OpenAI model is an error, even if it equals
the Gemini default. Model choices do not guarantee remote availability.

A vector file conflicts with either Mongo destination flag. Without a file,
both Mongo names are required. `--analysis-dir` never selects the vector file.
Stored-vector source/provenance/diagnostic-limit options belong to analyze and
are rejected here. An analysis directory supplied alongside `--skip-analysis`
is accepted but is not used to produce analysis files.

Provider-command syntax examples, requiring a synthetic input and configured
provider before execution:

```bash
nblue embeddings compute --input text.csv --vectors-file vectors.csv --skip-analysis
python main.py embeddings --narrative-path text.csv --embedding-output vectors.csv --skip-analysis
nblue embeddings compute --input text.csv --vectors-file vectors.csv --analysis-dir results
python main.py embeddings --narrative-path text.csv --embeddings-output vectors.csv --output results
```

The combined path still reads the whole chosen store through its compatibility
API, but retains only current-generation rows for analysis after a complete
outcome receipt. This is not a scalable graph workflow. Its legacy graph
can lose cross-block pairs and isolates, collapse duplicate texts and count
bridge edges in multiple communities. Projector and vector outputs may exist
before graph failure. The command does not add a spend cap or an enforced memory
ceiling. Provider exhaustion and storage errors now propagate; storage failures
never retry a successful provider response. See [snapshot validation](snapshot-validation.md)
for receipt states, partial generation, input-memory limits and offline validation.
