#!/bin/bash
# install-alias.sh — dodaje alias `bezpiecznik` do shella, żeby uruchamiać
# aplikację jednym słowem (zamiast szukać katalogu i odpalać uvicorn).
#
# Użycie (w katalogu bezpiecznika):
#   ./install-alias.sh
#
# Po instalacji:
#   bezpiecznik           → startuje serwer na http://localhost:8000

set -e

# Absolutna ścieżka do tego skryptu (= katalog bezpiecznika)
BEZPIECZNIK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_UVICORN="$BEZPIECZNIK_DIR/.venv/bin/uvicorn"

# Sprawdź czy venv istnieje
if [ ! -f "$VENV_UVICORN" ]; then
    echo "Brak .venv w $BEZPIECZNIK_DIR"
    echo "Najpierw zainstaluj zależności (Krok 5 z README):"
    echo "    python3 -m venv .venv"
    echo "    source .venv/bin/activate"
    echo "    pip install -r requirements.txt"
    exit 1
fi

# Wykryj shell config — zsh (default na macOS od Catalina) albo bash
if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
    SHELL_NAME="zsh"
elif [ -n "$BASH_VERSION" ] || [ "$(basename "$SHELL")" = "bash" ]; then
    SHELL_RC="$HOME/.bashrc"
    [ ! -f "$SHELL_RC" ] && SHELL_RC="$HOME/.bash_profile"
    SHELL_NAME="bash"
else
    echo "Nieznany shell: $SHELL"
    echo "Dodaj ręcznie do swojego shell rc:"
    echo "    alias bezpiecznik='cd \"$BEZPIECZNIK_DIR\" && .venv/bin/uvicorn server:app --port 8000'"
    exit 1
fi

# Sprawdź czy alias już istnieje
if grep -q "alias bezpiecznik=" "$SHELL_RC" 2>/dev/null; then
    echo "Alias 'bezpiecznik' już istnieje w $SHELL_RC"
    echo "Nic nie robię. Jeśli chcesz zaktualizować, usuń go ręcznie i odpal ponownie."
    exit 0
fi

# Dodaj alias
{
    echo ""
    echo "# Bezpiecznik — lokalny strażnik danych wrażliwych (https://github.com/Szewowsky/bezpiecznik)"
    echo "alias bezpiecznik='cd \"$BEZPIECZNIK_DIR\" && .venv/bin/uvicorn server:app --port 8000'"
} >> "$SHELL_RC"

echo "Alias dodany do $SHELL_RC"
echo ""
echo "Aby zacząć używać, wpisz w terminalu:"
echo "    source $SHELL_RC"
echo ""
echo "Albo po prostu otwórz nowe okno terminala. Potem:"
echo "    bezpiecznik"
echo ""
echo "Aplikacja wystartuje na http://localhost:8000"
