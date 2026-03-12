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

# --- Install ---
echo ""
echo "Installing di-quantizer..."
echo ""

$PYTHON -m pip install --user . 2>&1 | tail -5

# --- Verify ---
echo ""

# Check if the user's local bin is on PATH
USER_BIN=$($PYTHON -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))" 2>/dev/null || true)

if command -v diq &>/dev/null; then
    echo -e "${GREEN}Installed successfully!${NC}"
    echo ""
    echo "  You can now run:  diq quantize your_file.wav --bpm 120"
    echo ""
elif [ -n "$USER_BIN" ] && [ -f "$USER_BIN/diq" ]; then
    echo -e "${YELLOW}Installed, but $USER_BIN is not on your PATH.${NC}"
    echo ""
    SHELL_NAME=$(basename "$SHELL")
    if [ "$SHELL_NAME" = "zsh" ]; then
        RC_FILE="~/.zshrc"
    else
        RC_FILE="~/.bashrc"
    fi
    echo "  Add it by running this, then restart your terminal:"
    echo ""
    echo "    echo 'export PATH=\"$USER_BIN:\$PATH\"' >> $RC_FILE"
    echo ""
else
    # Fallback: try a global install
    echo -e "${YELLOW}User install didn't put diq on PATH. Trying global install...${NC}"
    $PYTHON -m pip install . 2>&1 | tail -3
    if command -v diq &>/dev/null; then
        echo -e "${GREEN}Installed successfully!${NC}"
        echo ""
        echo "  You can now run:  diq quantize your_file.wav --bpm 120"
        echo ""
    else
        echo -e "${RED}Install finished but 'diq' command not found.${NC}"
        echo "  You can still run it with:  $PYTHON -m di_quantizer"
        echo ""
    fi
fi
