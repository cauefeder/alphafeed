"""Category → keyword definitions for poly2_export.

Pure data, no logic. Imported by poly2_export.py. Edit a keyword list to
change which markets get classified into which bucket; no need to touch
the export pipeline.
"""

from __future__ import annotations

from typing import TypedDict


class CategorySpec(TypedDict):
    name: str
    emoji: str
    keywords: list[str]


CATEGORIES: dict[str, CategorySpec] = {
    "macro": {
        "name": "Macroeconomics",
        "emoji": "📊",
        "keywords": [
            "fed", "federal reserve", "interest rate", "rate cut", "rate hike",
            "inflation", "cpi", "pce", "gdp", "recession", "unemployment",
            "jobs", "nonfarm", "payroll", "treasury", "yield", "bond",
            "debt ceiling", "government shutdown", "deficit", "tariff",
            "trade war", "sanctions", "ecb", "bank of japan", "boj",
            "bank of england", "imf", "world bank", "core inflation",
            "consumer price", "producer price", "ppi", "retail sales",
            "housing", "mortgage", "real estate", "home price",
            "manufacturing", "pmi", "ism", "consumer confidence",
            "wage growth", "labor market", "initial claims",
            "quantitative", "balance sheet", "fomc", "dot plot",
            "soft landing", "hard landing", "stagflation",
        ],
    },
    "geopolitics": {
        "name": "Geopolitics & Global Affairs",
        "emoji": "🌍",
        "keywords": [
            "war", "ukraine", "russia", "china", "taiwan", "nato",
            "iran", "israel", "gaza", "hamas", "hezbollah", "north korea",
            "missile", "nuclear", "ceasefire", "peace", "invasion",
            "coup", "regime", "diplomacy", "summit",
            "united nations", "european union", "brexit",
            "middle east", "india", "modi", "xi jinping",
            "putin", "zelensky", "military", "troops", "border",
            "strike", "airstrike", "bomb", "attack", "conflict",
            "houthi", "yemen", "syria", "iraq", "saudi",
            "arms", "weapon", "defense", "pentagon", "escalat",
        ],
    },
    "crypto": {
        "name": "Crypto & Digital Assets",
        "emoji": "₿",
        "keywords": [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "sol",
            "xrp", "dogecoin", "doge", "defi", "nft", "stablecoin",
            "usdc", "usdt", "binance", "coinbase", "sec crypto",
            "bitcoin etf", "halving", "mining", "blockchain",
            "memecoin", "altcoin", "token",
        ],
    },
    "stocks": {
        "name": "Stocks & Traditional Assets",
        "emoji": "📈",
        "keywords": [
            "s&p", "sp500", "nasdaq", "dow jones", "stock", "equity",
            "earnings", "revenue", "ipo", "market cap",
            "oil", "gold", "silver", "commodity", "wti", "brent",
            "apple", "nvidia", "tesla", "microsoft", "amazon", "google",
            "meta", "netflix", "spy", "qqq",
        ],
    },
    "ai_tech": {
        "name": "AI & Technology",
        "emoji": "🤖",
        "keywords": [
            "openai", "anthropic", "google ai", "deepmind", "claude",
            "gpt", "gemini", "llama", "ai model", "artificial intelligence",
            "agi", "machine learning", "chatbot", "ai regulation",
            "ai safety", "chips act", "semiconductor", "tsmc",
            "ai act", "compute", "data center",
        ],
    },
    "politics": {
        "name": "US & Global Politics",
        "emoji": "🏛️",
        "keywords": [
            "trump", "biden", "harris", "republican", "democrat",
            "congress", "senate", "house", "election", "poll",
            "impeach", "supreme court", "executive order", "veto",
            "governor", "mayor", "primary", "nominee", "campaign",
            "doge ", "elon musk", "musk", "cabinet", "secretary",
            "fbi", "doj", "cia", "pardon", "indictment",
            "uk election", "france", "macron", "germany", "canada",
            "trudeau", "brazil", "lula", "mexico", "president",
        ],
    },
}
