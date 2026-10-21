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
availability. The supplied prompt examples assume a suspected disinformation
context and ask for inferred tactics, audience, and intent. Provider output does
not verify that premise, a claim's truth, or the author's intent.
