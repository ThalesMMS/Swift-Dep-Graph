# Swift Dependency Analyzer

[![Python](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)]()
[![Architecture](https://img.shields.io/badge/architecture-modular-blue.svg)]()

A lightweight, modular Python tool for analyzing and visualizing dependencies in iOS/macOS projects (Objective-C, Objective-C++, and Swift). Generate dependency graphs with labeled edges showing method/symbol usage and calculate transitive closures to identify minimal relevant file sets.

## 🎉 Project Status: PRODUCTION READY

**v2.0** - Completely refactored with modular architecture. All core features implemented and thoroughly tested.

## 🚀 Features

- **Multi-language Support**: Analyzes Objective-C (.m, .h), Objective-C++ (.mm, .hh), and Swift (.swift) files
- **Automatic Project Detection**: Automatically finds Xcode project root from any file within the project
- **Smart Defaults**: Shallow analysis (only used symbols) and automatic closure calculation for files
- **Symbol-level Analysis**: Labels dependency edges with actual methods/symbols used
- **Direct Transitive Closure**: Automatically calculates dependencies for single files
- **Multiple Output Formats**: JSON, DOT (Graphviz), Mermaid, CSV for various analysis needs
- **Zero Dependencies**: Pure Python implementation using only standard library
- **Built-in Test Project**: Generate complex test project with cycles, orphans, and deep dependencies
- **Path Exclusion**: Ignore specific directories like Pods, .build, or Carthage
- **Advanced Analysis**: Detect cycles, find orphan files, find paths between files (BFS)
- **Performance Optimized**: Built-in caching system for large projects
- **Modular Architecture**: Clean separation of concerns with extensible parsers and formatters

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Swift-Dependency-Analyzer.git
cd Swift-Dependency-Analyzer

# No installation needed - just Python 3.6+
python3 --version  # Verify Python 3.6 or higher
```

## 🔧 Usage

### Quick Start with Test Project

```bash
# Generate a realistic test project
python3 swift_dep_analyzer.py --test

# Analyze the test project (created automatically if doesn't exist)
python3 swift_dep_analyzer.py test_project

# Or analyze with options
python3 swift_dep_analyzer.py test_project --ignore Pods --detect-cycles
```

### Basic Analysis

Analyze from any file within your Xcode project:
```bash
# Auto-detect project root from a file (automatically calculates closure)
python3 swift_dep_analyzer.py /path/to/project/Sources/MyViewController.swift

# Disable automatic closure for files
python3 swift_dep_analyzer.py /path/to/MyFile.swift --no-closure

# Or analyze from project directory
python3 swift_dep_analyzer.py /path/to/xcode/project

# Use extended mode (includes all imports, not just used symbols)
python3 swift_dep_analyzer.py /path/to/project --extended

# Exclude specific directories
python3 swift_dep_analyzer.py /path/to/project --ignore Pods --ignore .build
```

### Calculate Direct Transitive Closure

Find all files that a specific file depends on (automatic for files):
```bash
# Automatic closure for files (no flag needed)
python3 swift_dep_analyzer.py /path/to/MyFile.swift

# Include external modules in closure
python3 swift_dep_analyzer.py /path/to/MyFile.swift --include-modules

# Show only direct dependencies
python3 swift_dep_analyzer.py /path/to/MyFile.swift --direct-deps-only

# Use extended analysis (includes all imports)
python3 swift_dep_analyzer.py /path/to/MyFile.swift --extended
```

### Advanced Analysis

```bash
# Detect circular dependencies
python3 swift_dep_analyzer.py /path/to/project --detect-cycles

# Find orphan (unreferenced) files
python3 swift_dep_analyzer.py /path/to/project --find-orphans

# Find all paths between two files (BFS - shortest paths first)
python3 swift_dep_analyzer.py /path/to/FileA.swift --showPath FileB.swift

# Export to multiple formats
python3 swift_dep_analyzer.py /path/to/project --mermaid --csv

# Disable cache for fresh analysis
python3 swift_dep_analyzer.py /path/to/project --no-cache

# Clean output directory
python3 swift_dep_analyzer.py --clear
```

### Custom Options

```bash
# Specify output directory (default: ./output)
python3 swift_dep_analyzer.py /path/to/project --output-dir ./analysis

# Use configuration file
python3 swift_dep_analyzer.py /path/to/project --config .swiftdeprc
```

### Visualize Results

Convert the generated graph to visual formats:
```bash
# Generate PDF
dot -Tpdf output/project_name/graph.dot -o dependencies.pdf

# Generate PNG
dot -Tpng output/project_name/graph.dot -o dependencies.png

# Generate SVG (web-friendly)
dot -Tsvg output/project_name/graph.dot -o dependencies.svg
```

## 📊 Output Files

All output files are saved to `output/<project_or_file_name>/` by default:

| File | Description |
|------|-------------|
| `graph.json` | Complete dependency graph with edge labels (methods/symbols used) |
| `graph.dot` | Graphviz format for visualization |
| `graph.mmd` | Mermaid diagram format (when using --mermaid) |
| `graph.csv` | Dependency relationships in CSV format (when using --csv) |
| `metrics.csv` | Complexity metrics and statistics (when using --csv) |
| `closure_*.txt` | Direct transitive closure results - files that the input depends on |
| `cycles.txt` | Detected circular dependencies (when using --detect-cycles) |
| `orphans.txt` | Unreferenced files list (when using --find-orphans) |
| `path_*.txt` | Paths between two files (when using --showPath) |

## 🏗️ Architecture

### Modular Design (v2.0)

```
swift_dependency_analyzer/
├── parsers/           # Language-specific parsers
│   ├── base_parser.py # Abstract base class
│   ├── objc_parser.py # Objective-C/C++ parser
│   └── swift_parser.py # Swift parser
├── graph/            # Graph construction and analysis
│   ├── builder.py    # Graph builder
│   └── analyzer.py   # Graph analysis (cycles, paths, metrics)
├── output/           # Output formatters
│   ├── formatters.py # JSON, DOT, Mermaid, CSV formatters
│   └── exporter.py   # Export manager
├── utils/            # Utilities
│   ├── file_utils.py # File operations
│   ├── cache_manager.py # Cache management
│   └── config_manager.py # Configuration
└── test_generator/   # Test project generator
```

### How It Works

1. **Symbol Indexing**: Scans all source files to build a symbol index
   - **Objective-C**: `@interface`, `@protocol`, `@implementation`, `NS_ENUM`, C functions
   - **Swift**: `class`, `struct`, `enum`, `protocol`, `extension`, top-level functions

2. **Dependency Detection**: Identifies dependencies through
   - **Direct imports**: `#import`, `@import`, `import` statements
   - **Symbol usage**: Method calls, type references, protocol conformance
   - **Bridging headers**: Swift-to-ObjC interop detection

3. **Graph Construction**: Creates a directed graph where
   - **Nodes**: Source files
   - **Edges**: A→B means "A depends on/uses B"
   - **Labels**: Specific symbols/methods that A uses from B
   - **Transitive Closure**: Finds all direct and indirect dependencies

## 🎯 Use Cases

- **Code Review**: Understand impact scope before making changes
- **Refactoring**: Identify tightly coupled components
- **Documentation**: Generate architecture diagrams
- **Optimization**: Find and break circular dependencies
- **Context Sharing**: Share only the minimal set of files needed to understand a specific file's context
- **Dead Code Detection**: Find orphan files that can be safely removed

## ⚠️ Limitations

This tool uses **heuristic regex patterns** for analysis, not a full compiler:

- **Accuracy**: ~80% for typical projects with clear structures
- **May miss**: Dynamic dispatch, complex macros, generated code, conditional compilation
- **False positives**: Possible with method name collisions across modules

For production-critical analysis, consider integrating:
- [libclang](https://clang.llvm.org/docs/Tooling.html) for Objective-C/C++
- [SourceKitten](https://github.com/jpsim/SourceKitten) for Swift

## 🔄 Integration Examples

### CI/CD Pipeline
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

## ⚙️ Configuration

Create a `.swiftdeprc` file in your project or home directory:

```ini
# .swiftdeprc example
ignore_patterns = Pods,Carthage,.build,DerivedData
custom_extensions = .swift,.m,.h
cache_enabled = true
max_depth = 10
shallow_mode = true
include_modules = false
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup
```bash
# Generate complex test project with various scenarios
python3 swift_dep_analyzer.py --test

# Run analysis on test project
python3 swift_dep_analyzer.py test_project

# Test specific features
python3 swift_dep_analyzer.py test_project --detect-cycles
python3 swift_dep_analyzer.py test_project --find-orphans

# Clean output directory
python3 swift_dep_analyzer.py --clear
```

### Extending the Tool

To add support for a new language:
1. Create a new parser in `swift_dependency_analyzer/parsers/`
2. Inherit from `BaseParser`
3. Implement required methods: `extract_declarations`, `extract_imports`, `extract_symbol_usage`
4. Register the parser in the `GraphBuilder`

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the need for better dependency management in large iOS codebases
- Built for teams working with mixed Objective-C and Swift projects
- Special thanks to the Xcode and Swift community

## 📧 Support

For questions, bug reports, or feature requests, please [open an issue](https://github.com/yourusername/Swift-Dependency-Analyzer/issues).

---

**Note**: This is a complete rewrite (v2.0) with modular architecture. The original monolithic version is kept as `code_depth_graph.py` for reference only.