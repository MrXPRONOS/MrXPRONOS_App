"""Free and public news inputs for Mr XPRONOS #08 and #09.

Editorial RSS sources remain independent only when their publishers differ.
First-party status APIs are official incident records, NOT independent press.
Access does not imply publication/syndication rights; keep attribution/link.
"""
from __future__ import annotations

EDITORIAL_FEEDS = {
    "CoinDesk": ("https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml", "coindesk.com"),
    "Cointelegraph": ("https://cointelegraph.com/rss", "cointelegraph.com"),
    "The Block": ("https://www.theblock.co/rss.xml", "theblock.co"),
    "Decrypt": ("https://decrypt.co/feed", "decrypt.co"),
    "Blockworks": ("https://blockworks.co/feed", "blockworks.co"),
    "BeInCrypto": ("https://beincrypto.com/feed/", "beincrypto.com"),
    "Bitcoin Magazine": ("https://bitcoinmagazine.com/feed", "bitcoinmagazine.com"),
    "NewsBTC": ("https://www.newsbtc.com/feed/", "newsbtc.com"),
}

# Official, public Atlassian Statuspage JSON REST endpoints; no API key.
# Records are about platform functionality, not general news.
OFFICIAL_STATUS_APIS = {
    "Coinbase Status": ("https://status.coinbase.com/api/v2/incidents.json",
                        "status.coinbase.com", "COINBASE"),
    "Kraken Status": ("https://status.kraken.com/api/v2/incidents.json",
                      "status.kraken.com", "KRAKEN"),
}


# Independent public RSS publishers used by the global 30-minute news desk.
# An unavailable source is logged and skipped. No feed access implies republication rights.
# URLs were checked against published RSS directories in November 2026; the
# automated pipeline validates their reachability and article domains on every scan.
FRENCH_NEWS_FEEDS = frozenset({"Journal du Coin", "Cryptoast"})

GLOBAL_NEWS_FEEDS = {
    **EDITORIAL_FEEDS,
    "CryptoSlate": ("https://cryptoslate.com/feed/", "cryptoslate.com"),
    "Bitcoin.com News": ("https://news.bitcoin.com/feed/", "news.bitcoin.com"),
    "CryptoPotato": ("https://cryptopotato.com/feed/", "cryptopotato.com"),
    "Crypto Briefing": ("https://cryptobriefing.com/feed/", "cryptobriefing.com"),
    "Cryptonews": ("https://cryptonews.com/news/feed", "cryptonews.com"),
    "Journal du Coin": ("https://journalducoin.com/feed/", "journalducoin.com"),
    "Cryptoast": ("https://cryptoast.fr/feed/", "cryptoast.fr"),
}
