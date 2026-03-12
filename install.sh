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

# Use pipx if available (handles PATH automatically), otherwise pip
INSTALLED_VIA=""
if command -v pipx >/dev/null 2>&1; then
    echo "Using pipx..."
    pipx install --force . 2>&1 | tail -5 && INSTALLED_VIA="pipx"
fi

if [ -z "$INSTALLED_VIA" ]; then
    # Try normal pip install first; capture output to preserve exit code
    set +e
    PIP_OUT=$($PYTHON -m pip install . 2>&1)
    PIP_RC=$?
    set -e
    echo "$PIP_OUT" | tail -5
    if [ "$PIP_RC" -ne 0 ]; then
        # Likely hit externally-managed-environment error; try --user
        echo ""
        echo "Retrying with --user flag..."
        $PYTHON -m pip install --user . 2>&1 | tail -5
    fi
    INSTALLED_VIA="pip"
fi

# Refresh shell hash table so 'command -v' picks up newly installed scripts
hash -r 2>/dev/null || true

# --- Verify ---
echo ""

# Collect all directories where diq might have been installed
find_diq_dir() {
    local dir
    for dir in \
        "$($PYTHON -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)" \
        "$($PYTHON -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))" 2>/dev/null)" \
        /opt/homebrew/bin \
        /usr/local/bin \
        "$HOME/.local/bin" \
        "$HOME/Library/Python/3.14/bin" \
        "$HOME/Library/Python/3.13/bin" \
        "$HOME/Library/Python/3.12/bin" \
        "$HOME/Library/Python/3.11/bin" \
        "$HOME/Library/Python/3.10/bin"; do
        [ -n "$dir" ] && [ -f "$dir/diq" ] && echo "$dir" && return 0
    done
    return 1
}

if command -v diq >/dev/null 2>&1; then
    echo -e "${GREEN}Installed successfully!${NC}"
    echo ""
    echo "  You can now run:  diq quantize your_file.wav --bpm 120"
    echo ""
elif DIQ_DIR=$(find_diq_dir); then
    # Found it, but it's not on PATH — fix that
    export PATH="$DIQ_DIR:$PATH"

    SHELL_NAME=$(basename "${SHELL:-bash}")
    if [ "$SHELL_NAME" = "zsh" ]; then
        RC_FILE="$HOME/.zshrc"
    elif [ "$SHELL_NAME" = "fish" ]; then
        RC_FILE="$HOME/.config/fish/config.fish"
    else
        RC_FILE="$HOME/.bashrc"
    fi

    # Add to shell config if not already there
    if [ "$SHELL_NAME" = "fish" ]; then
        if ! grep -q "$DIQ_DIR" "$RC_FILE" 2>/dev/null; then
            mkdir -p "$(dirname "$RC_FILE")"
            echo "" >> "$RC_FILE"
            echo "# Added by di-quantizer installer" >> "$RC_FILE"
            echo "set -gx PATH $DIQ_DIR \$PATH" >> "$RC_FILE"
        fi
    else
        if ! grep -q "$DIQ_DIR" "$RC_FILE" 2>/dev/null; then
            echo "" >> "$RC_FILE"
            echo "# Added by di-quantizer installer" >> "$RC_FILE"
            echo "export PATH=\"$DIQ_DIR:\$PATH\"" >> "$RC_FILE"
        fi
    fi

    echo -e "${GREEN}Installed successfully!${NC}"
    echo ""
    echo -e "  'diq' was installed to ${YELLOW}$DIQ_DIR${NC}"
    echo ""
    echo -e "  ${YELLOW}To start using it, run:${NC}"
    echo ""
    if [ "$SHELL_NAME" = "fish" ]; then
        echo "    source $RC_FILE"
    else
        echo "    source $RC_FILE"
    fi
    echo ""
    echo "  Or just open a new terminal, then:"
    echo ""
    echo "    diq quantize your_file.wav --bpm 120"
    echo ""
else
    echo -e "${YELLOW}Install finished. Use this command to run it:${NC}"
    echo ""
    echo "  $PYTHON -m di_quantizer quantize your_file.wav --bpm 120"
    echo ""
fi
