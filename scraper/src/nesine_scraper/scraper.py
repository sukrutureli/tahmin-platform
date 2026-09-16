import json
import time
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout
from urllib3.util.retry import Retry

URL = "https://bulten.nesine.com/api/bulten/getprebultenfull"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Authorization": "Basic RDQ3MDc4RDMtNjcwQi00OUJBLTgxNUYtM0IyMjI2MTM1MTZCOkI4MzJCQjZGLTQwMjgtNDIwNS05NjFELTg1N0QxRTZEOTk0OA==",
    "Referer": "https://www.nesine.com/",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = (10, 60)

FOOTBALL_TYPE = 1
BASKETBALL_TYPE = 2

DETAIL_URL_TEMPLATE = "https://istatistik.nesine.com/{event_id}"


def _normalize_date(date_str: str) -> str:
    parts = date_str.split(".")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str


def _build_detail_url(event_id: Any) -> str:
    if event_id is None:
        return ""
    return DETAIL_URL_TEMPLATE.format(event_id=event_id)


def _safe_odd(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        v = float(value)
        # Nesine bazı marketlerde 1.00'ı ekranda "-" gibi gösteriyor
        if v <= 1.0:
            return 0.0
        return v
    except Exception:
        return 0.0


def _build_session() -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=5)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)

    return session


def _download_payload() -> Dict[str, Any]:
    last_error = None

    for attempt in range(1, 6):
        session = _build_session()
        try:
            response = session.get(URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()

        except (ChunkedEncodingError, ConnectionError, ReadTimeout, json.JSONDecodeError) as exc:
            last_error = exc
            print(f"⚠️ İstek denemesi başarısız ({attempt}/5): {type(exc).__name__} - {exc}")
            time.sleep(attempt * 2)

        finally:
            session.close()

    raise RuntimeError(f"Nesine verisi alınamadı. Son hata: {last_error}")


def _extract_mbs(markets: List[Dict[str, Any]]) -> int:
    for market in markets:
        try:
            mbs = market.get("MBS")
            if mbs is not None:
                return int(mbs)
        except Exception:
            pass
    return 0


def _extract_football_odds(markets: List[Dict[str, Any]]) -> Dict[str, float]:
    odds = {
        "ms1": 0.0,
        "ms0": 0.0,
        "ms2": 0.0,
        "alt": 0.0,
        "ust": 0.0,
        "var": 0.0,
        "yok": 0.0,
    }

    for market in markets:
        mtid = market.get("MTID")
        sov = market.get("SOV")
        oca = market.get("OCA", [])

        if not isinstance(oca, list):
            continue

        if mtid == 1:
            for option in oca:
                n = option.get("N")
                o = _safe_odd(option.get("O"))
                if n == 1:
                    odds["ms1"] = o
                elif n == 2:
                    odds["ms0"] = o
                elif n == 3:
                    odds["ms2"] = o

        elif mtid == 12 and str(sov) == "2.5":
            for option in oca:
                n = option.get("N")
                o = _safe_odd(option.get("O"))
                if n == 1:
                    odds["alt"] = o
                elif n == 2:
                    odds["ust"] = o

        elif mtid == 38:
            for option in oca:
                n = option.get("N")
                o = _safe_odd(option.get("O"))
                if n == 1:
                    odds["var"] = o
                elif n == 2:
                    odds["yok"] = o

    return odds

def _pick_most_balanced_market(markets: List[Dict[str, Any]], target_mtid: int) -> Dict[str, Any] | None:
    candidates = []

    for market in markets:
        if market.get("MTID") != target_mtid:
            continue

        oca = market.get("OCA", [])
        if not isinstance(oca, list) or len(oca) < 2:
            continue

        odd1 = None
        odd2 = None

        for option in oca:
            n = option.get("N")
            o = _safe_odd(option.get("O"))

            if n == 1:
                odd1 = o
            elif n == 2:
                odd2 = o

        if odd1 is None or odd2 is None or odd1 <= 0 or odd2 <= 0:
            continue

        diff = abs(odd1 - odd2)

        try:
            sov = float(market.get("SOV", 0))
        except Exception:
            sov = 0.0

        candidates.append((diff, abs(sov), market))
        # diff küçük olan daha iyi
        # eşitse merkeze yakın olsun diye |sov| küçük olan öne gelsin

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]

def _extract_basketball_odds(markets: List[Dict[str, Any]]) -> Dict[str, float]:
    odds = {
        "ms1": 0.0,
        "ms2": 0.0,
        "h1Value": 0.0,
        "h1": 0.0,
        "h2": 0.0,
        "h2Value": 0.0,
        "alt": 0.0,
        "limit": 0.0,
        "ust": 0.0,
    }

    # MS: burada genelde tek market yeterli
    for market in markets:
        mtid = market.get("MTID")
        oca = market.get("OCA", [])

        if mtid == 142 and isinstance(oca, list):
            for option in oca:
                n = option.get("N")
                o = _safe_odd(option.get("O"))
                if n == 1:
                    odds["ms1"] = o
                elif n == 2:
                    odds["ms2"] = o
            break

    # Alt/Üst: en dengeli baremi seç
    total_market = _pick_most_balanced_market(markets, 149)
    if total_market:
        try:
            odds["limit"] = float(total_market.get("SOV", 0))
        except Exception:
            odds["limit"] = 0.0

        for option in total_market.get("OCA", []):
            n = option.get("N")
            o = _safe_odd(option.get("O"))
            if n == 1:
                odds["alt"] = o
            elif n == 2:
                odds["ust"] = o

    # Handikap: en dengeli baremi seç
    handicap_market = _pick_most_balanced_market(markets, 144)
    if handicap_market:
        try:
            line = float(handicap_market.get("SOV", 0))
        except Exception:
            line = 0.0

        odds["h1Value"] = line
        odds["h2Value"] = -line

        for option in handicap_market.get("OCA", []):
            n = option.get("N")
            o = _safe_odd(option.get("O"))
            if n == 1:
                odds["h1"] = o
            elif n == 2:
                odds["h2"] = o

    return odds


def _build_football_match(event: Dict[str, Any], normalized_date: str) -> Dict[str, Any]:
    event_id = event.get("C")
    home = event.get("HN") or ""
    away = event.get("AN") or ""
    markets = event.get("MA", [])

    core_odds = _extract_football_odds(markets)

    return {
        "event_id": event_id,
        "league_code": event.get("LC"),
        "date": normalized_date,
        "time": event.get("T") or "",
        "day": event.get("DAY") or "",
        "name": event.get("ENO") or f"{home} - {away}",
        "home": home,
        "away": away,
        "url": _build_detail_url(event_id),
        "mbs": _extract_mbs(markets),
        "ms1": core_odds["ms1"],
        "ms0": core_odds["ms0"],
        "ms2": core_odds["ms2"],
        "alt": core_odds["alt"],
        "ust": core_odds["ust"],
        "var": core_odds["var"],
        "yok": core_odds["yok"],
    }


def _build_basketball_match(event: Dict[str, Any], normalized_date: str) -> Dict[str, Any]:
    event_id = event.get("C")
    home = event.get("HN") or ""
    away = event.get("AN") or ""
    markets = event.get("MA", [])

    core_odds = _extract_basketball_odds(markets)

    return {
        "event_id": event_id,
        "league_code": event.get("LC"),
        "date": normalized_date,
        "time": event.get("T") or "",
        "day": event.get("DAY") or "",
        "name": event.get("ENO") or f"{home} - {away}",
        "home": home,
        "away": away,
        "url": _build_detail_url(event_id),
        "mbs": _extract_mbs(markets),
        "ms1": core_odds["ms1"],
        "ms2": core_odds["ms2"],
        "h1Value": core_odds["h1Value"],
        "h1": core_odds["h1"],
        "h2": core_odds["h2"],
        "h2Value": core_odds["h2Value"],
        "alt": core_odds["alt"],
        "limit": core_odds["limit"],
        "ust": core_odds["ust"],
    }


def fetch_football_matches(date_str: str) -> List[Dict[str, Any]]:
    payload = _download_payload()
    events = payload.get("sg", {}).get("EA", [])
    matches: List[Dict[str, Any]] = []

    for event in events:
        if event.get("TYPE") != FOOTBALL_TYPE:
            continue

        raw_date = event.get("D")
        normalized_date = _normalize_date(raw_date) if raw_date else None
        if normalized_date != date_str:
            continue

        home = event.get("HN")
        away = event.get("AN")
        if not home or not away:
            continue

        matches.append(_build_football_match(event, normalized_date))

    matches.sort(key=lambda x: (x.get("time") or "", x.get("name") or ""))
    return matches


def fetch_basketball_matches(date_str: str) -> List[Dict[str, Any]]:
    payload = _download_payload()
    events = payload.get("sg", {}).get("EA", [])
    matches: List[Dict[str, Any]] = []

    for event in events:
        if event.get("TYPE") != BASKETBALL_TYPE:
            continue

        raw_date = event.get("D")
        normalized_date = _normalize_date(raw_date) if raw_date else None
        if normalized_date != date_str:
            continue

        home = event.get("HN")
        away = event.get("AN")
        if not home or not away:
            continue

        matches.append(_build_basketball_match(event, normalized_date))

    matches.sort(key=lambda x: (x.get("time") or "", x.get("name") or ""))
    return matches
