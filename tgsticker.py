#!/usr/bin/env python3
"""tg-sticker-bypass: auto-convert text into Telegram stickers.

For group chats where plain text is banned and only stickers/GIFs are allowed.

Two modes:
  listen   Connect to Telegram via Telethon; any text you send in "Saved
           Messages" is instantly converted to a sticker and re-sent, so you
           can drag it into the group. Optionally also relays a target group:
           any text you post that the group would reject gets deleted and
           replaced with a sticker (uses your own userbot session).
  say      Render a one-off sticker from the command line (no login needed
           unless you pass --send).

Sticker spec (Telegram): 512x512 WebP, one side must be exactly 512px,
max 512 KB. We render text auto-wrapped, auto-sized, with a high-contrast
outline so it reads on any background.
"""

import argparse
import asyncio
import io
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- rendering

STICKER_SIZE = 512
FONT_PATH = os.environ.get(
    "TG_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)
# CJK fallback for characters the main font doesn't cover
CJK_FONT_PATH = os.environ.get("TG_CJK_FONT_PATH", "")

_FONT_CACHE: dict = {}
_CMAP_CACHE: dict = {}


def _cmap(path: str) -> dict:
    """Best unicode cmap for a font file (fontTools)."""
    if path not in _CMAP_CACHE:
        from fontTools.ttLib import TTFont, TTCollection

        try:
            if path.endswith((".ttc", ".otc")):
                fonts = TTCollection(path, lazy=True).fonts
            else:
                fonts = [TTFont(path, lazy=True, fontNumber=0)]
            merged: dict = {}
            for f in fonts:
                merged.update(f.getBestCmap() or {})
                f.close()
            _CMAP_CACHE[path] = merged
        except Exception:
            _CMAP_CACHE[path] = {}
    return _CMAP_CACHE[path]


def _covers(path: str, ch: str) -> bool:
    if not path:
        return False
    return ord(ch) in _cmap(path)


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont | None:
    key = (path, size)
    if key not in _FONT_CACHE:
        try:
            f = ImageFont.truetype(path, size)
            # Variable fonts default to their lightest instance; pin Bold.
            try:
                f.set_variation_by_axes([700])
            except Exception:
                pass
            _FONT_CACHE[key] = f
        except OSError:
            _FONT_CACHE[key] = None
    return _FONT_CACHE[key]


def _fonts_for(size: int) -> tuple:
    """(base_font, cjk_font_or_None) at a given size."""
    base = _load_font(FONT_PATH, size)
    if base is None:
        base = ImageFont.load_default()
    cjk = _load_font(CJK_FONT_PATH, size) if CJK_FONT_PATH else None
    return base, cjk


def _is_cjk(ch: str) -> bool:
    import unicodedata

    return unicodedata.east_asian_width(ch) in ("W", "F")


def _tokenize(paragraph: str) -> list[str]:
    """Split into wrappable units: latin words (keep ' '), CJK chars one-by-one."""
    tokens: list[str] = []
    for part in paragraph.split(" "):
        if not part:
            continue
        buf = ""
        for ch in part:
            if _is_cjk(ch):
                if buf:
                    tokens.append(buf + " ")
                    buf = ""
                tokens.append(ch)
            else:
                buf += ch
        if buf:
            tokens.append(buf + " ")
    if tokens and tokens[-1].endswith(" "):
        tokens[-1] = tokens[-1].rstrip(" ")
    return tokens


def _seg_runs(line: str):
    """Yield (text_run, use_cjk) segments of a line for fallback rendering."""
    if not line:
        return
    cjk = _is_cjk(line[0])
    start = 0
    for i, ch in enumerate(line):
        if _is_cjk(ch) != cjk:
            yield line[start:i], cjk
            start, cjk = i, _is_cjk(ch)
    yield line[start:], cjk


def _font_for(base, cjk, use_cjk: bool):
    return cjk if (use_cjk and cjk is not None) else base


def _line_width(line: str, fonts) -> float:
    base, cjk = fonts
    return sum(
        ImageDraw.Draw(Image.new("RGBA", (8, 8))).textlength(run, font=_font_for(base, cjk, u))
        for run, u in _seg_runs(line)
    )


def _wrap_to_width(text: str, fonts, draw, max_w: int) -> list[str]:
    """Greedy wrap so every line fits max_w pixels. Breaks CJK anywhere."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        cur = ""
        for tok in _tokenize(paragraph):
            while _line_width(tok, fonts) > max_w and len(tok) > 1:
                cut = len(tok)
                while cut > 1 and _line_width(tok[:cut], fonts) > max_w:
                    cut -= 1
                if cur.strip():
                    lines.append(cur.strip())
                cur = ""
                lines.append(tok[:cut])
                tok = tok[cut:]
            cand = (cur + tok) if cur else tok.lstrip(" ")
            if _line_width(cand, fonts) <= max_w:
                cur = cand
            else:
                if cur.strip():
                    lines.append(cur.strip())
                cur = tok.lstrip(" ")
        lines.append(cur.strip())
    return lines


def render_sticker(
    text: str,
    out_path: str,
    fg: str = "white",
    outline: str = "black",
    emoji: str | None = None,
) -> str:
    """Render text to a 512x512 WebP sticker at out_path. Returns out_path."""
    img = Image.new("RGBA", (STICKER_SIZE, STICKER_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    max_w = STICKER_SIZE - 48  # padding

    # Find the largest font size whose wrapped text fits the canvas.
    best_fonts, best_lines, best_h = None, None, None
    for size in range(120, 11, -2):
        fonts = _fonts_for(size)
        lines = _wrap_to_width(text, fonts, draw, max_w)
        line_h = fonts[0].getbbox("Ag")[3] - fonts[0].getbbox("Ag")[1] + int(size * 0.25)
        if line_h * len(lines) <= STICKER_SIZE - 48 and lines:
            best_fonts, best_lines, best_h = fonts, lines, line_h
            break
    if best_lines is None:  # absurdly long text: smallest font, clip lines
        best_fonts = _fonts_for(12)
        best_lines = _wrap_to_width(text, best_fonts, draw, max_w)[:20]
        best_h = 15

    base, cjk = best_fonts
    y = (STICKER_SIZE - best_h * len(best_lines)) / 2
    stroke = max(2, base.size // 14)
    for line in best_lines:
        w = _line_width(line, best_fonts)
        x = (STICKER_SIZE - w) / 2
        for run, use_cjk in _seg_runs(line):
            f = _font_for(base, cjk, use_cjk)
            draw.text(
                (x, y), run, font=f, fill=fg,
                stroke_width=stroke, stroke_fill=outline,
            )
            x += draw.textlength(run, font=f)
        y += best_h

    img.save(out_path, "WEBP", quality=95, exact=True)

    # Telegram hard limit: 512 KB per sticker. Drop quality until under.
    q = 90
    while os.path.getsize(out_path) > 512 * 1024 and q > 10:
        img.save(out_path, "WEBP", quality=q)
        q -= 10
    return out_path


# ---------------------------------------------------------------- telegram


def _client(args):
    from telethon import TelegramClient

    api_id = int(os.environ.get("TG_API_ID") or args.api_id or 0)
    api_hash = os.environ.get("TG_API_HASH") or args.api_hash
    if not api_id or not api_hash:
        sys.exit(
            "Need Telegram API credentials. Get them free at https://my.telegram.org "
            "then pass --api-id/--api-hash or set TG_API_ID / TG_API_HASH."
        )
    return TelegramClient(args.session, api_id, api_hash)


async def _send_as_sticker(client, chat, text: str, emoji: str):
    with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as f:
        tmp = f.name
    try:
        render_sticker(text, tmp)
        # force_document=False -> Telegram treats the webp as a real sticker
        await client.send_file(chat, tmp, force_document=False)
    finally:
        os.unlink(tmp)


async def cmd_say(args):
    out = args.out
    if not out:
        out = tempfile.mktemp(suffix=".webp")
    render_sticker(args.text, out, fg=args.fg, outline=args.outline)
    print(f"sticker written: {out} ({os.path.getsize(out)} bytes)")
    if args.send:
        client = _client(args)
        async with client:
            chat = args.send  # username, phone, or "me" for Saved Messages
            await client.send_file(chat, out, force_document=False)
            print(f"sent as sticker to {chat}")


async def cmd_listen(args):
    client = _client(args)
    from telethon import events

    await client.start()
    me = await client.get_me()
    print(f"logged in as {me.first_name} (@{me.username})")

    saved = "me"

    @client.on(events.NewMessage(chats=saved))
    async def on_saved(event):
        """Anything you type into Saved Messages -> sticker."""
        if not event.message.message or event.message.message.startswith("/"):
            return
        text = event.message.message
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as f:
            tmp = f.name
        try:
            render_sticker(text, tmp)
            await client.send_file(saved, tmp, force_document=False)
            # optionally forward into the target group automatically
            if args.group:
                await client.send_file(args.group, tmp, force_document=False)
        finally:
            os.unlink(tmp)

    if args.group:

        @client.on(events.NewMessage(chats=args.group))
        async def on_group(event):
            """Text you post in the group gets replaced by a sticker."""
            if event.sender_id != me.id:
                return
            text = event.message.message
            if not text or text.startswith("/"):
                return
            with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as f:
                tmp = f.name
            try:
                render_sticker(text, tmp)
                await event.message.delete()
                await client.send_file(args.group, tmp, force_document=False)
            finally:
                os.unlink(tmp)

        print(f"relaying your text in '{args.group}' as stickers")

    print("listening in Saved Messages — send any text to get a sticker back.")
    print("Ctrl-C to stop.")
    await client.run_until_disconnected()


# ---------------------------------------------------------------- main


def main():
    p = argparse.ArgumentParser(description="text -> telegram sticker bypass")
    p.add_argument("--session", default="tgsticker", help="telethon session name")
    p.add_argument("--api-id", help="telegram api_id (or env TG_API_ID)")
    p.add_argument("--api-hash", help="telegram api_hash (or env TG_API_HASH)")
    sub = p.add_subparsers(dest="cmd", required=True)

    say = sub.add_parser("say", help="render one sticker (optionally send)")
    say.add_argument("text")
    say.add_argument("--out", help="output .webp path (default: temp file)")
    say.add_argument("--send", help="also send: username/phone/'me'")
    say.add_argument("--fg", default="white")
    say.add_argument("--outline", default="black")
    say.set_defaults(func=cmd_say)

    listen = sub.add_parser("listen", help="auto-convert your text to stickers")
    listen.add_argument(
        "--group",
        help="also auto-forward your Saved-Messages stickers here, and replace "
        "any plain text you post in this group with a sticker",
    )
    listen.set_defaults(func=cmd_listen)

    args = p.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
