# Claude Transcript

Convert Claude Code JSONL session files to readable markdown transcripts with the exact same output as the physical-sessions command.

## Installation

### Install as a tool (recommended)

```bash
uv tool install claude-transcript
```

### Install in current environment

```bash
uv add claude-transcript
# or
pip install claude-transcript
```

## Usage

```bash
# Basic usage
claude-transcript session.jsonl

# Custom output filename
claude-transcript session.jsonl -o custom_name.md

# Upload to GitHub Gist after generation
claude-transcript session.jsonl --upload-gist

# Show help
claude-transcript --help
```

## Claude Code JSONL Files

Claude Code automatically saves all conversations locally in JSONL (JSON Lines) format. Each session creates a file containing structured data about your interaction:

- **Storage Location**: Conversations are stored locally on your machine with full message history
- **File Format**: JSONL files contain one JSON object per line, capturing messages, tool operations, metadata, and timing information
- **Content Types**: Files include user messages, assistant responses, tool executions (file edits, searches, bash commands), sidechains for parallel processing, and session metadata
- **Data Retention**: While local files persist indefinitely, Anthropic only retains user feedback transcripts for 30 days for debugging and improvement purposes

### JSONL Structure

Each line in a Claude Code JSONL file represents a different type of event or operation:
- Message exchanges between user and assistant
- Tool operations and their results
- Timing and cost information
- Parallel task execution data from sidechains

This structured format allows for comprehensive reconstruction of the entire conversation flow, which this tool converts into readable markdown transcripts.

## Features

- **Zero dependencies**: Pure Python with no external dependencies
- **Comprehensive parsing**: Handles all JSONL entry types including tool operations, sidechains, and timing information
- **GitHub Gist integration**: Optional upload to share transcripts easily
- **Tool operations display**: Shows detailed information about file edits, searches, and other actions taken during the session

## Example Output

The tool generates clean, readable markdown transcripts that include:

- Session metadata and timing information  
- Conversational turns with user requests and assistant responses
- Detailed tool operation logs (file edits, searches, bash commands, etc.)
- Parallel task execution details from sidechains
- Professional formatting suitable for documentation or sharing

## Requirements

- Python 3.8 or higher
- No external dependencies required
- Optional: GitHub CLI (`gh`) for gist upload functionality

## Development

This tool is built as a standalone script with PEP 723 inline dependencies, making it easy to run directly with `uv run` or package as a proper Python package.

## License

MIT License - see LICENSE file for details.