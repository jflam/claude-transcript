# Claude Transcript

Convert Claude Code JSONL session files to readable markdown transcripts and share them with your friends. 

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