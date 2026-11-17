"""Verified publisher photography + rich, link-free Telegram captions for #11.

Never send a fabricated poster or use arbitrary unverified images for news.
Article images come from the publisher RSS media or its article's og:image.
Remote URLs are restricted to public HTTPS; responses are bounded and decoded.
"""
from __future__ import annotations

from html import escape, unescape
from html.parser import HTMLParser
from io import BytesIO
import ipaddress
from pathlib import Path
import re
import socket
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

OUTPUT = Path("crypto/generated/test/news_v1_article.jpg")
MAX_IMAGE_BYTES = 6_000_000
MAX_ARTICLE_BYTES = 500_000
MAX_IMAGE_CANDIDATES = 7
Image.MAX_IMAGE_PIXELS = 30_000_000


class MediaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []
        self.og_images = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "img":
            url = d.get("src") or d.get("data-src") or d.get("data-original")
            if url:
                self.images.append(unescape(url.strip()))
        elif tag == "meta":
            key = (d.get("property") or d.get("name") or "").lower()
            if key in ("og:image", "og:image:secure_url", "twitter:image"):
                content = d.get("content")
                if content:
                    self.og_images.append(unescape(content.strip()))


def safe_https_shape(url):
    """Reject credentials, IP literals, local domains and non-HTTPS ports."""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or not host or parsed.username
                or parsed.password or parsed.port not in (None, 443)
                or len(url) > 1600 or re.search(r"[\s\x00-\x1f]", url)):
            return False
        if host.lower() == "localhost" or "." not in host:
            return False
        if host.endswith((".local", ".internal", ".test", ".localhost")):
            return False
        try:
            ipaddress.ip_address(host)
            return False  # all IP literals excluded, including public ones
        except ValueError:
            pass
        return bool(re.fullmatch(r"[a-zA-Z0-9.-]+", host))
    except (ValueError, TypeError):
        return False


def public_https(url):
    if not isinstance(url, str) or not safe_https_shape(url):
        return False
    host = urlsplit(url).hostname
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        return False
    return bool(answers) and all(
        ipaddress.ip_address(answer[4][0]).is_global for answer in answers
    )


def unique_urls(candidates, base):
    seen = set()
    for raw in candidates:
        if not isinstance(raw, str):
            continue
        url = urljoin(base, unescape(raw.strip()))
        if url not in seen and safe_https_shape(url):
            seen.add(url)
            yield url


def images_from_rss(entry, article_url):
    """Extract only images explicitly attached to THIS RSS article."""
    possibles = []
    for key in ("media_content", "media_thumbnail", "enclosures", "links"):
        for e in entry.get(key) or []:
            if not isinstance(e, dict):
                continue
            mime = str(e.get("type") or "").lower()
            medium = str(e.get("medium") or "").lower()
            if key == "media_thumbnail" or mime.startswith("image/") or medium == "image":
                possibles.append(e.get("url") or e.get("href"))
            elif key == "media_content" and not mime and not medium:
                possibles.append(e.get("url"))
    for key in ("summary", "description"):
        if entry.get(key):
            p = MediaParser()
            p.feed(str(entry[key])[:120_000])
            possibles.extend(p.images[:3])
    for body in (entry.get("content") or [])[:2]:
        if isinstance(body, dict):
            p = MediaParser()
            p.feed(str(body.get("value") or "")[:120_000])
            possibles.extend(p.images[:3])
    return list(unique_urls(possibles, article_url))[:MAX_IMAGE_CANDIDATES]


def og_images(article_html, article_url):
    p = MediaParser()
    p.feed(article_html[:MAX_ARTICLE_BYTES])
    return list(unique_urls(p.og_images, article_url))[:3]


def from_article_og(article_url, getter=requests.get):
    """Use the actual article's OpenGraph image only when RSS media is absent."""
    if not public_https(article_url):
        return []
    try:
        r = getter(article_url, headers={"User-Agent": "Mozilla/5.0 (MrXPRONOS News)" ,
                                         "Accept": "text/html"},
                   timeout=(5, 10), allow_redirects=False, stream=True)
        with r:
            if r.status_code != 200 or "html" not in r.headers.get("content-type", "").lower():
                return []
            if int(r.headers.get("content-length") or "0") > MAX_ARTICLE_BYTES:
                return []
            body = bytearray()
            for chunk in r.iter_content(32768):
                body.extend(chunk)
                if len(body) > MAX_ARTICLE_BYTES:
                    return []
            return og_images(body.decode("utf-8", errors="replace"), article_url)
    except (requests.RequestException, ValueError, OSError):
        return []


def fetch_photo(url, dest=OUTPUT, getter=requests.get):
    """Decode actual article photograph; never invent or replace with poster."""
    if not public_https(url):
        return None
    try:
        r = getter(url, headers={"User-Agent": "Mozilla/5.0 (MrXPRONOS News)",
                                 "Accept": "image/avif,image/webp,image/jpeg,image/png"},
                   timeout=(5, 12), stream=True, allow_redirects=False)
        with r:
            if r.status_code != 200:
                return None
            content_type = r.headers.get("content-type", "").lower().split(";")[0].strip()
            if not content_type.startswith("image/"):
                return None
            if int(r.headers.get("content-length") or "0") > MAX_IMAGE_BYTES:
                return None
            data = bytearray()
            for chunk in r.iter_content(32768):
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    return None
        if len(data) < 2000:
            return None
        with Image.open(BytesIO(data)) as img:
            if img.width < 400 or img.height < 200:
                return None
            if img.width * img.height > 30_000_000:
                return None
            # Keep proportions and the publisher's photograph without overlays.
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, format="JPEG", quality=88, optimize=True)
        if dest.stat().st_size < 10000:
            dest.unlink(missing_ok=True)
            return None
        return dest
    except (requests.RequestException, OSError, ValueError,
            UnidentifiedImageError, Image.DecompressionBombError):
        return None


def photo_for(candidate, dest=OUTPUT):
    """A news item is not published if no verifiable original image was found."""
    # The lead publisher must be attributed. Supporting publisher image
    # is allowed only with explicit attribution to that publisher.
    articles = [candidate["main"]] + list(candidate.get("others") or [])
    for row in articles:
        urls = list(row.get("image_candidates") or [])
        for uri in urls[:MAX_IMAGE_CANDIDATES]:
            path = fetch_photo(uri, dest)
            if path is not None:
                return path, row["source"]
        # RSS thumbnails may be broken; try this article's own og:image.
        for uri in from_article_og(row["url"]):
            if uri in urls:
                continue
            path = fetch_photo(uri, dest)
            if path is not None:
                return path, row["source"]
    return None


def no_links(value, max_chars=240):
    value = re.sub(r"(?i)(?:https?://|www\.)\S+", "", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_chars].strip()


def caption(candidate, image_source=None):
    """Telegram HTML: bold, italic, native blockquote; no links or clickable URLs."""
    main = candidate["main"]
    source = no_links(main["source"], 60)
    image_source = no_links(image_source or source, 60)
    category = no_links(main.get("category") or "ACTUALITÉ CRYPTO", 40)
    title = no_links(main["title"], 185)
    summary = no_links(main.get("summary"), 330)
    if not title:
        raise ValueError("Headline missing")
    # A concise, attributable quote, not an invented interpretation.
    quote = summary if summary and summary.casefold() != title.casefold() else title
    if len(quote) < 25:
        quote = title
    html_caption = (
        "📰 <b>ACTU CRYPTO</b>  |  <i>" + escape(category) + "</i>\n\n"
        + "🔸 <b>" + escape(title) + "</b>\n\n"
        + "<blockquote>" + escape(quote) + "</blockquote>\n\n"
        + "🗞️ <i>Source : " + escape(source) + "</i>"
        + ("\n📷 <i>Image : " + escape(image_source) + "</i>"
           if image_source != source else "")
    )
    # Telegram photo captions have a 1024 char text+entity limit.
    if len(html_caption) > 1000:
        raise ValueError("News photo caption above Telegram limit")
    if re.search(r"(?i)https?://|www\.", html_caption):
        raise ValueError("Links are forbidden in public Telegram messages")
    return html_caption
