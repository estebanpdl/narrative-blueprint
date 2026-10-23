# nblue blueprint

Generate structured blueprints from narrative text using an explicit TOML prompt
and an OpenAI or Gemini model. This command can make paid provider requests.
It does not compute embeddings or run similarity analysis.

| Group | Option | Default / behavior |
|---|---|---|
| Input | `--input FILE` (alias `--narrative-path`) | Required CSV/XLSX/JSON with `uuid` and `narrative` |
| Input | `--prompt-template TOML` | Required explicit path; `[system]` and `[message]` each contain `prompt`; message uses `${narrative}` |
| Input | `--sample-size N` | Omitted or zero: all rows; positive: first N; negative retains legacy Python prefix slicing |
| Provider | `--model MODEL` | `gpt-4o-mini`; must occur in the packaged model-limit configuration |
| Result destination | `--result-file JSON` (alias `--output`) | Local JSON file; no default |
| Result destination | `--mongo-db-name NAME` | Required with collection if no local result file |
| Result destination | `--mongo-collection-name NAME` | Required with database if no local result file |
| Help | `-h`, `--help` | Show help without provider setup |

If a local result file and Mongo options are supplied, the local file wins, as
in the original command. Without a local file, both Mongo names are required.
Mongo uses the existing localhost connection; the flags are destination names,
not credentials. Explicit paths are relative to the current working directory.

These are provider-command syntax examples, not offline demonstrations. Supply
your own synthetic `text.csv`, prompt and configured provider before executing:

```bash
nblue blueprint --input text.csv --prompt-template prompt.toml --sample-size 1 --result-file blueprint.json
python main.py blueprint --narrative-path text.csv --prompt-template prompt.toml --sample-size 1 --output blueprint.json
```

There is no CLI cost ceiling or dry-run mode. A sample count is not a spend cap.
Model configuration lists software defaults, not guaranteed current provider
availability. The supplied English and Spanish examples describe topics, framing,
claims and observable text and communication patterns for researchers. They do
not assume a campaign or hidden intent. Empty lists and empty strings are allowed
when the text does not support a requested observation. Provider output remains
material for human review; it does not verify truth, coordination or author intent.

## Template compatibility

`communication_patterns` is a **provisional** example-template field for observed
features such as comparison, repetition, quotation and explicit appeals. Its name
and meaning may change after methodology review. The remaining topic categories
are examples, not an exhaustive or validated taxonomy. The `neutral` topic flag
describes everyday topics outside the named categories; it is not a truth or
author-intent judgment. Audience and purpose should be reported only when expressed
in the text. Evaluate English and Spanish outputs independently; matching keys do
not establish equivalent analytical quality.

Older outputs may contain `disinformation_tactic`. That historical field is not
equivalent to the provisional field. No application code reads or validates that
specific key: the provider clients parse JSON, attach `uuid`, and pass the result
to storage. The application does not enforce the example fields or these prose
instructions as an output schema. Existing result files are not renamed,
converted or reinterpreted by this template update; downstream consumers that
expect particular keys must handle the chosen template explicitly.

Blueprint resume excludes UUIDs already present in the destination, regardless
of prompt changes. Use a **new result file or collection** when changing templates;
reusing one can skip old UUIDs and mix differently shaped results. Keep a copy of
the exact template with each run. Automatic template/schema versioning, recipe-aware
blueprint resume and legacy adapters remain deferred.
