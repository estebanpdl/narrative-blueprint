<div align="center">

# 🔍 Narrative Blueprint

**AI-Assisted Narrative Analysis**

![Python](https://img.shields.io/badge/python-3.14-blue.svg)
![Active Development](https://img.shields.io/badge/status-active%20development-orange.svg)
![AI Research](https://img.shields.io/badge/AI-research-purple.svg)
![Made with Love](https://img.shields.io/badge/made%20with%20❤️-python-red.svg)

</div>

## 🚀 Overview

<div align="center">
  <img src="assets/analyzer.png" alt="Narrative Blueprint Analyzer" width="800"/>
</div>

<br>

Narrative Blueprint helps researchers describe narratives, framing, and observable text and communication patterns. It applies user-supplied TOML prompts to text records with OpenAI or Google Gemini models and stores the returned JSON documents. Separate commands compute embeddings through a provider, validate stored vectors into a local snapshot, and analyze occurrence similarities without a provider. A small CSV diagnostic remains available for compatibility.

The project is in active development. Generated labels and similarity groups are material for human review; they do not establish truth, intent, coordination, or how common a view is in a population. See the [documentation index](docs/index.md) for current command behavior and limitations.

## ✨ Key Features

### 🧠 AI-Powered Analysis
- **Multi-Provider LLM Support**: Works with OpenAI GPT and Google Gemini models
- **Multilingual Prompts**: Supply prompt instructions in English, Spanish, or another language; analytical quality needs separate evaluation for each language and task

### 📊 Research Capabilities
- **Labels from Your Prompt**: Request candidate topics, claims, or rhetorical descriptions using your chosen template
- **Stored-Vector Diagnostics**: Inspect similarity groups in a small CSV, with explicit limits and documented legacy graph behavior
- **Snapshot Validation**: Validate CSV, Parquet or SQLite vectors into an indexed disk-backed snapshot with occurrence counts, exclusions and generation receipts; see [snapshot validation](docs/snapshot-validation.md)
- **Global Similarity Analysis**: Analyze validated snapshots with exhaustive tiled threshold comparisons, all occurrence nodes, seeded Louvain, separate bridge statistics and verified CSV publication; see [global similarity](docs/global-similarity.md)

### 🔧 Technical Architecture
- **Flexible Storage**: Save blueprints to MongoDB or JSON, and embeddings to MongoDB, CSV, Parquet, or SQLite
- **Concurrent Blueprint Requests**: Process prompts with a thread pool and local pacing; this does not establish large-corpus capacity or provider quota guarantees
- **Custom Prompt Engineering**: Flexible template system for domain-specific analysis
- **Multi-format Support**: Process CSV, XLSX, and JSON input files

## 🎯 Use Cases

### Content Review
- **Media and Public Discourse**: Organize model-generated topic or claim descriptions for review against the source text
- **Research and Monitoring**: Apply a consistent prompt to selected records, then assess the outputs with a documented method
- **Similarity Exploration**: Review stored-text relationships through a validated snapshot graph, with explicit resource limits and separate counts for repeated texts and occurrences

Campaign attribution, cross-platform spread, actor intent, and policy impact require evidence and analysis beyond these outputs.

## 🛠️ Installation

### Prerequisites
- Python 3.14 (the currently qualified runtime series)
- OpenAI API key and/or Google Gemini API key for generation; none for stored-vector diagnostics
- MongoDB instance (optional — only needed when using MongoDB storage)

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd narrative-blueprint

# Install dependencies
python -m pip install .

# Inspect the installed commands without credentials
nblue --help
python -m narrative_blueprint --help

# Set up environment variables
cp config/.env.template config/.env
# Edit config/.env and add your API keys:
#   OPENAI_API_KEY=your-openai-api-key
#   GEMINI_API_KEY=your-gemini-api-key
```

See the [documentation index](docs/index.md) and [provider-free quick start](docs/quick-start.md).
The [local workflow scope](docs/local-workflow.md) collects the offline commands,
qualification evidence, compatibility notes and deferred capabilities.
The canonical commands are `nblue blueprint`, `nblue embeddings compute`,
`nblue embeddings snapshot`, and `nblue embeddings analyze`. The source launcher `python main.py` and compatibility aliases
remain supported through 1.x; see the [migration map](docs/cli-compatibility.md).
Source-only clone use requires `python -m pip install -r requirements.txt`.
The package is installed from the checkout; these instructions do not imply a
published PyPI release. Set up generation credentials only if using a provider.

## 📋 Dataset Requirements

Your narrative dataset must include the following structure:

### Required Columns/Keys
- **`uuid`**: Unique identifier for each narrative
- **`narrative`**: The text content to be analyzed

### Supported Formats
- **CSV**: UTF-8 encoded with header row
- **XLSX**: Excel format with proper column headers
- **JSON**: Array of objects or single object structure

### Example Dataset Structure
```csv
uuid,narrative
"12345","This is a sample narrative text for analysis..."
"67890","Another narrative example with different content..."
```

```json
[
  {
    "uuid": "12345",
    "narrative": "This is a sample narrative text for analysis..."
  },
  {
    "uuid": "67890",
    "narrative": "Another narrative example with different content..."
  }
]
```

## 🎨 Prompt Engineering

The tool loads your TOML system and message prompts, substitutes the source text into `${narrative}`, and sends those messages to the selected model. The template defines the requested interpretation and output fields.

### Template Structure
```toml
[system]
prompt = """
Your system-level instructions for the AI analyst...
"""

[message]
prompt = """
Analysis instructions with ${narrative} placeholder...
"""
```

### Available Templates
- **`prompt_examples/narrative_blueprint_EN.toml`**: English narrative and communication-pattern analysis
- **`prompt_examples/narrative_blueprint_ES.toml`**: Spanish narrative and communication-pattern analysis
- **Create your own**: Choose instructions and output fields suited to your evidence and research question

These examples help researchers describe topics, framing, claims and observable communication patterns in text. They do not assume a campaign or hidden intent. The `communication_patterns` field is provisional pending methodology review; it describes textual features, not verified author motives. Review the instructions before use and evaluate each language separately before comparing outputs. See [template compatibility](docs/blueprint.md#template-compatibility) before reusing an existing result destination.

### Custom Template Development
You can create domain-specific analysis by:
1. Writing your analysis framework in the system prompt (in any language)
2. Defining the desired JSON output structure
3. Customizing analysis dimensions for your specific use case
4. Adapting prompts for different languages and cultural contexts
5. Testing and refining your prompts for better results

## 🚀 Usage

The following generation commands are syntax examples that require your own input files, prompt, and provider credentials. They can incur provider charges. Model names shown are present in the packaged configuration; their presence does not verify current remote availability. For a provider-free example, use the stored-vector diagnostic below.

### JSON File Output (no MongoDB required)
```bash
python main.py blueprint \
  --model gpt-4o-mini \
  --prompt-template prompt_examples/narrative_blueprint_EN.toml \
  --narrative-path data/narratives.csv \
  --output results.json
```

### MongoDB Output
```bash
python main.py blueprint \
  --model gpt-4o-mini \
  --prompt-template prompt_examples/narrative_blueprint_EN.toml \
  --narrative-path data/narratives.csv \
  --mongo-db-name narrative-analysis \
  --mongo-collection-name results
```

### Using Google Gemini
```bash
python main.py blueprint \
  --model gemini-2.5-flash-lite \
  --prompt-template prompt_examples/narrative_blueprint_EN.toml \
  --narrative-path data/narratives.csv \
  --output results.json
```

### Limiting Sample Size
```bash
python main.py blueprint \
  --model gpt-4o-mini \
  --prompt-template custom_analysis.toml \
  --narrative-path large_dataset.xlsx \
  --sample-size 1000 \
  --output analysis_results.json
```

### Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--model` | No | `gpt-4o-mini` | LLM model to use (OpenAI or Gemini) |
| `--prompt-template` | Yes | — | Path to TOML prompt template |
| `--narrative-path` | Yes | — | Path to narrative dataset |
| `--sample-size` | No | all | Limit analysis to N narratives |
| `--output` | No | — | Path to JSON output file |
| `--mongo-db-name` | No* | — | MongoDB database name |
| `--mongo-collection-name` | No* | — | MongoDB collection name |

\* `--mongo-db-name` and `--mongo-collection-name` are required when `--output` is not provided.

### Storage Behavior

- **MongoDB**: A result callback writes each returned document as provider tasks finish. This is per-document persistence, not an all-or-nothing run transaction.
- **JSON file**: Results are held until the provider task batch returns, then appended one at a time; each append rewrites the JSON file. This is not atomic publication. UUIDs found in the loaded output are excluded from the next input selection. An interruption can leave generated results unpersisted or a write incomplete.

## Embeddings

### Analyze stored vectors without a provider

For corrected analysis, follow [global similarity analysis](docs/global-similarity.md):
build a validated snapshot, then run `nblue embeddings analyze --snapshot-dir SNAPSHOT --analysis-dir RESULTS`.
This route preserves duplicates and isolates and checks configurable graph/output
budgets. [Output interpretation](docs/analysis-outputs.md) explains the completion
manifest, assignments and bridge statistics. The older CSV diagnostic below is
retained for compatibility.

Start with the [analysis-only user guide](docs/analysis-only.md) for flag examples,
CSV requirements, output interpretation, and creating a small subset of a larger CSV.
This mode requires no API keys or MongoDB configuration.

The analysis-only entry accepts a small local CSV and performs a **diagnostic
legacy analysis**. It does not load provider credentials or compute embeddings.
Start with the synthetic fixture, using a new output directory for each run:

```bash
python main.py embeddings --analysis-only --analysis-source tests/fixtures/diagnostic/vectors.csv --declared-space synthetic/fixture-v1 --allow-legacy-source --output results/diagnostic-example
```

Expect four selected occurrences, three unique texts, one legacy community
representing two unique texts, and `Output status: diagnostic_complete`.
Inspect `selection.json`, `legacy-communities.json` and
`diagnostic-status.json`. UUIDs such as `001` stay strings. The selected
duplicate occurrences remain visible, but the legacy graph collapses their
text and drops the isolated fixture record. Its bridge-edge statistics and
batch filtering are also uncorrected. These are diagnostic results, not
complete occurrence assignments or a scalable analysis.

`--allow-legacy-source` acknowledges unknown original generation completeness.
Optional `--declared-space` records an unverified recipe note (null if omitted); it
does not verify that assertion. CSV requires `uuid`, `text` and `embedding`
(a JSON numeric array). Repeated UUIDs, invalid vectors, mixed dimensions and
conflicting reported space metadata refuse the whole run.

Useful offline checks:

```bash
python main.py embeddings --analysis-only --analysis-source tests/fixtures/diagnostic/no-edges.csv --declared-space synthetic/orthogonal-v1 --allow-legacy-source --output results/diagnostic-no-edges
python main.py embeddings --analysis-only --analysis-source tests/fixtures/diagnostic/empty.csv --declared-space synthetic/empty-v1 --allow-legacy-source --output results/diagnostic-empty
python main.py embeddings --analysis-only --analysis-source tests/fixtures/diagnostic/vectors.csv --declared-space synthetic/fixture-v1 --allow-legacy-source --max-records 3 --output results/diagnostic-refused
```

The first two complete with zero communities (two and zero selected rows).
The third exits with an error before creating output because four rows exceed
the limit. To rerun a successful example, choose a new output directory.

Defaults admit at most 100 records, 3072 dimensions, 4 MiB source bytes, 4950
possible pairs and a 64 MiB working-memory estimate. All five limits are
configurable within strict diagnostic ceilings shown in `embeddings --help`.
The working estimate is not an enforced process RSS or runtime ceiling.
The [stored-vector contract](docs/embedding-analysis-contract.md) specifies
identity, limits, diagnostic outputs and the separately versioned corrected
analysis format, which this adapter does not implement.

Tests run with provider constructors, credential loaders, `.env` opens and
network connection operations blocked:

```bash
python -m pytest tests -q
```

### Compute and store embeddings

Use `nblue embeddings compute` for generation; the flat `python main.py embeddings` examples below remain compatibility syntax. This path can contact a provider.

The compute command stores vectors in MongoDB by default. Use
`--embeddings-output` to select a local CSV, Parquet, or SQLite file instead.
The existing `-o, --output` option remains the directory for projector and
similarity-analysis files.

### Store embeddings in CSV

```bash
python main.py embeddings \
  --model text-embedding-3-small \
  --narrative-path data/narratives.csv \
  --embeddings-output results/embeddings.csv \
  --output results/analysis
```

CSV embeddings are encoded as JSON arrays in the `embedding` column.

### Store embeddings in Parquet

```bash
python main.py embeddings \
  --model text-embedding-3-small \
  --narrative-path data/narratives.csv \
  --embeddings-output results/embeddings.parquet \
  --skip-analysis
```

Parquet stores `embedding` as a native list-of-floats column and uses Zstandard
compression. Writes are finalized atomically after embedding computation.

### Store embeddings in SQLite without analysis

```bash
python main.py embeddings \
  --model gemini-embedding-001 \
  --gemini-task-type CLUSTERING \
  --narrative-path data/narratives.csv \
  --embeddings-output results/embeddings.sqlite \
  --skip-analysis
```

SQLite embeddings are stored as JSON arrays in the `embeddings.embedding`
column. Supported local database extensions are `.db`, `.sqlite`, and
`.sqlite3`.

### Gemini task types

`--gemini-task-type` applies only to `gemini-embedding-001` and accepts the
[supported Gemini task types](https://ai.google.dev/gemini-api/docs/embeddings#supported-task-types):
`SEMANTIC_SIMILARITY` (default), `CLASSIFICATION`, `CLUSTERING`,
`RETRIEVAL_DOCUMENT`, `RETRIEVAL_QUERY`, `CODE_RETRIEVAL_QUERY`,
`QUESTION_ANSWERING`, and `FACT_VERIFICATION`.

### MongoDB embedding storage

When `--embeddings-output` is omitted, both MongoDB arguments are required:

```bash
python main.py embeddings \
  --model text-embedding-3-small \
  --narrative-path data/narratives.csv \
  --mongo-db-name embeddings-db \
  --mongo-collection-name embeddings \
  --output results/analysis
```

## 📊 Output Structure

Blueprint fields depend on the chosen prompt. The following abbreviated, invented example illustrates the English template; it is not a verified finding or a fixed schema enforced by the application:

```json
{
  "uuid": "narrative-identifier",
  "content_topics": {
    "government": 0,
    "military": 0,
    "elections": 0,
    "environment": 1,
    "other": "Community gardening"
  },
  "communication_patterns": ["Comparison of planting methods", "Invitation to participate"],
  "target_audience": ["Residents explicitly addressed in the notice"],
  "intent": "The notice states that it invites residents to a gardening workshop.",
  "calls_to_action": ["Register for the workshop"],
  "key_actors_entities": ["Community Garden Association"],
  "key_claims": [
    "The workshop will compare two planting methods",
    "Registration is open to local residents"
  ]
}
```

---

**⚠️ Ethical Use Notice**: This tool is designed for legitimate intelligence analysis, academic research, and security applications. Users are responsible for ensuring compliance with applicable laws and ethical guidelines when analyzing narratives and content.
