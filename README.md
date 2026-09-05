<div align="center">

# 🔍 Narrative Blueprint

**AI-Assisted Narrative Analysis**

![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Active Development](https://img.shields.io/badge/status-active%20development-orange.svg)
![Open Source](https://img.shields.io/badge/open%20source-MIT-blue.svg)
![AI Research](https://img.shields.io/badge/AI-research-purple.svg)
[![Research](https://img.shields.io/badge/Research-Narrative%20Analysis-red?style=flat&logo=academia&logoColor=white)]()
![Made with Love](https://img.shields.io/badge/made%20with%20❤️-python-red.svg)

</div>

## 🚀 Overview

<div align="center">
  <img src="assets/analyzer.png" alt="Narrative Blueprint Analyzer" width="800"/>
</div>

<br>

Narrative Blueprint is an AI-driven analysis framework that uses LLMs to analyze narratives, content patterns, and information structures. The tool is particularly powerful for information warfare and disinformation analysis, but its flexibility makes it valuable for any domain requiring structured narrative intelligence.

## ✨ Key Features

### 🧠 AI-Powered Analysis
- **Multi-Provider LLM Support**: Works with OpenAI GPT and Google Gemini models
- **Multilingual Prompt Support**: Create analysis instructions in any language - English, Spanish, or any language of your choice

### 📊 Intelligence Capabilities
- **Narrative Pattern Recognition**: Identify recurring themes, tactics, and messaging strategies
- **Content Categorization**: Systematically classify narratives across multiple dimensions

### 🔧 Technical Architecture
- **Flexible Storage**: Save blueprints to MongoDB or JSON, and embeddings to MongoDB, CSV, Parquet, or SQLite
- **Parallel Processing**: Efficient batch analysis of large narrative datasets
- **Custom Prompt Engineering**: Flexible template system for domain-specific analysis
- **Multi-format Support**: Process CSV, XLSX, and JSON input files

## 🎯 Use Cases

### Information Warfare Analysis
- **Disinformation Campaign Detection**: Identify coordinated inauthentic behavior patterns
- **Propaganda Analysis**: Decode persuasion techniques and messaging strategies
- **Social Media Intelligence**: Analyze narrative spread across platforms
- **Threat Actor Profiling**: Characterize adversarial communication patterns

### Content Intelligence
- **Media Monitoring**: Track narrative evolution across news cycles
- **Policy Impact Assessment**: Analyze public discourse around policy changes
- **Crisis Communication**: Track narrative dynamics during critical events

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- OpenAI API key and/or Google Gemini API key
- MongoDB instance (optional — only needed when using MongoDB storage)

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd narrative-blueprint

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp config/.env.template config/.env
# Edit config/.env and add your API keys:
#   OPENAI_API_KEY=your-openai-api-key
#   GEMINI_API_KEY=your-gemini-api-key
```

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

The tool reads and executes custom TOML prompt templates that you create. You define how the AI analyzes your narratives through these templates.

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
- **`prompt_examples/narrative_blueprint_EN.toml`**: English disinformation analysis
- **`prompt_examples/narrative_blueprint_ES.toml`**: Spanish disinformation analysis
- **Create your own**: Templates can be developed in any language for global applicability

### Custom Template Development
You can create domain-specific analysis by:
1. Writing your analysis framework in the system prompt (in any language)
2. Defining the desired JSON output structure
3. Customizing analysis dimensions for your specific use case
4. Adapting prompts for different languages and cultural contexts
5. Testing and refining your prompts for better results

## 🚀 Usage

### JSON File Output (no MongoDB required)
```bash
python main.py \
  --model gpt-4o-mini \
  --prompt-template prompt_examples/narrative_blueprint_EN.toml \
  --narrative-path data/narratives.csv \
  --output results.json
```

### MongoDB Output
```bash
python main.py \
  --model gpt-4o-mini \
  --prompt-template prompt_examples/narrative_blueprint_EN.toml \
  --narrative-path data/narratives.csv \
  --mongo-db-name narrative-analysis \
  --mongo-collection-name results
```

### Using Google Gemini
```bash
python main.py \
  --model gemini-2.5-flash-preview-05-20 \
  --prompt-template prompt_examples/narrative_blueprint_EN.toml \
  --narrative-path data/narratives.csv \
  --output results.json
```

### Limiting Sample Size
```bash
python main.py \
  --model gpt-4o \
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

- **MongoDB**: Each result is stored in real time as it is processed. This provides resilience against interruptions — completed results are persisted immediately.
- **JSON file**: Results are written to the file after all processing completes. If the output file already exists, previously processed UUIDs are skipped (deduplication).

## Embeddings

The `embeddings` command stores vectors in MongoDB by default. Use
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

Results are stored as JSON documents with structured analysis:

```json
{
  "uuid": "narrative-identifier",
  "content_topics": {
    "government": 1,
    "military": 0,
    "elections": 1,
    "conspiracy": 1,
    "other": "Climate change discussion"
  },
  "disinformation_tactic": ["fear-mongering", "false dichotomy"],
  "target_audience": ["elderly voters", "rural communities"],
  "intent": "Influence voter behavior through manufactured controversy",
  "calls_to_action": ["Vote against incumbent", "Share this message"],
  "key_actors_entities": ["Political Candidate X", "News Organization Y"],
  "key_claims": [
    "Government is hiding climate data",
    "Opposition candidate supports dangerous policies"
  ]
}
```

---

**⚠️ Ethical Use Notice**: This tool is designed for legitimate intelligence analysis, academic research, and security applications. Users are responsible for ensuring compliance with applicable laws and ethical guidelines when analyzing narratives and content.
