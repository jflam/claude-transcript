# Claude Transcript Packaging Guide

## Step-by-Step Instructions for Packaging as a Pip Package

This guide shows how to package `claude_transcript.py` as a proper Python package that can be installed with `uv` as a tool and run as `claude_transcript <path>`.

### Step 1: Create Package Structure

```
claude-transcript/
├── src/
│   └── claude_transcript/
│       ├── __init__.py
│       └── main.py
├── pyproject.toml
├── README.md
└── LICENSE
```

### Step 2: Move and Prepare Code

1. **Create the package directory**:
   ```bash
   mkdir -p src/claude_transcript
   ```

2. **Move the script**:
   ```bash
   cp claude_transcript.py src/claude_transcript/main.py
   ```

3. **Create `__init__.py`**:
   ```python
   """Claude Transcript - Convert Claude Code JSONL sessions to readable markdown."""
   __version__ = "1.0.0"
   ```

4. **Update `main.py`** - Add a simple entry point function at the end:
   ```python
   def cli():
       """Entry point for the CLI."""
       sys.exit(main())
   
   if __name__ == '__main__':
       cli()
   ```

### Step 3: Create `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "claude-transcript"
version = "1.0.0"
description = "Convert Claude Code JSONL sessions to readable markdown transcripts"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "Claude Code Community", email = "noreply@anthropic.com"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Documentation",
    "Topic :: Text Processing :: Markup :: Markdown",
]
requires-python = ">=3.8"
dependencies = []

[project.urls]
Homepage = "https://github.com/your-username/claude-transcript"
Repository = "https://github.com/your-username/claude-transcript"
Issues = "https://github.com/your-username/claude-transcript/issues"

[project.scripts]
claude-transcript = "claude_transcript.main:cli"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-dir]
"" = "src"
```

### Step 4: Create Additional Files

1. **README.md**:
   ```markdown
   # Claude Transcript
   
   Convert Claude Code JSONL session files to readable markdown transcripts.
   
   ## Installation
   
   ```bash
   uv tool install claude-transcript
   ```
   
   ## Usage
   
   ```bash
   claude-transcript session.jsonl
   claude-transcript session.jsonl -o custom_name.md
   claude-transcript session.jsonl --upload-gist
   ```
   ```

2. **LICENSE** (MIT License):
   ```
   MIT License
   
   Copyright (c) 2024 Claude Code Community
   
   Permission is hereby granted, free of charge, to any person obtaining a copy...
   ```

### Step 5: Build and Test Locally

1. **Install build tools**:
   ```bash
   uv add --dev build twine
   ```

2. **Build the package**:
   ```bash
   uv run python -m build
   ```
   This creates `dist/claude_transcript-1.0.0.tar.gz` and `dist/claude_transcript-1.0.0-py3-none-any.whl`

3. **Test local installation**:
   ```bash
   uv tool install ./dist/claude_transcript-1.0.0-py3-none-any.whl
   claude-transcript --help
   ```

### Step 6: Publish to PyPI

#### Prerequisites

1. **Create PyPI accounts**:
   - Main PyPI: https://pypi.org/account/register/
   - Test PyPI (recommended for testing): https://test.pypi.org/account/register/

2. **Install upload tools**:
   ```bash
   uv add --dev twine
   ```

#### Upload Process

1. **Clean and rebuild** (ensure fresh build):
   ```bash
   rm -rf dist/ build/ src/*.egg-info/
   uv build
   ```

2. **Upload to Test PyPI first** (recommended):
   ```bash
   uv run twine upload --repository testpypi dist/*
   ```
   
   You'll need:
   - Username: Your Test PyPI username  
   - Password: Your Test PyPI password (or API token)

3. **Test installation from Test PyPI**:
   ```bash
   uv tool install --index-url https://test.pypi.org/simple/ claude-transcript
   claude-transcript --help
   ```

4. **Upload to production PyPI** (after testing):
   ```bash
   uv run twine upload dist/*
   ```

#### Using API Tokens (Recommended)

For better security, use API tokens:

1. **Create API tokens**:
   - PyPI: https://pypi.org/manage/account/token/
   - Test PyPI: https://test.pypi.org/manage/account/token/

2. **Upload with tokens**:
   ```bash
   # Test PyPI
   uv run twine upload --repository testpypi dist/* --username __token__ --password pypi-your-test-token

   # Production PyPI
   uv run twine upload dist/* --username __token__ --password pypi-your-production-token
   ```

#### Configure ~/.pypirc (Optional)

Create `~/.pypirc` for easier uploads:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-production-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-token-here
```

Then simply run:
```bash
uv run twine upload --repository testpypi dist/*  # For test
uv run twine upload dist/*                        # For production
```

### Step 7: Install and Use

Once published, anyone can install and use it:

```bash
# Install as a tool
uv tool install claude-transcript

# Use directly
claude-transcript session.jsonl

# Or install in current environment
uv add claude-transcript
```

### Step 8: Version Management for Updates

For subsequent releases:

1. **Update version numbers**:
   - In `src/claude_transcript/__init__.py`: `__version__ = "1.1.0"`
   - In `pyproject.toml`: `version = "1.1.0"`

2. **Rebuild and upload**:
   ```bash
   rm -rf dist/ build/ src/*.egg-info/
   uv build
   uv run twine upload --repository testpypi dist/*  # Test first
   uv run twine upload dist/*                        # Then production
   ```

3. **Users can upgrade**:
   ```bash
   uv tool upgrade claude-transcript
   ```

## Alternative: Quick Distribution Options

For simpler distribution without full PyPI publishing:

### 1. Direct uv execution (Current approach):
```bash
# Run directly from local file
uv run claude_transcript.py session.jsonl

# Or from GitHub/gist
uv run https://github.com/user/repo/claude_transcript.py session.jsonl
```

### 2. GitHub Gist sharing:
```bash
# Upload script to gist
gh gist create --public claude_transcript.py

# Others can run directly:
uv run https://gist.githubusercontent.com/user/gist-id/raw/claude_transcript.py session.jsonl
```

## Benefits of Full Package Approach

- **Professional CLI**: Simple command `claude-transcript <path>`
- **Tool isolation**: uv manages dependencies automatically  
- **Easy updates**: `uv tool upgrade claude-transcript`
- **Standard compliant**: Uses modern Python packaging standards
- **Cross-platform**: Works on Windows, macOS, Linux