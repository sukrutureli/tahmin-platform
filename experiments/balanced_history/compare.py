"""Artifact-only experiment. No publishing, Telegram, or production mutations."""
import argparse
import copy
import hashlib
import html
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text())
MONTHS = {name: i + 1 for i, name in enumerate(
    "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split())}
FINISHED = {5, 9, 11}


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def parse_date(value):
    value = str(value or "").strip()
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    parts = value.split()
    if len(parts) == 3 and parts[1] in MONTHS:
        try:
            return date(int(parts[2]), MONTHS[parts[1]], int(parts[0]))
        except ValueError:
            pass
    return None


def event_id(info):
    found = re.search(r"nesine\.com/(?:p1/)?(\d+)", info.get("detailUrl", ""))
    if not found:
        raise ValueError("Missing event ID: " + str(info))
    return found.group(1)


def friendly(name):
    return any(w in str(name).casefold() for w in ("hazırlık", "friendly", "preseason"))


class RateLimitError(RuntimeError):
    pass


class Client:
    def __init__(self, cache):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.last_request = 0
        self.audit = []

    def get(self, url, account=None, text=False):
        key = hashlib.sha256((url + str(account)).encode()).hexdigest()
        target = self.cache / (key + (".txt" if text else ".json"))
        if target.exists():
            content = target.read_text()
            return content if text else json.loads(content)
        headers = {"Accept": "application/json", "User-Agent": "PredictionComparison/1.0"}
        if account:
            headers.update({"x-brdg": account, "Origin": "https://istatistik.nesine.com",
                            "Referer": "https://istatistik.nesine.com/"})
        for attempt in range(3):
            time.sleep(max(0, CONFIG["request_interval_seconds"] - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
                    content = response.read().decode("utf-8")
                value = content if text else json.loads(content)
                target.write_text(content)
                self.audit.append({"url": url, "cache": target.name, "status": 200})
                return value
            except urllib.error.HTTPError as error:
                self.audit.append({"url": url, "status": error.code, "attempt": attempt + 1})
                if error.code == 429:
                    # Stop the entire experiment; do not evade quotas or export partial predictions.
                    raise RateLimitError("HTTP 429: experiment stopped: " + url) from error
                if error.code not in (502, 503, 504) or attempt == 2:
                    raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
            time.sleep(1 + attempt)
        raise RuntimeError("Unreachable retry state")


def flatten(items):
    for item in items or []:
        if isinstance(item, list):
            yield from flatten(item)
        elif isinstance(item, dict):
            yield item


def schedule_row(row, cutoff, sport):
    """Team schedule's team is the OPPONENT; teamType belongs to that opponent."""
    played = parse_date(row.get("date"))
    state = row.get("status", {}).get("id")
    if not played or played >= cutoff or state not in FINISHED:
        return None
    if sport == "basketball" and state == 11:
        return None
    opponent_side = row.get("teamType")
    if opponent_side not in ("home", "away"):
        return None
    side = "away" if opponent_side == "home" else "home"
    other = "away" if side == "home" else "home"
    scores = row.get("scores", {})
    own, opp = scores.get(side, {}), scores.get(other, {})
    regulation_key = "ordinary"
    if sport == "basketball":
        regulation_key = next((k for k in ("ordinary", "regularTime", "regular") if k in own and k in opp), "ordinary")
    # An overtime row without explicit regulation cannot safely enter regulation averages.
    if state != 5 and (regulation_key not in own or regulation_key not in opp):
        return None
    gf, ga = own.get(regulation_key, own.get("current")), opp.get(regulation_key, opp.get("current"))
    ff, fa = own.get("current"), opp.get("current")
    if not all(isinstance(x, (int, float)) and x >= 0 for x in (gf, ga, ff, fa)):
        return None
    if sport == "basketball" and ff == fa:
        return None
    tournament = row.get("tournament", {})
    return {"id": "broadage:" + str(row["id"]), "date": played.isoformat(), "venue": side,
            "for": gf, "against": ga, "finalFor": ff, "finalAgainst": fa,
            "win": int(ff > fa), "draw": int(ff == fa), "regulationKnown": True,
            "tournament": tournament.get("name", ""), "tournamentId": tournament.get("id"),
            "opponent": row.get("team", {}).get("name", ""), "source": "broadage-team-schedule"}


def archived_rows(rows, team, cutoff, sport):
    result = []
    for row in rows:
        played = parse_date(row.get("matchDate"))
        if not played or played >= cutoff or row.get("status", "finished") != "finished":
            continue
        if row.get("homeTeam") == team:
            side, gf, ga = "home", row["homeScore"], row["awayScore"]
        elif row.get("awayTeam") == team:
            side, gf, ga = "away", row["awayScore"], row["homeScore"]
        else:
            continue
        key = "|".join(str(row.get(k)) for k in ("matchDate", "homeTeam", "awayTeam"))
        # Archive basketball stores regulation only; ties have UNKNOWN final outcome.
        known = sport != "basketball" or gf != ga
        result.append({"id": "archive:" + key, "date": played.isoformat(), "venue": side,
                       "for": gf, "against": ga, "finalFor": gf if known else None,
                       "finalAgainst": ga if known else None, "win": int(gf > ga) if known else None,
                       "draw": int(gf == ga) if known else None, "regulationKnown": True,
                       "tournament": row.get("tournament", ""), "tournamentId": None,
                       "opponent": row.get("awayTeam" if side == "home" else "homeTeam"),
                       "source": "archived-six"})
    return unique(result)


def unique(rows):
    return sorted({row["id"]: row for row in rows}.values(), key=lambda r: (r["date"], r["id"]), reverse=True)


def balanced_sample(rows, limit):
    rows = unique(rows)
    selected = rows[:limit]
    for venue in ("home", "away"):
        desired = min(4, sum(r["venue"] == venue for r in rows))
        for candidate in rows[limit:]:
            if sum(r["venue"] == venue for r in selected) >= desired:
                break
            if candidate["venue"] != venue:
                continue
            replace = next((r for r in reversed(selected) if r["venue"] != venue and
                            sum(x["venue"] == r["venue"] for x in selected) > 4), None)
            if replace:
                selected.remove(replace)
                selected.append(candidate)
                selected = unique(selected)
    return unique(selected)


class Collector:
    def __init__(self, client):
        self.client = client
        self.teams = {}
        self.config = None

    def summary_fallback(self, info, cutoff, sport):
        eid = event_id(info)
        base = "https://apistats.nesine.com/api/v3/HeadToHead/" + eid + "/"
        header = self.client.get(base + "Header")["d"]
        if header.get("SID") != (1 if sport == "football" else 2):
            raise ValueError("Nesine sport mismatch")
        summary = self.client.get(base + "Summary?competitionHistoryCount=6")["d"]
        ids = [header[k][0]["TID"] for k in ("HT", "AT")]
        output = []
        for tid in ids:
            rows = []
            for league in summary.get("SLM", {}).get("ML", []):
                for group in league.get("TT", []):
                    if group.get("FT") not in (5, 2):
                        continue
                    for team in group.get("TMS", []):
                        if team.get("TID") != tid:
                            continue
                        for row in team.get("ML", []):
                            played = parse_date(row.get("POFMD"))
                            if not played or played >= cutoff:
                                continue
                            scores = {s.get("OBI"):s for s in row.get("SC") or []}
                            regulation = scores.get(99 if sport == "football" else 45)
                            if not regulation:
                                continue
                            final = scores.get(1000, regulation) if sport == "basketball" else regulation
                            side = "home" if row.get("HT", {}).get("TID") == tid else "away" if row.get("AT", {}).get("TID") == tid else None
                            if side is None:
                                continue
                            own, other = ("HTS", "ATS") if side == "home" else ("ATS", "HTS")
                            values = [s.get(k) for s in (regulation,final) for k in (own,other)]
                            if not all(isinstance(v,(int,float)) and v >= 0 for v in values):
                                continue
                            gf,ga,ff,fa = values
                            known = sport != "basketball" or ff != fa
                            rows.append({"id":"nesine:"+str(row["MID"]),"date":played.isoformat(),"venue":side,
                                         "for":gf,"against":ga,"finalFor":ff if known else None,"finalAgainst":fa if known else None,
                                         "win":int(ff>fa) if known else None,"draw":int(ff==fa) if known else None,
                                         "regulationKnown":True,"tournament":row.get("LG",{}).get("N",""),
                                         "tournamentId":row.get("LG",{}).get("TID"),
                                         "opponent":row.get("AT" if side=="home" else "HT",{}).get("N",""),
                                         "source":"nesine-summary-general-and-venue"})
            output.append({"rows":unique(rows),"source":"nesine-summary-general-and-venue","teamId":tid})
        return output

    def collect(self, info, history, cutoff, sport):
        eid = event_id(info)
        page = self.client.get("https://istatistik.nesine.com/p1/" + eid, text=True)
        def field(key):
            found = re.search(r"model\." + key + r"\s*=\s*[\"']?([\w-]+)", page)
            if not found:
                raise ValueError("Missing p1 field: " + key)
            return found.group(1)
        account = field("AccountId")
        if int(field("SportId")) != (1 if sport == "football" else 2):
            raise ValueError("Broadage sport mismatch")
        if self.config is None:
            self.config = self.client.get("https://cdn-saas.broadage.com/config/config.json")
        prefix = self.config["accountMap"][account.upper()]
        base = "https://" + str(prefix) + ".rsc.cdn77.org/" + ("soccer" if sport == "football" else "basketball")
        result = []
        for key in ("HomeTeamId", "AwayTeamId"):
            tid = field(key)
            cache_key = (sport, tid, cutoff.isoformat())
            if cache_key not in self.teams:
                collected, raw_count = [], 0
                # Month navigation is supplied by the endpoint, not guessed pagination.
                query = {"teId": tid, "tId": 0, "calculation": "overall",
                         "options": json.dumps({"lang": "tr-TR", "timeZone": 3, "rowPerPage": 30}, separators=(",", ":"))}
                initial = self.client.get(base + "/widget/team/schedule?" + urllib.parse.urlencode(query), account)
                data = initial.get("data", {})
                metadata = data.get("metaData", {})
                if str(metadata.get("team", {}).get("id")) != tid:
                    raise ValueError("Team ID mismatch: " + tid)
                rounds = sorted({r["id"] for r in metadata.get("rounds", [])
                                 if isinstance(r.get("id"), int) and 190001 <= r["id"] <= cutoff.year * 100 + cutoff.month}, reverse=True)
                for i, month in enumerate(rounds[:CONFIG["max_months"]]):
                    selected = any(r.get("selected") and r.get("id") == month for r in metadata.get("rounds", []))
                    if selected:
                        monthly = data
                    else:
                        monthly = self.client.get(base + "/widget/team/schedule?" + urllib.parse.urlencode(dict(query, rId=month)), account).get("data", {})
                    for row in flatten(monthly.get("initialData")):
                        raw_count += 1
                        parsed = schedule_row(row, cutoff, sport)
                        if parsed:
                            collected.append(parsed)
                    collected = unique(collected)
                    limit = CONFIG[sport]["history_limit"]
                    if len(collected) >= limit and all(sum(r["venue"] == venue for r in collected) >= 6 for venue in ("home", "away")):
                        break
                self.teams[cache_key] = {"rows": collected, "monthsAvailable": len(rounds),
                                         "rawRows": raw_count, "teamId": tid, "source": "broadage-team-schedule"}
            selected = copy.deepcopy(self.teams[cache_key])
            selected["targetTournamentId"] = int(field("TournamentId"))
            result.append(selected)
        return result


def weight(row, cutoff, sport, tournament=None):
    age = (cutoff - date.fromisoformat(row["date"])).days
    w = 2 ** (-age / CONFIG[sport]["half_life_days"])
    if friendly(row["tournament"]):
        w *= CONFIG["friendly_weight"]
    elif tournament is not None and row.get("tournamentId") not in (None, tournament):
        w *= 0.7
    return w


def stats(rows, cutoff, sport, venue, tournament=None):
    rows = balanced_sample(rows, CONFIG[sport]["history_limit"])
    cfg = CONFIG[sport]
    prior = cfg["prior_strength"]
    weighted = [(r, weight(r, cutoff, sport, tournament)) for r in rows]
    sw = sum(w for _, w in weighted)
    ess = sw * sw / sum(w * w for _, w in weighted) if sw else 0
    def mean(field, selected, fallback, shrink=False):
        valid = [(r[field], w) for r, w in selected if r.get(field) is not None]
        denominator = sum(w for _, w in valid)
        numerator = sum(v * w for v, w in valid)
        return (numerator + (prior * fallback if shrink else 0)) / (denominator + (prior if shrink else 0)) if denominator or shrink else fallback
    general_for = mean("for", weighted, cfg["prior_for"], True)
    general_against = mean("against", weighted, cfg["prior_against"], True)
    venue_rows = [(r, w) for r, w in weighted if r["venue"] == venue]
    venue_for = mean("for", venue_rows, general_for, True)
    venue_against = mean("against", venue_rows, general_against, True)
    recent = weighted[:6]
    form_for = mean("for", recent, general_for, True)
    form_against = mean("against", recent, general_against, True)
    v, f = CONFIG["venue_fraction"], cfg["form_fraction"]
    gf = (1-v-f)*general_for + v*venue_for + f*form_for
    ga = (1-v-f)*general_against + v*venue_against + f*form_against
    points = [(dict(r, points=(3*r["win"] + r["draw"])/3 if sport == "football" else r["win"]), w)
              for r, w in weighted[:6] if r.get("win") is not None]
    form = mean("points", points, 0.5, True)
    official = sum(w for r, w in weighted if not friendly(r["tournament"])) / sw if sw else 0
    freshness = sw / len(rows) if rows else 0
    venue_support = min(1, sum(w for _, w in venue_rows)/5)
    quality = 100 * (0.35*min(ess/15, 1) + 0.35*min(freshness, 1) + 0.2*official + 0.1*venue_support)
    margin_mean = mean("margin", [(dict(r, margin=r["for"]-r["against"]), w) for r, w in weighted], 0)
    total_mean = mean("total", [(dict(r, total=r["for"]+r["against"]), w) for r, w in weighted], 2*cfg["prior_for"])
    margin_var = sum(w*(r["for"]-r["against"]-margin_mean)**2 for r, w in weighted)
    total_var = sum(w*(r["for"]+r["against"]-total_mean)**2 for r, w in weighted)
    ot = [(dict(r, overtime=max(0, r["finalFor"]+r["finalAgainst"]-r["for"]-r["against"])), w)
          for r, w in weighted if r.get("finalFor") is not None and r.get("finalAgainst") is not None]
    return {"for": gf, "against": ga, "form": form, "count": len(rows), "effectiveCount": ess,
            "weightedCount": sw, "venueCount": len(venue_rows), "quality": quality,
            "meanAgeDays": sum(w*(cutoff-date.fromisoformat(r["date"])).days for r, w in weighted)/sw if sw else None,
            "friendlyCount": sum(friendly(r["tournament"]) for r in rows),
            "unknownFinalCount": sum(r.get("win") is None for r in rows),
            "marginVariance": (margin_var+prior*144)/(sw+prior),
            "totalVariance": (total_var+prior*256)/(sw+prior),
            "overtime": mean("overtime", ot, 0, True), "rows": rows}


def devig(odds):
    if not all(isinstance(x, (int, float)) and math.isfinite(x) and x > 1 for x in odds):
        return None
    inverse = [1/x for x in odds]
    return [x/sum(inverse) for x in inverse]


def normal_cdf(x):
    return (1 + math.erf(x / math.sqrt(2))) / 2


def poisson_probabilities(home, away):
    def pmf(lam):
        result = [math.exp(-lam)]
        for i in range(1, 31):
            result.append(result[-1]*lam/i)
        return result
    h, a = pmf(home), pmf(away)
    ms = [sum(ph*pa for i, ph in enumerate(h) for j, pa in enumerate(a) if test(i, j))
          for test in (lambda i,j:i>j, lambda i,j:i==j, lambda i,j:i<j)]
    ms = [p/sum(ms) for p in ms]
    total = home+away
    over = 1-math.exp(-total)*(1+total+total*total/2)
    btts = (1-math.exp(-home))*(1-math.exp(-away))
    return ms, over, btts


def predict(history, odds, home_rows, away_rows, cutoff, sport, tournament=None):
    hs = stats(home_rows, cutoff, sport, "home", tournament)
    aws = stats(away_rows, cutoff, sport, "away", tournament)
    quality = min(hs["quality"], aws["quality"])
    reliability = quality/100
    expected_home = (hs["for"]+aws["against"])/2
    expected_away = (aws["for"]+hs["against"])/2
    # H2H is a small, age-limited adjustment, never an independent vote/veto.
    h2h = [r for r in archived_rows(history.get("rekabetGecmisi", []), history["teamEv"], cutoff, sport)
           if (cutoff-date.fromisoformat(r["date"])).days <= CONFIG["h2h_max_age_days"]]
    if h2h:
        ws = [weight(r, cutoff, sport) for r in h2h]
        fraction = CONFIG["h2h_fraction"] * min(sum(ws)/5, 1)
        expected_home = (1-fraction)*expected_home+fraction*sum(r["for"]*w for r,w in zip(h2h,ws))/sum(ws)
        expected_away = (1-fraction)*expected_away+fraction*sum(r["against"]*w for r,w in zip(h2h,ws))/sum(ws)
    if sport == "football":
        expected_home *= CONFIG[sport]["home_advantage"]
        expected_home *= 1+0.12*(hs["form"]-0.5)
        expected_away *= 1+0.12*(aws["form"]-0.5)
        expected_home, expected_away = [min(6, max(0.15, v)) for v in (expected_home, expected_away)]
        ms, over, btts = poisson_probabilities(expected_home, expected_away)
        market = devig([odds.get(k,0) for k in ("ms1", "msX", "ms2")])
        ou = devig([odds.get(k,0) for k in ("over25", "under25")])
        bt = devig([odds.get(k,0) for k in ("bttsYes", "bttsNo")])
        labels = ["MS1", "MSX", "MS2"]
        line = 2.5
    else:
        # Normalized win rate has full [0,1] scale; no former divide-by-ten attenuation.
        expected_home += CONFIG[sport]["home_advantage"] + 3*(hs["form"]-aws["form"])
        sd_margin = max(8, math.sqrt((hs["marginVariance"]+aws["marginVariance"])/2))
        sd_total = max(10, math.sqrt((hs["totalVariance"]+aws["totalVariance"])/2))
        ms = [normal_cdf((expected_home-expected_away)/sd_margin)]
        ms.append(1-ms[0])
        line = odds.get("hOverUnderValue", 0)
        # Published basketball OU/real scores include overtime. Account for empirical OT separately.
        total = expected_home+expected_away+(hs["overtime"]+aws["overtime"])/2
        over = normal_cdf((total-line)/sd_total) if line > 0 else None
        btts, bt = None, None
        market = devig([odds.get(k,0) for k in ("ms1", "ms2")])
        ou = devig([odds.get(k,0) for k in ("over", "under")]) if line > 0 else None
        labels = ["MS1", "MS2"]
    # Reduce model-only separation when evidence is weak, then blend valid de-vigged market.
    ms = [1/len(ms) + reliability*(p-1/len(ms)) for p in ms]
    over = 0.5+reliability*(over-0.5) if over is not None else None
    btts = 0.5+reliability*(btts-0.5) if btts is not None else None
    market_fraction = CONFIG["market_fraction"]
    if market:
        ms = [(1-market_fraction)*p+market_fraction*m for p,m in zip(ms,market)]
    if ou and over is not None:
        over = (1-market_fraction)*over+market_fraction*ou[0]
    if bt and btts is not None:
        btts = (1-market_fraction)*btts+market_fraction*bt[0]
    probabilities = dict(zip(labels, ms))
    if over is not None:
        probabilities.update({"Üst": over, "Alt": 1-over})
    if btts is not None:
        probabilities.update({"Var": btts, "Yok": 1-btts})
    odd_map = dict(zip(labels, [odds.get(k,0) for k in (("ms1","msX","ms2") if sport == "football" else ("ms1","ms2"))]))
    odd_map.update({"Üst": odds.get("over25" if sport == "football" else "over",0),
                    "Alt": odds.get("under25" if sport == "football" else "under",0),
                    "Var": odds.get("bttsYes",0), "Yok": odds.get("bttsNo",0)})
    selections = select(probabilities, odd_map, quality, min(hs["count"],aws["count"]), labels)
    return {"probabilities": probabilities, "selections": selections, "odds": odd_map,
            "expectedScore": [expected_home, expected_away], "line": line,
            "quality": quality, "homeStats": hs, "awayStats": aws,
            "algorithm": CONFIG["version"], "calibrated": False}


def select(probabilities, odds, quality, count, ms_labels):
    selections = []
    if quality < CONFIG["minimum_quality"] or count < CONFIG["minimum_matches_per_team"]:
        return selections
    for group in (ms_labels, ["Üst", "Alt"], ["Var", "Yok"]):
        available = [k for k in group if k in probabilities]
        if not available:
            continue
        key = max(available, key=lambda k:probabilities[k])
        p, odd = probabilities[key], odds.get(key,0)
        if isinstance(odd,(int,float)) and math.isfinite(odd) and odd > 1 and p >= CONFIG["minimum_probability"] and p*odd-1 >= CONFIG["minimum_expected_value"]:
            selections.append({"market": key, "probability": p, "odd": odd, "expectedValue": p*odd-1})
    return selections


def baseline_probabilities(prediction, sport):
    out = {"MS1": prediction["pHome"], "MS2": prediction["pAway"],
           "Üst": prediction["pOver25"], "Alt": 1-prediction["pOver25"]}
    if sport == "football":
        out.update({"MSX": prediction["pDraw"], "Var": prediction["pBttsYes"], "Yok": 1-prediction["pBttsYes"]})
    return out


def keyed_histories(rows):
    out = {}
    for row in rows:
        url = row.get("originalMatchUrl", row.get("detailUrl", ""))
        eid = event_id({"detailUrl": url})
        if eid in out:
            raise ValueError("Duplicate event ID: " + eid)
        out[eid] = row
    return out


def run_day(published, day, sport, collector=None):
    folder = published/("futbol" if sport == "football" else "basketbol")/"data"
    load = lambda kind:json.loads((folder/(kind+"-"+day+".json")).read_text())
    infos, histories, baselines = load("MatchInfo"), keyed_histories(load("TeamMatchHistory")), load("PredictionResult")
    pred_map = {(p["homeTeam"],p["awayTeam"]):p for p in baselines}
    if len(pred_map) != len(baselines):
        raise ValueError("Ambiguous baseline team pairs")
    cutoff = date.fromisoformat(day)
    results = []
    for info in infos:
        eid = event_id(info)
        if eid not in histories:
            raise ValueError("History absent for event " + eid)
        history = histories[eid]
        old = pred_map.get((history["teamEv"],history["teamDep"]))
        if old is None:
            raise ValueError("Baseline prediction absent for event " + eid)
        fallback = [archived_rows(history.get(k,[]), history[t], cutoff, sport)
                    for k,t in (("sonMaclarHome","teamEv"),("sonMaclarAway","teamDep"))]
        data = [{"rows": r, "source": "archived-six"} for r in fallback]
        error = None
        if collector:
            try:
                fetched = collector.collect(info, history, cutoff, sport)
                # Never replace a more recent archived signal with stale provider coverage.
                needs_summary = [not f["rows"] or bool(r and max(x["date"] for x in f["rows"]) < max(x["date"] for x in r)) for f,r in zip(fetched,fallback)]
                summary = collector.summary_fallback(info,cutoff,sport) if any(needs_summary) else [None,None]
                data = []
                for f,r,s,needed in zip(fetched,fallback,summary,needs_summary):
                    if needed:
                        f = s if s and s["rows"] else {"rows":r,"source":"archive-fallback-empty-or-stale-schedule"}
                        if r and f["rows"] and max(x["date"] for x in f["rows"]) < max(x["date"] for x in r):
                            f = {"rows":r,"source":"archive-fallback-stale-summary"}
                    data.append(f)
            except RateLimitError:
                raise
            except (ValueError,KeyError,urllib.error.URLError,TimeoutError) as exc:
                error = str(exc)
                data = [{"rows": r,"source":"archive-fallback-error"} for r in fallback]
        prediction = predict(history, info["odds"], data[0]["rows"], data[1]["rows"], cutoff, sport, data[0].get("targetTournamentId"))
        # An ablation with frozen six-match input separates feature/model changes from history expansion.
        six = predict(history, info["odds"], fallback[0], fallback[1], cutoff, sport)
        result = {"eventId": eid, "date": day, "sport": sport, "name": info["name"], "time": info["time"],
                  "homeTeam": history["teamEv"], "awayTeam": history["teamDep"], "inputOdds": info["odds"],
                  "baseline": {"probabilities":baseline_probabilities(old,sport),"pick":old.get("pick"),"scoreline":old.get("scoreline")},
                  "new": prediction, "sixMatchAblation": six, "sources": [d["source"] for d in data], "endpointError": error}
        results.append(result)
        print(f"{sport} {eid}: {prediction['homeStats']['count']}+{prediction['awayStats']['count']} Q={prediction['quality']:.0f} {result['sources']}", flush=True)
    if len(results) != len(infos):
        raise ValueError("Match coverage changed")
    return results


def outcomes(real, row):
    """Use saved production settlement scores, joining strictly by saved team names."""
    home, away = real.get("homeScore"), real.get("awayScore")
    if home is None or away is None:
        score = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", str(real.get("score", "")))
        if score:
            home, away = map(int, score.groups())
    if not isinstance(home,(int,float)) or not isinstance(away,(int,float)):
        return None
    if row["sport"] == "basketball" and home == away:
        return None
    result = {"MS1":int(home>away),"MS2":int(home<away),
              "Üst":int(home+away>row["new"]["line"]),"Alt":int(home+away<row["new"]["line"])}
    if row["sport"] == "football":
        result.update({"MSX":int(home==away),"Var":int(home>0 and away>0),"Yok":int(not(home>0 and away>0))})
    if home+away == row["new"]["line"] or row["new"]["line"] <= 0:
        result.pop("Üst",None);result.pop("Alt",None)
    return result


def evaluate(rows, published):
    observations = []
    missing = 0
    by_date = {}
    for row in rows:
        sport_folder = "futbol" if row["sport"] == "football" else "basketbol"
        key = (sport_folder,row["date"])
        if key not in by_date:
            p = published/sport_folder/"data"/("RealScores-"+row["date"]+".json")
            real = json.loads(p.read_text()) if p.exists() else []
            by_date[key] = {(r.get("homeTeam"),r.get("awayTeam")):r for r in real}
        # Production settlement stores MatchInfo display names; model history may use full names.
        # Prefer the exact saved display pair (e.g. U20), never fuzzy team-name matching.
        real = next((r for (home,away),r in by_date[key].items()
                     if home + " - " + away == row["name"]), None)
        if real is None and row["name"] == row["homeTeam"] + " - " + row["awayTeam"]:
            real = by_date[key].get((row["homeTeam"],row["awayTeam"]))
        result = outcomes(real,row) if real else None
        if result is None:
            missing += 1
            continue
        observations.append((row,result))
    report = {"settledMatches":len(observations), "missingResults":missing,
              "evaluationInput":"archived six-match snapshots; expanded historical backtest not available",
              "calibration":{"fitted":False,"reason":"Limited dated archive; no fitting on evaluation outcomes",
                             "minimumRows":CONFIG["calibration_minimum_rows"],"minimumDates":CONFIG["calibration_minimum_dates"]},
              "metrics":[]}
    for sport in ("football","basketball"):
        for variant in ("baseline","new"):
            for market,labels in (("MS",["MS1","MSX","MS2"] if sport=="football" else ["MS1","MS2"]),("OU",["Üst","Alt"]),("BTTS",["Var","Yok"])):
                valid = [(r[variant]["probabilities"],y) for r,y in observations if r["sport"]==sport and all(k in r[variant]["probabilities"] and k in y for k in labels)]
                if not valid:
                    continue
                brier = statistics.mean(sum((p[k]-y[k])**2 for k in labels) for p,y in valid)
                loss = statistics.mean(-sum(y[k]*math.log(max(1e-12,p[k])) for k in labels) for p,y in valid)
                accuracy = statistics.mean(y[max(labels,key=lambda k:p[k])] for p,y in valid)
                bins = []
                for lo in range(0,10):
                    selected = [(p[max(labels,key=lambda k:p[k])],y[max(labels,key=lambda k:p[k])]) for p,y in valid
                                if lo/10 <= max(p[k] for k in labels) < (lo+1)/10]
                    if selected:
                        bins.append({"range":[lo/10,(lo+1)/10],"count":len(selected),"meanProbability":statistics.mean(p for p,y in selected),"hitRate":statistics.mean(y for p,y in selected)})
                report["metrics"].append({"sport":sport,"variant":variant,"market":market,"count":len(valid),"brier":brier,"logLoss":loss,"accuracy":accuracy,"calibrationBins":bins})
    return report


STYLE = """body{font-family:'Segoe UI',Arial,sans-serif;background:#f3f6fa;color:#222;margin:0}.page{max-width:1400px;margin:auto;padding:20px}h1{color:#004d80}a{color:#0077cc}.card{background:white;border:1px solid #dce3ec;border-radius:12px;padding:18px;margin:18px 0;box-shadow:0 2px 8px #0001}.table-wrapper{overflow-x:auto}table{border-collapse:collapse;width:100%;background:white}th{background:#0077cc;color:white}td,th{padding:10px;text-align:center;border-bottom:1px solid #ddd}tr:nth-child(even){background:#f3f6fa}.muted{color:#666;font-size:.9em}.badge{padding:5px 8px;background:#eaf3ff;border-radius:6px}.warn{background:#fff1df;padding:12px;border-radius:8px}input{padding:10px;width:90%;max-width:500px}summary{cursor:pointer;font-weight:bold}.positive{color:#087a35}.negative{color:#bc2431}nav{display:flex;gap:20px;flex-wrap:wrap}@media(max-width:650px){.page{padding:10px}td,th{padding:8px;font-size:.85em}}"""


def page(title, body):
    return "<!DOCTYPE html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+html.escape(title)+"</title><style>"+STYLE+"</style></head><body><main class='page'><h1>"+html.escape(title)+"</h1><nav><a href='index.html'>Karşılaştırma</a><a href='new-football.html'>Yeni futbol</a><a href='new-basketball.html'>Yeni basketbol</a><a href='baseline-football.html'>Mevcut futbol</a><a href='baseline-basketball.html'>Mevcut basketbol</a><a href='evaluation.html'>Geçmiş ölçümü</a></nav>"+body+"</main></body></html>"


def percentage(v):
    return f"%{100*v:.1f}" if v is not None else "—"


def picks(prediction):
    return " | ".join(s["market"] for s in prediction["selections"]) or "Seçim yok"


def write_html(output, rows, evaluation, day):
    for sport in ("football","basketball"):
        content = "<p class='warn'>Deneysel olasılıklar henüz kalibre edilmedi. Veri puanı başarı olasılığı değildir. Oranlar günlük ilk yayından sabittir.</p>"
        for row in rows:
            if row["sport"] != sport:
                continue
            new = row["new"]
            content += "<article class='card'><h2>"+html.escape(row["name"])+" <span class='muted'>"+html.escape(row["time"])+"</span></h2>"
            content += f"<p><span class='badge'>Veri puanı {new['quality']:.0f}/100</span> <strong>{html.escape(picks(new))}</strong> · Beklenen skor {new['expectedScore'][0]:.1f}–{new['expectedScore'][1]:.1f}</p>"
            content += "<div class='table-wrapper'><table><tr><th>Pazar</th><th>Mevcut %</th><th>Yeni %</th><th>Fark</th><th>Sabit oran</th></tr>"
            for key,value in new["probabilities"].items():
                old=row["baseline"]["probabilities"].get(key)
                content += f"<tr><td>{html.escape(key)}</td><td>{percentage(old)}</td><td>{percentage(value)}</td><td>{(value-old)*100:+.1f} puan</td><td>{new['odds'].get(key,0):.2f}</td></tr>"
            content += "</table></div><details><summary>Kullanılan geçmiş ve veri kalitesi</summary>"
            for label,key,source in zip(("Ev sahibi","Deplasman"),("homeStats","awayStats"),row["sources"]):
                st=new[key]
                content += f"<h3>{label}</h3><p>{st['count']} maç; etkin örnek {st['effectiveCount']:.1f}; ilgili saha {st['venueCount']}; hazırlık {st['friendlyCount']}; sonucu bilinmeyen {st['unknownFinalCount']}. Kaynak: {html.escape(source)}</p><div class='table-wrapper'><table><tr><th>Tarih</th><th>Saha</th><th>Rakip</th><th>Normal skor</th><th>Son skor</th><th>Turnuva</th></tr>"
                for r in st["rows"]:
                    final="—" if r["finalFor"] is None else str(r["finalFor"])+"–"+str(r["finalAgainst"])
                    content += "<tr>"+"".join("<td>"+html.escape(str(v))+"</td>" for v in (r["date"],r["venue"],r.get("opponent",""),f"{r['for']}–{r['against']}",final,r["tournament"]))+"</tr>"
                content += "</table></div>"
            if row["endpointError"]:
                content += "<p class='warn'>Endpoint hatası: "+html.escape(row["endpointError"])+"</p>"
            content += "</details></article>"
        (output/("new-"+sport+".html")).write_text(page(day+" · Yeni "+("futbol" if sport=="football" else "basketbol"),content),encoding="utf-8")
    body="<p class='warn'>Aynı maç ve oranlar. Eski yayın HTML'leri aynen saklandı. Yeni model deneysel; yüzdeler öğrenilmiş kalibrasyon içermez. Aynı günün maçları geçmişe alınmaz.</p><input id='filter' placeholder='Takım ara'><div class='table-wrapper'><table id='comparison'><thead><tr><th>Spor / saat</th><th>Maç</th><th>Mevcut model etiketi</th><th>Yeni seçim</th><th>MS1 mevcut → yeni</th><th>Üst mevcut → yeni</th><th>Geçmiş ev + dep.</th><th>Veri puanı</th></tr></thead><tbody>"
    for r in rows:
        n,b=r["new"],r["baseline"]
        fields=(r["sport"]+" / "+r["time"],r["name"],b["pick"],picks(n),percentage(b["probabilities"]["MS1"])+" → "+percentage(n["probabilities"]["MS1"]),percentage(b["probabilities"]["Üst"])+" → "+percentage(n["probabilities"].get("Üst")),f"{n['homeStats']['count']} + {n['awayStats']['count']}",f"{n['quality']:.0f}/100")
        body += "<tr>"+"".join("<td>"+html.escape(str(v))+"</td>" for v in fields)+"</tr>"
    body += "</tbody></table></div><p class='muted'>Mevcut model etiketi, mevcut kuponun filtrelenmiş seçimi değildir. Kuponu mevcut HTML'den inceleyin. Beklenen skor seçim vetosu olarak kullanılmaz. Saha ortalamaları az örnekte genel ortalamaya çekilir.</p><script>document.getElementById('filter').addEventListener('input',e=>{for(const r of document.querySelectorAll('#comparison tbody tr'))r.hidden=!r.textContent.toLocaleLowerCase('tr').includes(e.target.value.toLocaleLowerCase('tr'));});</script>"
    (output/"index.html").write_text(page(day+" · Mevcut / yeni karşılaştırması",body),encoding="utf-8")
    body=f"<p>{evaluation['settledMatches']} sonuçlanmış maç; {evaluation['missingResults']} eşleşmeyen/bekleyen sonuç.</p><p class='warn'>Geçmiş ölçümü arşivdeki altı maç girdisiyle yapılır; geniş geçmişin üstünlüğünü ölçmez. Yalnızca mevcut tarihli arşiv kullanılır. Kalibrasyon eğitimi yapılmadı; yeterli ayrı gün ve maç yok. Brier ve log loss için düşük değer iyidir.</p><div class='table-wrapper'><table><tr><th>Spor</th><th>Model</th><th>Pazar</th><th>N</th><th>Brier</th><th>Log loss</th><th>En olası sonuç isabeti</th></tr>"
    for m in evaluation["metrics"]:
        body += f"<tr><td>{m['sport']}</td><td>{m['variant']}</td><td>{m['market']}</td><td>{m['count']}</td><td>{m['brier']:.4f}</td><td>{m['logLoss']:.4f}</td><td>{percentage(m['accuracy'])}</td></tr>"
    body += "</table></div><details><summary>Kalibrasyon dilimleri ve ölçüm ayrıntısı</summary><pre>"+html.escape(json.dumps(evaluation,ensure_ascii=False,indent=2))+"</pre></details>"
    (output/"evaluation.html").write_text(page("Geçmiş sonuç ölçümü",body),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--published",type=Path,required=True)
    parser.add_argument("--date",required=True)
    parser.add_argument("--output",type=Path,default=Path("comparison-output"))
    parser.add_argument("--offline",action="store_true")
    args=parser.parse_args()
    date.fromisoformat(args.date)
    args.output.mkdir(parents=True,exist_ok=True)
    client=Client(args.output/"http-cache")
    collector=None if args.offline else Collector(client)
    rows=[]
    historical=[]
    for sport,folder in (("football","futbol"),("basketball","basketbol")):
        rows.extend(run_day(args.published,args.date,sport,collector))
        baseline=args.published/folder/(folder+".html")
        (args.output/("baseline-"+sport+".html")).write_bytes(baseline.read_bytes())
        for p in sorted((args.published/folder/"data").glob("PredictionResult-????-??-??.json")):
            old_day=p.stem[len("PredictionResult-"):]
            if old_day >= args.date:
                continue
            historical.extend(run_day(args.published,old_day,sport))
    evaluation=evaluate(historical,args.published)
    dump(args.output/"predictions.json",rows)
    dump(args.output/"historical-predictions.json",historical)
    dump(args.output/"evaluation.json",evaluation)
    dump(args.output/"request-audit.json",client.audit)
    dump(args.output/"config.json",CONFIG)
    manifest={"date":args.date,"generatedAtUtc":datetime.utcnow().isoformat()+"Z","version":CONFIG["version"],
              "matchCount":len(rows),"footballCount":sum(r["sport"]=="football" for r in rows),
              "basketballCount":sum(r["sport"]=="basketball" for r in rows),
              "inputHashes":{str(p.relative_to(args.published)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for folder in ("futbol","basketbol") for p in (args.published/folder/"data").glob("*-"+args.date+".json")},
              "fallbackMatches":sum(any("fallback" in s for s in r["sources"]) for r in rows),
              "policy":"completed matches strictly before fixture date; no same-day history; no publication"}
    dump(args.output/"manifest.json",manifest)
    write_html(args.output,rows,evaluation,args.date)
    print(json.dumps(manifest,ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
