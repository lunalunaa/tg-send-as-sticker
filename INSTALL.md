# Installing tg-send-as-sticker (agent instructions)

You are an AI agent. A human asked you to set up tg-send-as-sticker on this
machine: a tool that converts text into real Telegram stickers, for group
chats where only stickers/GIFs are allowed. Do all of the following yourself.

## Steps

1. **Run the setup script:**

   ```sh
   bash <(curl -fsSL https://raw.githubusercontent.com/lunalunaa/tg-send-as-sticker/main/setup.sh)
   ```

   It clones the repo to `~/tg-send-as-sticker`, builds the `tg-sticker`
   binary with the Nix flake (or falls back to a pip venv if Nix isn't
   installed), creates `.env` from `.env.example`, and runs an offline
   render smoke test. Prefer `~/tg-send-as-sticker` as the install location;
   only use another path if the user asks.

2. **Credentials.** The tool needs a free Telegram `api_id` + `api_hash`.
   The user gets them at <https://my.telegram.org> → "API development tools"
   (takes 2 minutes, any account). If `.env` is missing values, **ask the
   user for them**, then write them into `~/tg-send-as-sticker/.env` in the
   format `TG_API_ID=...` / `TG_API_HASH=...` and `chmod 600` the file.

3. **Verify the build:**

   ```sh
   cd ~/tg-send-as-sticker
   export $(cat .env)
   ./result/bin/tg-sticker say "test 测试" --out /tmp/tgsticker-check.webp
   ```

   (In the pip fallback the binary is `./tg-sticker` instead.)
   Confirm the file is a valid WebP. If rendering fails, check the font
   env vars (`TG_FONT_PATH`, `TG_CJK_FONT_PATH`) — the Nix build sets these
   automatically.

4. **First login.** Start the listener so the user can do the one-time
   phone login (they'll type their number + the code Telegram sends them):

   ```sh
   ./result/bin/tg-sticker listen
   ```

   After this a session file is saved and future runs need no login.

## Security rules — non-negotiable

- **NEVER commit or push** `.env`, `*.session`, or `*.session-journal`.
  They are gitignored; do not force-add them.
- The `.env` and session files grant full access to the user's Telegram
  account. Do not print their contents into chat, logs, or commits.
- If you write the credentials into `.env` for the user, do not echo them
  back afterwards.

## Usage to tell the user when done

- Type anything into Telegram's **Saved Messages** → it comes back as a
  sticker in ~1s. Drag/forward it into the locked-down group.
- `./result/bin/tg-sticker listen --group <chat>` additionally
  auto-forwards every sticker to that group and replaces any plain text the
  user posts there with a sticker version.
- `./result/bin/tg-sticker say "text" --send <chat>` sends a one-off
  sticker straight from the command line.
- `<chat>` can be: `@username`, a numeric id like `-1001234567890`, a
  `t.me/...` link, the exact group title as it appears in the user's chat
  list (they must be a member), or `me` for Saved Messages. The tool prints
  what it resolved at startup so the user can confirm it's the right group.

Report what actually happened: build result, smoke-test render size, and
whether login succeeded. If something failed, say so — don't claim success
you didn't verify.
