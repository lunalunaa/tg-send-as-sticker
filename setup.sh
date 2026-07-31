#!/usr/bin/env bash
# tg-sticker-bypass one-click setup.
# Safe for an AI agent (or a human) to run non-interactively-ish:
#   bash <(curl -fsSL https://raw.githubusercontent.com/lunalunaa/tg-send-as-sticker/main/setup.sh)
# or from a clone:  ./setup.sh
set -euo pipefail

REPO_URL="${TG_REPO_URL:-https://github.com/lunalunaa/tg-send-as-sticker.git}"
DEST="${TG_DEST:-$HOME/workspace/git-repos/tg-bypass}"

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------- 1. clone
if [ -d "$DEST/.git" ]; then
  say "repo already at $DEST — pulling latest"
  git -C "$DEST" pull --ff-only || warn "pull failed, continuing with local copy"
else
  say "cloning $REPO_URL -> $DEST"
  git clone "$REPO_URL" "$DEST"
fi
cd "$DEST"

# ---------------------------------------------------------------- 2. deps + build
if command -v nix >/dev/null 2>&1; then
  say "nix found — building with flake"
  nix build .#default -o result
  BIN="$DEST/result/bin/tg-sticker"
else
  warn "nix not found — falling back to pip install into a venv"
  PYTHON_BIN="$(command -v python3 || true)"
  if [ -z "$PYTHON_BIN" ]; then
    echo "No nix and no python3 on PATH. Install one of them and re-run." >&2
    exit 1
  fi
  "$PYTHON_BIN" -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet telethon pillow fonttools
  cat > tg-sticker <<EOF
#!/usr/bin/env bash
exec "$DEST/.venv/bin/python" "$DEST/tgsticker.py" "\$@"
EOF
  chmod +x tg-sticker
  BIN="$DEST/tg-sticker"
  warn "pip fallback: you'll need DejaVu Sans Bold + Noto Sans CJK fonts installed"
  warn "or set TG_FONT_PATH / TG_CJK_FONT_PATH manually."
fi
say "binary: $BIN"

# ---------------------------------------------------------------- 3. credentials
if [ ! -f .env ]; then
  cp .env.example .env
fi
# shellcheck disable=SC1091
set -a; . ./.env 2>/dev/null || true; set +a

if [ -z "${TG_API_ID:-}" ] || [ -z "${TG_API_HASH:-}" ]; then
  say "Telegram API credentials needed (free at https://my.telegram.org → API development tools)"
  if [ -t 0 ]; then
    read -rp "TG_API_ID: " TG_API_ID
    read -rp "TG_API_HASH: " TG_API_HASH
  else
    warn "non-interactive: fill in $DEST/.env before running 'listen'"
  fi
  if [ -n "${TG_API_ID:-}" ] && [ -n "${TG_API_HASH:-}" ]; then
    printf 'TG_API_ID=%s\nTG_API_HASH=%s\n' "$TG_API_ID" "$TG_API_HASH" > .env
    chmod 600 .env
    say "credentials written to .env (chmod 600, gitignored)"
  fi
else
  say "credentials already present in .env"
fi

# ---------------------------------------------------------------- 4. smoke test
say "smoke test (offline render)"
if "$BIN" say "setup ok 安装成功" --out /tmp/tg-sticker-setup-check.webp; then
  say "render works: /tmp/tg-sticker-setup-check.webp"
else
  warn "render failed — check fonts / deps above"
fi

cat <<EOF

$(say "done")

Run it:
  cd $DEST
  export \$(cat .env)
  $BIN listen                 # then text yourself in Saved Messages
  $BIN listen --group <name>  # full auto mode for a sticker-only group

First 'listen' run asks for your phone number and Telegram login code once,
then saves a session so you never log in again.
EOF
