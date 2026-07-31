# tg-sticker-bypass

For group chats where plain text is banned and only stickers/GIFs are allowed:
this tool converts anything you want to say into a **real Telegram sticker**
(512×512 WebP, auto-wrapped, auto-sized, outlined for readability on any
background), and sends it from your own account via Telethon.

Full Unicode support: Latin, **中文**, 日本語, 한국어, mixed text — CJK text
renders in Noto Sans CJK Bold and wraps per-character; Latin text renders in
DejaVu Sans Bold and wraps per-word.

## Setup

### Option A — just tell your agent this (copy-paste)

> Clone and set up tg-sticker-bypass on this machine: run
> `bash <(curl -fsSL https://raw.githubusercontent.com/OWNER/tg-bypass/main/setup.sh)`.
> It clones the repo to ~/workspace/git-repos/tg-bypass, builds it with the
> Nix flake (or falls back to a pip venv if there's no Nix), creates `.env`
> from `.env.example`, and runs an offline render smoke test. Ask me for my
> Telegram api_id/api_hash if the script needs them (I get them free at
> https://my.telegram.org → API development tools), write them into `.env`,
> then verify the build by running `tg-sticker say "test 测试" --out /tmp/x.webp`.
> Finally start it with `tg-sticker listen` so I can do the one-time phone
> login. Never commit `.env` or `*.session` files.

That's it — paste the quoted paragraph to your agent (Hermes, Claude Code,
Codex, etc.) and it will do everything below by itself.

### Option B — manual

```sh
git clone https://github.com/OWNER/tg-bypass.git ~/workspace/git-repos/tg-bypass
cd ~/workspace/git-repos/tg-bypass
./setup.sh
```

Or fully by hand:

```sh
nix build            # builds ./result/bin/tg-sticker
# or: nix develop    # drops you in a shell with python + deps
```

Get free API credentials at <https://my.telegram.org> (any account can), then:

```sh
cp .env.example .env   # fill in TG_API_ID and TG_API_HASH
export $(cat .env)     # or use direnv / your shell's env loader
```

## Usage

### 1. Interactive mode (the actual bypass)

```sh
tg-sticker listen
```

- First run asks for your phone number + login code, then saves a session file
  (`tgsticker.session`) so you only log in once. **Keep this file private —
  it grants full access to your account.**
- **Anything you type into your own "Saved Messages" chat is instantly
  re-sent as a sticker** — drag/forward it into the locked-down group.
- With `--group <username-or-id>`:
  - Saved Messages stickers are **also auto-forwarded to the group**, and
  - any plain text you accidentally post in the group is **deleted and
    replaced with a sticker version** within a second.

```sh
tg-sticker listen --group my_sticker_only_group
```

### 2. One-off rendering (no login needed)

```sh
tg-sticker say "mods can't stop me" --out sticker.webp
tg-sticker say "这也太离谱了" --out chinese.webp
tg-sticker say "send it straight to the group" --send my_sticker_only_group
```

- Text auto-wraps and auto-sizes (largest font that fits, down to 12px).
- Long words get hard-split; absurdly long messages are clipped at ~20 lines.
- `--fg` / `--outline` change text/outline colors (default white on black).

## How it passes Telegram's sticker rules

- Exactly 512×512 px, WebP, `exact=True` (no size metadata tricks).
- Quality auto-degrades if the file ever exceeds the 512 KB sticker limit.
- Sent with `force_document=False`, so Telegram's clients treat it as a
  native sticker, not a file attachment.

## Files

| file           | purpose                                          |
| -------------- | ------------------------------------------------ |
| `tgsticker.py` | renderer (Pillow) + Telethon listen/say commands |
| `flake.nix`    | python312 + telethon + pillow + fonttools + fonts |
| `.env.example` | template for your API credentials                |

## Notes / caveats

- This is a **userbot** (Telethon user session). Automating a user account is
  against Telegram's ToS if abused; for occasional personal use in one group
  it's generally tolerated, but don't spam or run mass automation with it.
- The group-replace trick requires you to have delete rights on your own
  messages (always true in normal groups).
- `.env`, `*.session`, and `*.session-journal` are gitignored — never commit
  them.

## License

MIT — see [LICENSE](LICENSE).
