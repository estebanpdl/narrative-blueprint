<div align="center">

# 🔍 Narrative Blueprint

**AI-Assisted Narrative Analysis**

![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-green.svg)
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
- **LLM Integration**: Seamlessly works with OpenAI's GPT models for sophisticated narrative understanding. New models and providers will be added.
- **Multilingual Prompt Support**: Create analysis instructions in any language - English, Spanish, or any language of your choice

### 📊 Intelligence Capabilities
- **Narrative Pattern Recognition**: Identify recurring themes, tactics, and messaging strategies
- **Content Categorization**: Systematically classify narratives across multiple dimensions
- **Threat Intelligence**: Extract actionable insights for information security applications
- **Disinformation Detection**: Specialized prompts for identifying manipulation tactics

### 🔧 Technical Architecture
- **MongoDB Integration**: Scalable storage for analysis results and metadata
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
- MongoDB instance.
    - Currently. Local support only.
- OpenAI API key

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd narrative-blueprint

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export OPENAI_API_KEY="your-openai-api-key"
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

### Basic Analysis
```bash
python main.py \
  --model gpt-4o-mini \
  --prompt-template prompt_examples/narrative_blueprint_EN.toml \
  --narrative-path data/narratives.csv \
  --mongo-db-name narrative-analysis \
  --mongo-collection-name results
```

### Advanced Options
```bash
python main.py \
  --model gpt-4o \
  --prompt-template custom_analysis.toml \
  --narrative-path large_dataset.xlsx \
  --sample-size 1000 \
  --mongo-db-name intelligence-db \
  --mongo-collection-name campaign-analysis
```

### Command-Line Arguments
- `--model`: OpenAI model selection (default: gpt-4o-mini)
- `--prompt-template`: Path to TOML prompt template (required)
- `--narrative-path`: Path to narrative dataset (required)
- `--sample-size`: Limit analysis to N narratives
- `--mongo-db-name`: MongoDB database name (required)
- `--mongo-collection-name`: MongoDB collection name (required)

## 📊 Output Structure

Results are stored in MongoDB as JSON documents with structured analysis:

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

## 🔒 Information Threat Intelligence

### Specialized Analysis Dimensions
- **Tactic Classification**: Identify specific disinformation techniques
- **Target Audience Profiling**: Understand intended recipients
- **Intent Recognition**: Decode underlying objectives
- **Actor Attribution**: Link narratives to potential sources
- **Claim Verification**: Extract testable assertions

### Intelligence Reporting
The tool generates structured intelligence reports suitable for:
- **Threat Assessment**: Understanding adversarial capabilities
- **Campaign Tracking**: Monitoring information operations over time
- **Attribution Analysis**: Connecting narratives to threat actors
- **Impact Assessment**: Measuring narrative reach and effectiveness

## 🔧 Development Status

**This tool is actively under development.** Upcoming enhancements include:

- **Additional LLM Providers**: Anthropic Claude, Google Gemini integration
- **Advanced Analytics**: Statistical analysis and visualization components
- **Enhanced Prompt Library**: Domain-specific templates for various use cases
- **API Interface**: RESTful API for integration with other tools
- **Dashboard Interface**: Web-based analysis and visualization

## 🤝 Contributing

We encourage contributions, especially:
- **Custom Prompt Templates**: Share domain-specific analysis frameworks
- **Dataset Examples**: Provide anonymized sample datasets
- **Analysis Techniques**: Contribute novel analytical approaches
- **Documentation**: Improve setup guides and use case examples

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OpenAI for providing the LLM capabilities
- MongoDB for scalable data storage
- The information security community for inspiration and use cases

---

**⚠️ Ethical Use Notice**: This tool is designed for legitimate intelligence analysis, academic research, and security applications. Users are responsible for ensuring compliance with applicable laws and ethical guidelines when analyzing narratives and content.
