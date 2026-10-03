"""Coleta prévia e leve de dados externos — clima, cotações e notícias (RSS).

Economia de tokens: o Gemini recebe apenas o texto sintetizado destes dados.
Todas as fontes são públicas e não exigem chave. Qualquer falha de rede
degrada para valor nulo/lista vazia — o briefing nunca deve travar por
causa de uma fonte externa.
"""

import asyncio
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Nexus-HUD/1.0"}
TIMEOUT = httpx.Timeout(9.0)

NEXUS_CITY = os.environ.get("NEXUS_CITY", "Novorizonte, MG")
NEXUS_LAT = os.environ.get("NEXUS_LAT", "-20.7458")
NEXUS_LON = os.environ.get("NEXUS_LON", "-46.9289")

WMO_CODES: dict[int, str] = {
    0: "céu limpo", 1: "predomínio de sol", 2: "parcialmente nublado",
    3: "nublado", 45: "nevoeiro", 48: "nevoeiro com geada",
    51: "garoa fraca", 53: "garoa moderada", 55: "garoa intensa",
    61: "chuva fraca", 63: "chuva moderada", 65: "chuva forte",
    66: "chuva congelante", 67: "chuva congelante forte",
    71: "neve fraca", 73: "neve moderada", 75: "neve intensa",
    80: "pancadas isoladas", 81: "pancadas moderadas", 82: "pancadas violentas",
    95: "tempestade", 96: "tempestade com granizo", 99: "tempestade severa com granizo",
}

# Cada categoria tenta fontes oficiais primeiro e completa com busca de notícia (Google News RSS).
FEEDS: dict[str, list[tuple[str, str]]] = {
    "saude": [
        ("G1 Saúde", "https://g1.globo.com/rss/g1/saude/"),
        ("Google News Saúde", "https://news.google.com/rss/search?q=sa%C3%BAde+medicina+pesquisa+cient%C3%ADfica&hl=pt-BR&gl=BR&ceid=BR%3Apt-419"),
    ],
    "lgbtqia": [
        ("Google News LGBTQIA+", "https://news.google.com/rss/search?q=direitos+lgbtqia+OR+%22comunidade+lGBT%22&hl=pt-BR&gl=BR&ceid=BR%3Apt-419"),
    ],
    "politica": [
        ("G1 Política", "https://g1.globo.com/rss/g1/politica/"),
        ("Google News Política", "https://news.google.com/rss/search?q=pol%C3%ADtica+governo+congresso&hl=pt-BR&gl=BR&ceid=BR%3Apt-419"),
    ],
    "tecnologia": [
        ("G1 Tecnologia", "https://g1.globo.com/rss/g1/tecnologia/"),
        ("Google News Tecnologia", "https://news.google.com/rss/search?q=tecnologia+%22intelig%C3%AAncia+artificial%22&hl=pt-BR&gl=BR&ceid=BR%3Apt-419"),
    ],
}


async def get_weather(client: httpx.AsyncClient) -> dict[str, Any] | None:
    """Open-Meteo — sem chave. Coordenadas de Novorizonte-MG vindas do .env."""
    try:
        resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": NEXUS_LAT,
                "longitude": NEXUS_LON,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "America/Sao_Paulo",
                "forecast_days": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        cur = data.get("current", {})
        daily = data.get("daily", {})
        code = int(cur.get("weather_code") or 0)
        return {
            "city": NEXUS_CITY,
            "temperature": cur.get("temperature_2m"),
            "apparent": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "condition": WMO_CODES.get(code, "condição indefinida"),
            "temp_min": (daily.get("temperature_2m_min") or [None])[0],
            "temp_max": (daily.get("temperature_2m_max") or [None])[0],
            "rain_prob": (daily.get("precipitation_probability_max") or [None])[0],
        }
    except Exception as exc:
        logger.warning("coleta de clima falhou: %s", exc)
        return None


async def _finance_fallback(client: httpx.AsyncClient) -> dict[str, Any] | None:
    """Frankfurter (USD/EUR→BRL, cotação BCE) + CoinGecko (BTC→BRL) — sem chave."""
    try:
        start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        usd_resp = await client.get(f"https://api.frankfurter.app/{start}..?from=USD&to=BRL")
        eur_resp = await client.get(f"https://api.frankfurter.app/{start}..?from=EUR&to=BRL")
        usd_resp.raise_for_status()
        eur_resp.raise_for_status()

        def series(data: dict[str, Any]) -> dict[str, float] | None:
            rates = {day: float(node["BRL"]) for day, node in (data.get("rates") or {}).items() if node.get("BRL")}
            days = sorted(rates)
            if not days:
                return None
            latest = rates[days[-1]]
            previous = rates[days[-2]] if len(days) >= 2 else latest
            pct = (latest - previous) / previous * 100 if previous else 0.0
            return {"bid": latest, "pct": round(pct, 2)}

        usd = series(usd_resp.json())
        if not usd:
            return None
        eur = series(eur_resp.json())
        btc: dict[str, float] | None = None
        try:
            btc_resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "brl", "include_24hr_change": "true"},
            )
            node = (btc_resp.json().get("bitcoin") or {}) if btc_resp.status_code == 200 else {}
            if node.get("brl"):
                btc = {"bid": float(node["brl"]), "pct": round(float(node.get("brl_24h_change") or 0), 2)}
        except Exception as exc:
            logger.warning("coleta de BTC falhou: %s", exc)
        return {"usd": usd, "eur": eur, "btc": btc}
    except Exception as exc:
        logger.warning("fallback de finanças falhou: %s", exc)
        return None


async def get_finance(client: httpx.AsyncClient) -> dict[str, Any] | None:
    """AwesomeAPI primeiro; se a cota estourar, fallback Frankfurter + CoinGecko."""
    primary: dict[str, Any] | None = None
    try:
        resp = await client.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-BRL")
        resp.raise_for_status()
        data = resp.json()

        def entry(key: str) -> dict[str, float] | None:
            raw = data.get(key) or {}
            try:
                return {"bid": float(raw["bid"]), "pct": float(raw.get("pctChange") or 0)}
            except (KeyError, TypeError, ValueError):
                return None

        usd, eur, btc = entry("USDBRL"), entry("EURBRL"), entry("BTCBRL")
        if usd:
            primary = {"usd": usd, "eur": eur, "btc": btc}
    except Exception as exc:
        logger.warning("coleta de finanças falhou: %s", exc)
    return primary or await _finance_fallback(client)


def _parse_feed(xml_text: str, fallback_source: str, limit: int) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("RSS inválido (%s): %s", fallback_source, exc)
        return []
    items: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = re.sub(r"\s+", " ", (item.findtext("title") or "")).strip()
        if not title:
            continue
        # findtext("source") já devolve o TEXTO do elemento <source> (str), não o elemento.
        src_text = (item.findtext("source") or "").strip()
        items.append({
            "title": title,
            "source": src_text or fallback_source,
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
        })
        if len(items) >= limit:
            break
    return items


async def _fetch_feed(client: httpx.AsyncClient, category: str, label: str, url: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        resp = await client.get(url, headers=UA)
        resp.raise_for_status()
        return category, _parse_feed(resp.text, label, 6)
    except Exception as exc:
        logger.warning("feed %s (%s): %s", category, label, exc)
        return category, []


async def get_news(client: httpx.AsyncClient, per_category: int = 4) -> dict[str, list[dict[str, Any]]]:
    tasks = [(cat, label, url) for cat, feeds in FEEDS.items() for label, url in feeds]
    results = await asyncio.gather(*(_fetch_feed(client, cat, label, url) for cat, label, url in tasks))
    merged: dict[str, list[dict[str, Any]]] = {cat: [] for cat in FEEDS}
    for cat, items in results:
        merged[cat].extend(items)
    out: dict[str, list[dict[str, Any]]] = {}
    for cat, items in merged.items():
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            key = item["title"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        out[cat] = unique[:per_category]
    return out


async def collect_all() -> dict[str, Any]:
    """Coleta paralela de todas as fontes. Nunca levanta — falhas viram None/lista vazia."""
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        weather, finance, news = await asyncio.gather(
            get_weather(client), get_finance(client), get_news(client)
        )
    return {
        "weather": weather,
        "finance": finance,
        "news": news,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }