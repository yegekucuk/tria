# tria
![Python Version](https://img.shields.io/badge/python%20version-%3E%3D3.8-blue)
[![PyPi Package](https://img.shields.io/badge/pypi%20package-live-green)](https://pypi.org/project/git2mind/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/git2mind?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=GREEN&left_text=total%20downloads)](https://pepy.tech/projects/git2mind)

**Turn Python repositories into AI-friendly format (.md / .json / .xml / .toon)**

tria scans a git repository, analyzes commits, branches, and contributors, extracts and chunks files intelligently, and produces summaries that are ready for LLM consumption. Perfect for onboarding and documentation generation.

## 🚀 Features

- ✅ Basic CLI with essential flags
- ✅ Local repository scanning
- ✅ Create project structure tree
- ✅ Analyze commits, branches and contributors
- ✅ Exclude binary files and common ignore patterns, default gitignore file support & custom exclusions
- ✅ Python, Markdown, Dockerfile and License parsers
- ✅ Simple line-based chunking
- ✅ Multiple output formats
- ✅ [PyPI package (git2mind)](https://pypi.org/project/git2mind/)

## 📦 Installation

```bash
# Install from PyPI
pip install tria

# or install from source
git clone https://github.com/yegekucuk/tria.git
pip install -e tria
```

## 🎯 Usage

### Basic Usage

```bash
# Generate summary of current directory (TOON by default)
tria .

# Generate Markdown summary (Better for human reading)
tria . -f md

# Include git history
tria . --git-history

# Specify the name of output file (gitignore is used by default)
tria /path/to/repo -o summary.md

# If you want to ignore .gitignore and include all files, disable it:
tria /path/to/repo -o summary.md --no-gitignore

# Exclude specific patterns
tria ./my-repo --exclude "tests" --exclude "*.log" --format md --output summary.md

# Verbose output with custom chunk size
tria . --verbose --chunk-size 100 --format json
```

### Command Line Options

```
Usage: tria PATH [OPTIONS]

Options:
  -f, --format [toon|md|json|xml]    Output format (default: toon)
  -o, --output PATH                  Output file path (default: ./tria_output.[toon|md|json|xml])
  --exclude PATTERN                  Exclude path pattern (can be repeated)
  --no-gitignore                     Do not use .gitignore to exclude files
  --git-history                      Include git history (commits, contributors). Disabled by default
  --git-commits INT                  Number of recent commits to include (default: 20)
  --chunk-size INT                   Lines per chunk (default: 50)
  --max-files INT                    Max files to process (default: 1000)
  --dry-run                          Do everything except writing output
  -v, --verbose                      Verbose logging
  -h, --help                         Show help message
```

## 📋 Default Exclusions

The following patterns are excluded by default:
- `*.pyc`, `__pycache__`
- `.git`, `.venv`, `venv`
- `node_modules`, `dist`, `build`
- `*.egg-info`
- Binary files
- Files larger than 100KB

## 🤝 Use Cases

- **Token-Efficient LLM Input** - Use TOON format for maximum efficiency with language models
- **Documentation Generation** - Create automatic project overviews
- **Onboarding** - Help new team members understand codebases
- **Project Auditing** - Quick overview of project structure and content

## 📝 License

- Author: Yunus Ege Küçük
- MIT License - see [LICENSE](LICENSE) file for details
