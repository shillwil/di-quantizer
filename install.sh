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

# Try normal install first (works with Homebrew Python), fall back to --user
if ! $PYTHON -m pip install . 2>&1 | tail -5; then
    echo "Retrying with --user flag..."
    $PYTHON -m pip install --user . 2>&1 | tail -5
fi

# --- Verify ---
echo ""

# Find where pip put the diq script
find_diq() {
    # Check PATH first
    command -v diq 2>/dev/null && return 0
    # Check common pip install locations
    for dir in \
        "$($PYTHON -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)" \
        "$($PYTHON -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))" 2>/dev/null)" \
        "$($PYTHON -c "import site; print(site.getusersitepackages().replace('/lib/', '/bin/'))" 2>/dev/null)" \
        /opt/homebrew/bin \
        /usr/local/bin \
        "$HOME/.local/bin" \
        "$HOME/Library/Python/3.14/bin" \
        "$HOME/Library/Python/3.13/bin" \
        "$HOME/Library/Python/3.12/bin" \
        "$HOME/Library/Python/3.11/bin" \
        "$HOME/Library/Python/3.10/bin"; do
        [ -n "$dir" ] && [ -f "$dir/diq" ] && echo "$dir/diq" && return 0
    done
    return 1
}

DIQ_PATH=$(find_diq)

if [ -n "$DIQ_PATH" ]; then
    DIQ_DIR=$(dirname "$DIQ_PATH")

    # Check if it's already usable via PATH
    if command -v diq >/dev/null 2>&1; then
        echo -e "${GREEN}Installed successfully!${NC}"
        echo ""
        echo "  You can now run:  diq quantize your_file.wav --bpm 120"
        echo ""
    else
        # Add to PATH in current shell and shell config
        export PATH="$DIQ_DIR:$PATH"

        SHELL_NAME=$(basename "${SHELL:-bash}")
        if [ "$SHELL_NAME" = "zsh" ]; then
            RC_FILE="$HOME/.zshrc"
        else
            RC_FILE="$HOME/.bashrc"
        fi

        # Add to shell config if not already there
        if ! grep -q "$DIQ_DIR" "$RC_FILE" 2>/dev/null; then
            echo "" >> "$RC_FILE"
            echo "# Added by di-quantizer installer" >> "$RC_FILE"
            echo "export PATH=\"$DIQ_DIR:\$PATH\"" >> "$RC_FILE"
        fi

        echo -e "${GREEN}Installed successfully!${NC}"
        echo ""
        echo -e "${YELLOW}NOTE: Restart your terminal (or run 'source $RC_FILE') for the 'diq' command to work.${NC}"
        echo ""
        echo "  Then run:  diq quantize your_file.wav --bpm 120"
        echo ""
    fi
else
    echo -e "${YELLOW}Install finished. Use this command to run it:${NC}"
    echo ""
    echo "  $PYTHON -m di_quantizer quantize your_file.wav --bpm 120"
    echo ""
fi
