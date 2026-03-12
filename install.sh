#!/bin/bash
# di-quantizer installer
# Usage: curl the repo, cd in, run this script. That's it.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "  di-quantizer installer"
echo "  ======================"
echo ""

# --- Check Python ---
# Ensure Homebrew paths are available (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    for brewdir in /opt/homebrew/bin /usr/local/bin; do
        [[ -d "$brewdir" ]] && [[ ":$PATH:" != *":$brewdir:"* ]] && export PATH="$brewdir:$PATH"
    done
fi

check_python() {
    local cmd="$1"
    if [ -x "$cmd" ] || command -v "$cmd" >/dev/null 2>&1; then
        local ver
        ver=$("$cmd" --version 2>&1) || return 1
        local major minor
        major=$(echo "$ver" | sed -n 's/.*Python \([0-9]*\)\.\([0-9]*\).*/\1/p')
        minor=$(echo "$ver" | sed -n 's/.*Python \([0-9]*\)\.\([0-9]*\).*/\2/p')
        [ -n "$major" ] && [ "$major" -ge 3 ] 2>/dev/null && [ "$minor" -ge 10 ] 2>/dev/null
    else
        return 1
    fi
}

PYTHON=""
for cmd in python3 python python3.14 python3.13 python3.12 python3.11 python3.10 \
           /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if check_python "$cmd"; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}Python 3.10 or newer is required.${NC}"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Install it with:"
        echo "  brew install python"
        echo ""
        echo "Don't have Homebrew? Install it first:"
        echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    else
        echo "Install it with your package manager, e.g.:"
        echo "  sudo apt install python3"
    fi
    exit 1
fi

echo -e "${GREEN}Found $PYTHON ($($PYTHON --version))${NC}"

# --- Install into a virtual environment ---
# Modern Python (3.12+ / Homebrew) blocks pip install outside a venv (PEP 668).
# We create a dedicated venv, install there, and symlink the 'diq' command.

echo ""
echo "Installing di-quantizer..."
echo ""

INSTALL_DIR="$HOME/.local/share/di-quantizer"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$INSTALL_DIR/venv"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

# Clean previous install if present
[ -d "$INSTALL_DIR" ] && rm -rf "$INSTALL_DIR"

# Create venv
echo "  Creating virtual environment..."
$PYTHON -m venv "$VENV_DIR"

# Install into the venv
echo "  Installing package (this may take a minute)..."
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
"$VENV_DIR/bin/pip" install "$SRC_DIR" 2>&1 | tail -3

# Verify the diq script exists in the venv
if [ ! -f "$VENV_DIR/bin/diq" ]; then
    echo -e "${RED}Install failed — diq was not created in the venv.${NC}"
    echo "  Please report this issue."
    exit 1
fi

# Create ~/.local/bin and symlink diq into it
mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/diq" "$BIN_DIR/diq"

# Refresh shell hash table
hash -r 2>/dev/null || true

# --- Verify ---
echo ""

if command -v diq >/dev/null 2>&1; then
    echo -e "${GREEN}Installed successfully!${NC}"
    echo ""
    echo "  You can now run:  diq quantize your_file.wav --bpm 120"
    echo ""
elif [ -x "$BIN_DIR/diq" ]; then
    # ~/.local/bin exists but isn't on PATH — add it
    SHELL_NAME=$(basename "${SHELL:-bash}")
    if [ "$SHELL_NAME" = "zsh" ]; then
        RC_FILE="$HOME/.zshrc"
    elif [ "$SHELL_NAME" = "fish" ]; then
        RC_FILE="$HOME/.config/fish/config.fish"
    else
        RC_FILE="$HOME/.bashrc"
    fi

    if [ "$SHELL_NAME" = "fish" ]; then
        if ! grep -q "$BIN_DIR" "$RC_FILE" 2>/dev/null; then
            mkdir -p "$(dirname "$RC_FILE")"
            echo "" >> "$RC_FILE"
            echo "# Added by di-quantizer installer" >> "$RC_FILE"
            echo "set -gx PATH $BIN_DIR \$PATH" >> "$RC_FILE"
        fi
    else
        if ! grep -q "$BIN_DIR" "$RC_FILE" 2>/dev/null; then
            echo "" >> "$RC_FILE"
            echo "# Added by di-quantizer installer" >> "$RC_FILE"
            echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$RC_FILE"
        fi
    fi

    echo -e "${GREEN}Installed successfully!${NC}"
    echo ""
    echo -e "  ${YELLOW}One more step — run this, then you're good:${NC}"
    echo ""
    echo "    source $RC_FILE"
    echo ""
    echo "  Then:  diq quantize your_file.wav --bpm 120"
    echo ""
else
    echo -e "${RED}Something went wrong. The symlink at $BIN_DIR/diq is missing.${NC}"
    echo "  You can still run it directly:"
    echo "    $VENV_DIR/bin/diq quantize your_file.wav --bpm 120"
    echo ""
fi
