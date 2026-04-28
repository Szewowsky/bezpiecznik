#!/usr/bin/env bash
# Bezpiecznik — skrypt aktualizacji
# Pobiera najnowszą wersję z GitHub i aktualizuje zależności.
#
# Użycie:
#   ./update.sh              # interaktywnie
#   ./update.sh --yes        # bez pytań

set -e

YES=0
[ "$1" = "--yes" ] || [ "$1" = "-y" ] && YES=1

# Kolory (jeśli terminal je obsługuje)
if [ -t 1 ]; then
  C_OK="\033[0;32m"
  C_WARN="\033[0;33m"
  C_ERR="\033[0;31m"
  C_DIM="\033[2m"
  C_END="\033[0m"
else
  C_OK="" C_WARN="" C_ERR="" C_DIM="" C_END=""
fi

ok()    { printf "${C_OK}✓${C_END} %s\n" "$1"; }
warn()  { printf "${C_WARN}⚠${C_END} %s\n" "$1"; }
fail()  { printf "${C_ERR}✗${C_END} %s\n" "$1" >&2; exit 1; }
step()  { printf "\n${C_DIM}→${C_END} %s\n" "$1"; }

cd "$(dirname "$0")"

# ── Sprawdzenia ───────────────────────────────────────────────────────────
[ -d ".git" ] || fail "To nie jest repozytorium git. Uruchom skrypt w katalogu privacy-tool."
command -v git >/dev/null 2>&1 || fail "Git nie jest zainstalowany."
[ -d ".venv" ] || fail "Brak środowiska Python (.venv). Uruchom najpierw instalację (zobacz README)."

step "Sprawdzam aktualną wersję"
CURRENT=$(git rev-parse --short HEAD)
echo "  Aktualna wersja: $CURRENT"

step "Pobieram informacje z GitHub"
git fetch --quiet origin main || fail "Nie udało się pobrać aktualizacji. Sprawdź połączenie z internetem."

REMOTE=$(git rev-parse --short origin/main)
echo "  Najnowsza wersja: $REMOTE"

if [ "$CURRENT" = "$REMOTE" ]; then
  ok "Masz już najnowszą wersję."
  exit 0
fi

# ── Lista zmian ──────────────────────────────────────────────────────────
step "Co się zmieniło"
git log --oneline "$CURRENT..origin/main" | head -20 | sed 's/^/  • /'
echo ""

if [ "$YES" -eq 0 ]; then
  printf "Zaktualizować? [T/n] "
  read -r ans
  case "$ans" in
    n|N|nie) echo "Anulowano."; exit 0 ;;
  esac
fi

# ── Aktualizacja ─────────────────────────────────────────────────────────
step "Aktualizuję kod"
if ! git diff --quiet || ! git diff --cached --quiet; then
  warn "Masz lokalne zmiany w plikach. Stash → przywrócę po update."
  git stash push -m "auto-stash-update-$(date +%s)" >/dev/null
  STASHED=1
fi

git pull --ff-only origin main || fail "Konflikt lub problem z pull. Skontaktuj się z autorem."

if [ "${STASHED:-0}" = "1" ]; then
  step "Przywracam Twoje lokalne zmiany"
  git stash pop || warn "Nie udało się przywrócić — zmiany są w 'git stash list'."
fi

step "Aktualizuję zależności Python"
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q -r requirements.txt || fail "Problem z instalacją zależności."

# ── Done ────────────────────────────────────────────────────────────────
NEW=$(git rev-parse --short HEAD)
ok "Zaktualizowano do wersji $NEW"
echo ""
echo "Aby uruchomić:"
echo "  uvicorn server:app --port 8000     # nowy UI (Bezpiecznik)"
echo "  python app.py                       # wersja Gradio (legacy)"
