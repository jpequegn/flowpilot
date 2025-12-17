# Installation

## Prerequisites

- **macOS** (primary supported platform)
- **Python 3.11+**
- **pip** or **uv** package manager

### Optional Dependencies

- **Claude CLI** - For AI-powered nodes (`claude_cli` type)
- **Node.js/Bun** - For frontend development

## Installation Methods

### From GitHub Release (Recommended)

Download the latest wheel from GitHub Releases:

```bash
# Download the wheel file
curl -LO https://github.com/jpequegn/flowpilot/releases/latest/download/flowpilot-1.0.0-py3-none-any.whl

# Install with pip
pip install flowpilot-1.0.0-py3-none-any.whl

# Or with uv (faster)
uv pip install flowpilot-1.0.0-py3-none-any.whl
```

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/jpequegn/flowpilot.git
cd flowpilot

# Install with uv (recommended)
uv sync --all-extras

# Or with pip
pip install -e ".[dev]"
```

### Building from Source

If you want to build the package with the bundled frontend:

```bash
# Clone and enter directory
git clone https://github.com/jpequegn/flowpilot.git
cd flowpilot

# Build frontend and package
python scripts/build.py --all

# Install the built wheel
pip install dist/flowpilot-*.whl
```

## Verification

After installation, verify FlowPilot is working:

```bash
# Check version
flowpilot --version

# View help
flowpilot --help

# Available commands
flowpilot init --help
flowpilot serve --help
flowpilot run --help
```

## Setting Up Claude CLI (Optional)

For AI-powered nodes, install and configure Claude CLI:

```bash
# Install Claude CLI (if not already installed)
npm install -g @anthropic-ai/claude-cli

# Verify installation
claude --version
```

Ensure your Anthropic API key is configured (see Claude CLI documentation).

## Next Steps

- [Quick Start Guide](quick-start.md) - Create your first workflow
- [Configuration](configuration.md) - Configure FlowPilot settings
