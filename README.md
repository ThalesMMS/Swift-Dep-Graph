# Swift Dependency Analyzer

[![Python](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Swift Dependency Analyzer is a lightweight Python tool for inspecting and visualizing dependencies in iOS and macOS codebases that mix Objective-C, Objective-C++, and Swift. It produces dependency graphs with labeled edges that describe symbol usage and derives minimal file sets via transitive closure.

## Current Status

Version 2.0 introduces a modular architecture and replaces the earlier monolithic script. Core features are implemented and exercised by automated tests.

## Features

- Multi-language support for Objective-C (.m, .h), Objective-C++ (.mm, .hh), and Swift (.swift)
- Project root detection from any file inside an Xcode project
- Shallow analysis mode that focuses on referenced symbols
- Dependency edges annotated with method and type usage
- Automatic transitive closure for individual files
- Export formats: JSON, DOT (Graphviz), Mermaid, and CSV
- Pure Python implementation with no third-party runtime dependencies
- Built-in synthetic test project with cycles, orphans, and deep dependency chains
- Ignore rules for directories such as Pods, .build, or Carthage
- Cycle detection, orphan detection, shortest path queries, and other advanced reports
- Caching layer tuned for large repositories
- Extensible architecture separating parsing, graph construction, and output formatting

## Installation

```bash
git clone https://github.com/yourusername/Swift-Dependency-Analyzer.git
cd Swift-Dependency-Analyzer
python3 --version  # Requires Python 3.6 or newer
```

## Usage

### Quick Start with the Test Project

```bash
python3 swift_dep_analyzer.py --test
python3 swift_dep_analyzer.py test_project
python3 swift_dep_analyzer.py test_project --ignore Pods --detect-cycles
```

### Basic Analysis

```bash
python3 swift_dep_analyzer.py /path/to/project/Sources/MyViewController.swift
python3 swift_dep_analyzer.py /path/to/MyFile.swift --no-closure
python3 swift_dep_analyzer.py /path/to/xcode/project
python3 swift_dep_analyzer.py /path/to/project --extended
python3 swift_dep_analyzer.py /path/to/project --ignore Pods --ignore .build
```

### Transitive Closure

```bash
python3 swift_dep_analyzer.py /path/to/MyFile.swift
python3 swift_dep_analyzer.py /path/to/MyFile.swift --include-modules
python3 swift_dep_analyzer.py /path/to/MyFile.swift --direct-deps-only
python3 swift_dep_analyzer.py /path/to/MyFile.swift --extended
```

### Advanced Analysis

```bash
python3 swift_dep_analyzer.py /path/to/project --detect-cycles
python3 swift_dep_analyzer.py /path/to/project --find-orphans
python3 swift_dep_analyzer.py /path/to/FileA.swift --showPath FileB.swift
python3 swift_dep_analyzer.py /path/to/project --mermaid --csv
python3 swift_dep_analyzer.py /path/to/project --no-cache
python3 swift_dep_analyzer.py --clear
```

### Custom Options

```bash
python3 swift_dep_analyzer.py /path/to/project --output-dir ./analysis
python3 swift_dep_analyzer.py /path/to/project --config .swiftdeprc
```

### Visualizing Graphs

```bash
dot -Tpdf output/project_name/graph.dot -o dependencies.pdf
dot -Tpng output/project_name/graph.dot -o dependencies.png
dot -Tsvg output/project_name/graph.dot -o dependencies.svg
```

## Output Files

Artifacts are written to `output/<project_or_file_name>/` by default.

| File | Description |
|------|-------------|
| `graph.json` | Complete dependency graph with labeled edges |
| `graph.dot` | Graphviz representation of the dependency graph |
| `graph.mmd` | Mermaid diagram (generated with `--mermaid`) |
| `graph.csv` | Dependency relationships in CSV format (generated with `--csv`) |
| `metrics.csv` | Complexity metrics (generated with `--csv`) |
| `closure_*.txt` | Transitive closure results for individual files |
| `cycles.txt` | List of detected dependency cycles |
| `orphans.txt` | Files not referenced by other files |
| `path_*.txt` | Paths between files returned by `--showPath` |

## Architecture Overview

### Modular Design (v2.0)

```
swift_dependency_analyzer/
├── parsers/             # Language parsers
│   ├── base_parser.py   # Shared parsing abstractions
│   ├── objc_parser.py   # Objective-C and Objective-C++ support
│   └── swift_parser.py  # Swift support
├── graph/               # Graph construction and analysis
│   ├── builder.py       # Graph builder
│   └── analyzer.py      # Cycle detection, paths, metrics
├── output/              # Output formatting (JSON, DOT, etc.)
├── utils/               # File, cache, and configuration helpers
└── test_generator/      # Synthetic project generator
```

### Processing Pipeline

1. Symbol indexing scans source files for declarations.
2. Dependency detection gathers imports, symbol usage, and bridging header information.
3. Graph construction produces a directed graph with labeled edges and supports transitive closure queries.

## Use Cases

- Code review preparation and impact analysis
- Refactoring planning and dependency reduction
- Architecture documentation
- Identifying circular dependencies
- Sharing focused context around specific files
- Reducing dead code by locating orphaned files

## Limitations

The analyzer relies on heuristic regular expressions rather than compiler tooling.

- Accuracy typically reaches around 80 percent on projects with clear structure.
- Dynamic dispatch, heavy macro usage, generated code, and conditional compilation can lead to missed dependencies.
- Method name collisions across modules may cause false positives.

For higher accuracy, consider integrating:
- [libclang](https://clang.llvm.org/docs/Tooling.html) for Objective-C and Objective-C++
- [SourceKitten](https://github.com/jpsim/SourceKitten) for Swift

## Integration Examples

### GitHub Actions

```yaml
# .github/workflows/dependencies.yml
- name: Analyze Dependencies
  run: |
    python3 swift_dep_analyzer.py ${{ github.workspace }}
    dot -Tsvg output/*/graph.dot -o dependencies.svg
```

### Pre-commit Hook

```bash
#!/bin/sh
# .git/hooks/pre-commit
changed_files=$(git diff --cached --name-only --diff-filter=ACMR | grep -E '\.(swift|m|h)$' | head -1)
if [ -n "$changed_files" ]; then
    python3 swift_dep_analyzer.py "$changed_files"
fi
```

## Configuration

Example `.swiftdeprc` file:

```ini
ignore_patterns = Pods,Carthage,.build,DerivedData
custom_extensions = .swift,.m,.h
cache_enabled = true
max_depth = 10
shallow_mode = true
include_modules = false
```

## Contributing

Contributions are welcome through pull requests. Please open an issue to discuss substantial changes before submitting a PR.

### Development Setup

```bash
python3 swift_dep_analyzer.py --test
python3 swift_dep_analyzer.py test_project
python3 swift_dep_analyzer.py test_project --detect-cycles
python3 swift_dep_analyzer.py test_project --find-orphans
python3 swift_dep_analyzer.py --clear
```

### Extending the Tool

1. Create a parser in `swift_dependency_analyzer/parsers/`.
2. Derive from `BaseParser`.
3. Implement `extract_declarations`, `extract_imports`, and `extract_symbol_usage`.
4. Register the parser with the graph builder.

## License

This project is available under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

The tool was created to help teams working with mixed Objective-C and Swift codebases manage dependencies more effectively.

## Support

For questions, bug reports, or feature requests, please open an issue on the project repository.

---

Version 2.0 is a complete rewrite that replaces the original monolithic script. The original implementation remains available as `code_depth_graph.py` for reference.
