"""Daily wide history collection; experiment artifacts only."""
import argparse, copy, hashlib, json, re, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
CONFIG={"request_interval_seconds":0.5,"max_months":12,"football":{"history_limit":20},"basketball":{"history_limit":25}}
MONTHS={name:i+1 for i,name in enumerate("Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split())}
FINISHED={5,9,11}
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
            parsed = datetime.strptime(value, fmt)
            # Broadage raw widget dates are UTC (verified against saved Nesine start times).
            # Nesine POFMD/date snapshots use Istanbul; Turkey remains UTC+3.
            if fmt == "%m/%d/%Y %H:%M:%S":
                parsed += timedelta(hours=3)
            return parsed.date()
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
    win_for, win_against = (gf, ga) if sport == "football" else (ff, fa)
    return {"id": "broadage:" + str(row["id"]), "date": played.isoformat(), "venue": side,
            "for": gf, "against": ga, "finalFor": ff, "finalAgainst": fa,
            "win": int(win_for > win_against), "draw": int(win_for == win_against), "regulationKnown": True,
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
            output.append({"rows":unique(rows),"source":"nesine-summary-general-and-venue","teamId":tid,
                           "targetTournamentId":header.get("TOUR",{}).get("TID")})
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
                        if parsed and str(row.get("id")) != field("MatchId"):
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



def preserve_journal(previous,output,snapshot):
    path=previous/'live-history-journal.json'
    journal=json.loads(path.read_text()) if path.exists() else []
    journal=[r for r in journal if r['targetDate']!=snapshot['targetDate']]
    journal.append(snapshot)
    dump(output/'live-history-journal.json',journal)


def collect_day(published, previous, output, target, max_seconds=2700):
    cutoff = date.fromisoformat(target)
    output.mkdir(parents=True, exist_ok=True)
    client = Client(output / 'http-cache' / target)
    collector = Collector(client)
    snapshot = {'targetDate': target, 'startedAt': datetime.now(timezone.utc).isoformat(),
                'fixtures': [], 'errors': [], 'policy': 'Exact event identity; finished rows strictly before fixture day; fetched after kickoff is retrospective.'}
    # Re-evaluation reuses the exact original daily collection, including gaps.
    saved = previous / 'live-history.json'
    if saved.exists():
        old = json.loads(saved.read_text())
        if old.get('targetDate') == target:
            dump(output / 'live-history.json', old)
            preserve_journal(previous,output,old)
            return old
    deadline = time.monotonic() + max_seconds
    stopped = False
    try:
        for sport, folder in (('football','futbol'),('basketball','basketbol')):
            infos = json.loads((published/folder/'data'/f'MatchInfo-{target}.json').read_text())
            histories = json.loads((published/folder/'data'/f'TeamMatchHistory-{target}.json').read_text())
            by_id = {event_id({'detailUrl':h.get('originalMatchUrl',h.get('detailUrl',''))}):h for h in histories}
            for info in infos:
                eid = event_id(info)
                h = by_id.get(eid)
                if not h or any(h.get(k,'-').strip() in ('','-') for k in ('teamEv','teamDep')):
                    snapshot['errors'].append({'sport':sport,'eventId':eid,'reason':'identity/history absent'})
                    continue
                if time.monotonic() > deadline:
                    stopped = True
                    snapshot['errors'].append({'sport':sport,'eventId':eid,'reason':'collection time budget exhausted; remaining fixtures unavailable'})
                    break
                try:
                    sides = collector.collect(info,h,cutoff,sport)
                    now = datetime.now(timezone.utc)
                    try:
                        kickoff = datetime.fromisoformat(target+'T'+info['time']+'+03:00')
                        prospective = now < kickoff
                    except (ValueError,KeyError):
                        prospective = False
                    snapshot['fixtures'].append({'sport':sport,'eventId':eid,
                        'teams':[h['teamEv'],h['teamDep']], 'sides':sides,
                        'collectedAt':now.isoformat(),'beforeKickoff':prospective})
                except RateLimitError as exc:
                    stopped = True
                    snapshot['errors'].append({'sport':sport,'eventId':eid,'reason':str(exc)})
                    break
                except Exception as exc:
                    snapshot['errors'].append({'sport':sport,'eventId':eid,'reason':str(exc)})
                finally:
                    # Keep a recoverable partial artifact even on runner timeout.
                    dump(output/'live-history.json',snapshot)
            if stopped: break
    finally:
        snapshot.update({'completedAt':datetime.now(timezone.utc).isoformat(),'stoppedEarly':stopped,
                         'requests':client.audit})
        dump(output/'live-history.json',snapshot)
        preserve_journal(previous,output,snapshot)
    return snapshot


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--published',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--target-date',required=True)
    p.add_argument('--max-seconds',type=int,default=2700)
    a=p.parse_args()
    result=collect_day(a.published,a.previous,a.output,a.target_date,a.max_seconds)
    print(json.dumps({'fixtures':len(result['fixtures']),'errors':len(result['errors']),
                      'stoppedEarly':result.get('stoppedEarly',False)}))
