"""User's explicit 80/20 competition-history policy; no fitting or score forecast."""
import copy
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from display_odds import KEYS, valid_number
from report import GROUPS, result
from priced_choices import read, write, signature, digest
from live_history import parse_date

POLICY = 'competition-six-80-20-v1'
START_DATE = '2026-11-27'
FILE = 'user-rules-before-results.json'
MODEL = 'user-rules-model.json'
RULES = {
    'policy': POLICY, 'historyLimit': 6, 'teamWeight': .8, 'h2hWeight': .2,
    'teamScope': 'same tournament if any, otherwise general; each team separately',
    'h2hScope': 'general, newest six, oriented to current home team',
    'cutoff': 'finished matches strictly before fixture Istanbul date; same-day history excluded if exact kickoff unknown',
    'selection': 'two highest priced probabilities; lower latest-match support wins',
    'tie': 'all available supports match: lower probability; otherwise higher probability',
    'exactTie': 'same unrounded combined probability and same support fraction: both top choices',
    'oppositeTie': 'skip an entire market when its two highest opposing options tie in probability and support; no remaining option means no prediction',
    'basketball': 'finished final score including overtime; OU at current fixture line; pushes excluded',
    'odds': 'complete valid market (>1 finite), same safety rule as complete-market-price-v2',
    'scorePrediction': False,
}
MODEL_TEXT = json.dumps(RULES, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
MODEL_HASH = hashlib.sha256(MODEL_TEXT.encode()).hexdigest()


def label(sport, market, option):
    value = GROUPS[sport][market][option]
    return 'MS0' if value == 'MSX' else 'KG ' + value if market == 'BTTS' else value


def score(match, sport, team):
    keys = ('homeFinal', 'awayFinal') if sport == 'basketball' else ('homeScore', 'awayScore')
    values = [match.get(k) for k in keys]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in values):
        return None
    if sport == 'basketball' and values[0] == values[1]:
        return None
    return values if match['home'] == team else values[::-1]


def outcome(match, sport, team, market, line, invert=False):
    values = score(match, sport, team)
    if values is None:
        return None
    a, b = values
    if market == 'MS':
        if invert: a, b = b, a
        return 0 if a > b else (1 if sport == 'football' and a == b else 2 if sport == 'football' else 1)
    if market == 'BTTS':
        return 0 if a > 0 and b > 0 else 1
    if not valid_number(line, 0) or a + b == line:
        return None
    return 0 if a + b > line else 1


def select(candidates):
    """Stable market/option order breaks exact probability ties deterministically."""
    candidates, _ = remove_ambiguous(candidates)
    top = sorted(candidates, key=lambda c: -c['confidence'])[:2]
    if len(top) < 2:
        return (top[0] if top else None), top
    a, b = top
    # Different missing/push counts cannot be compared as if both had three votes.
    if a['supportCount'] != b['supportCount'] or not a['supportCount']:
        chosen = a
    elif a['supportHits'] != b['supportHits']:
        chosen = min(top, key=lambda c: c['supportHits'])
    elif a['supportHits'] == a['supportCount']:
        chosen = min(top, key=lambda c: c['confidence'])
    else:
        chosen = a
    return chosen, top


def remove_ambiguous(candidates):
    skipped=[]
    for market in dict.fromkeys(c['market'] for c in candidates if 'market' in c):
        options=sorted([c for c in candidates if c['market']==market],key=lambda c:-c['confidence'])
        if len(options)>=2 and math.isclose(options[0]['confidence'],options[1]['confidence'],rel_tol=0,abs_tol=1e-12) and \
                (options[0]['supportHits'],options[0]['supportCount'])==(options[1]['supportHits'],options[1]['supportCount']):
            skipped.append(market)
    return [c for c in candidates if c.get('market') not in skipped],skipped


def sources(row, sport, matches, identity):
    """Use the fixture's own dedicated H2H list, not just incidental wide-history overlap.

    Original saved summary names are scoped to this exact fixture, never fuzzy-joined
    to another fixture/provider. The raw source is preserved by prepare/replay.
    """
    raw = row.get('userRuleHistory') or {}
    own_names = [raw.get('teamEv'), raw.get('teamDep')]
    if not all(isinstance(t,str) and t.strip() for t in own_names) or own_names[0] == own_names[1]:
        return matches, identity, None
    identity = copy.deepcopy(identity) if identity else {
        'home': 'fixture:'+str(row['eventId'])+':home', 'away':'fixture:'+str(row['eventId'])+':away',
        'namespace':'fixture:'+str(row['eventId']), 'tournamentId':None}
    names = dict(zip(own_names, (identity['home'], identity['away'])))
    tournament_names = {m.get('tournament') for m in matches if identity.get('tournamentId') and
                        m.get('sport')==sport and m.get('namespace')==identity['namespace'] and
                        m.get('tournamentId')==identity['tournamentId'] and m.get('tournament')}
    def convert(rows):
        out=[]
        for m in rows or []:
            played=parse_date(m.get('matchDate'))
            if not played or played.isoformat()>=row['date'] or m.get('status','finished')!='finished':continue
            if not m.get('homeTeam') or not m.get('awayTeam'):continue
            h=names.get(m['homeTeam'],identity['namespace']+':name:'+m['homeTeam'])
            a=names.get(m['awayTeam'],identity['namespace']+':name:'+m['awayTeam'])
            values=(m.get('homeScore'),m.get('awayScore'))
            key='summary:'+played.isoformat()+':'+h+':'+a
            out.append({'key':key,'date':played.isoformat(),'sport':sport,'namespace':identity['namespace'],
                        'home':h,'away':a,'homeScore':values[0],'awayScore':values[1],
                        'homeFinal':values[0],'awayFinal':values[1],
                        'tournamentId':identity['tournamentId'] if len(tournament_names)==1 and m.get('tournament') in tournament_names else None})
        return out
    pool=list(matches)
    for prop,team in [('sonMaclarHome',identity['home']),('sonMaclarAway',identity['away'])]:
        if not any(m.get('sport')==sport and m.get('date','9999')<row['date'] and team in (m['home'],m['away']) and score(m,sport,team) is not None for m in pool):
            pool.extend(m for m in convert(raw.get(prop)) if team in (m['home'],m['away']))
    # An explicit empty H2H list is authoritative; None means source list absent.
    h2h=convert(raw['rekabetGecmisi']) if raw.get('rekabetGecmisi') is not None else None
    return pool,identity,h2h


def calculate(row, sport, matches, identity):
    matches,identity,dedicated_h2h=sources(row,sport,matches,identity)
    detail = {'teamCounts': {'home': 0, 'away': 0}, 'teamScopes': {}, 'h2hCount': 0,
              'markets': {}, 'topTwo': [], 'reason': 'Yeterli geçmiş / doğrulanmış takım kimliği yok'}
    entry = {k: row.get(k) for k in ('date', 'eventId', 'name', 'time')}
    entry.update(sport=sport, markets={}, chosen=None, choices=[], calculation=detail)
    if not identity:
        return entry
    h, a = identity['home'], identity['away']
    pool = [m for m in matches if m.get('sport') == sport and m.get('date', '9999') < row['date']
            and m.get('namespace') == identity['namespace']]
    pool.sort(key=lambda m: (m['date'], m['key']), reverse=True)
    # Reject duplicate conflicts and repeat records rather than silently double-count.
    seen = {}; conflicts = set()
    for m in pool:
        if m['key'] in seen and seen[m['key']] != m: conflicts.add(m['key'])
        seen.setdefault(m['key'], m)
    pool = [m for k, m in seen.items() if k not in conflicts]
    teams = []
    for side, team in [('home', h), ('away', a)]:
        general = [m for m in pool if team in (m['home'], m['away']) and score(m, sport, team) is not None]
        same = [m for m in general if identity.get('tournamentId') and m.get('tournamentId') == identity['tournamentId']]
        chosen = (same or general)[:6]
        teams.append(chosen)
        detail['teamCounts'][side] = len(chosen)
        detail['teamScopes'][side] = 'Bu turnuva' if same else 'Genel (turnuva geçmişi yok / kimliği eksik)'
    hpool=sorted(dedicated_h2h,key=lambda m:(m['date'],m['key']),reverse=True) if dedicated_h2h is not None else pool
    hseen={}
    for m in hpool:
        if {m['home'],m['away']}=={h,a} and score(m,sport,h) is not None:hseen.setdefault(m['key'],m)
    h2h = list(hseen.values())[:6]
    detail['h2hCount'] = len(h2h)
    if not all(teams):
        return entry
    line = 2.5 if sport == 'football' else (row.get('odds') or {}).get('hOverUnderValue')
    candidates = []
    for market, keys in KEYS[sport].items():
        observations = [[outcome(m, sport, t, market, line, invert=(side == 1)) for m in rows]
                        for side, (t, rows) in enumerate(zip((h, a), teams))]
        counts = [[sum(y == i for y in ys) for i in range(len(keys))] for ys in observations]
        denominators = [sum(y is not None for y in ys) for ys in observations]
        hy = [outcome(m, sport, h, market, line) for m in h2h]
        hn = sum(y is not None for y in hy)
        # Each side must contribute valid observations; a push is not a loss.
        if not all(denominators): continue
        weight = .8 if hn else 1.
        probs = []
        metrics = []
        latest = [(h2h[0], h, False)] if h2h else []
        latest += [(teams[0][0], h, False), (teams[1][0], a, True)]
        votes = [outcome(m, sport, t, market, line, inv) for m, t, inv in latest]
        for i, key in enumerate(keys):
            numerator = sum(c[i] for c in counts); n = sum(denominators)
            hcount = sum(y == i for y in hy)
            team_part = numerator / n * weight
            hpart = hcount / hn * (1 - weight) if hn else 0.
            probability = team_part + hpart
            probs.append(probability)
            metric = {'market': market, 'option': i, 'confidence': probability,
                      'teamNumerators': [c[i] for c in counts], 'teamDenominators': denominators,
                      'teamWeight': weight, 'teamPart': team_part, 'h2hNumerator': hcount,
                      'h2hDenominator': hn, 'h2hPart': hpart,
                      'supportHits': sum(y == i for y in votes), 'supportCount': sum(y is not None for y in votes)}
            metrics.append(metric)
            if all(valid_number((row.get('odds') or {}).get(k), 1) for k in keys):
                candidates.append(dict(metric, price=row['odds'][key]))
        entry['markets'][market] = probs
        detail['markets'][market] = metrics
    candidates,detail['skippedMarkets']=remove_ambiguous(candidates)
    chosen, top = select(candidates)
    entry['chosen'] = chosen
    entry['choices'] = [chosen] if chosen else []
    if len(top) == 2 and math.isclose(top[0]['confidence'], top[1]['confidence'], rel_tol=0, abs_tol=1e-12) and \
            (top[0]['supportHits'], top[0]['supportCount']) == (top[1]['supportHits'], top[1]['supportCount']):
        entry['choices'] = top
    detail['topTwo'] = top
    detail['reason'] = ('Tek uygun aday' if len(top) == 1 else
                        'Son maç desteği düşük aday; eşitlikte tümü destekliyorsa düşük yüzde, aksi halde yüksek yüzde') if chosen else 'Geçerli oranlı pazar / yeterli geçmiş yok'
    if len(top)==2 and (top[0]['supportCount']!=top[1]['supportCount'] or not top[0]['supportCount']):
        detail['reason']='Karşılaştırılabilir son maç verisi eksik / baremde iade: yüksek yüzde'
    if len(entry['choices']) == 2: detail['reason'] = 'Yüzde ve son maç desteği birebir eşit: iki tercih'
    if not chosen and detail['skippedMarkets']:detail['reason']='Zıt tercihleri eşit çıkan pazarlar atlandı; başka uygun aday yok'
    return entry


def verify(root):
    root = Path(root); book = read(root / FILE)
    if book['policy'] != POLICY or book['snapshotSha256'] != signature({k: v for k, v in book.items() if k != 'snapshotSha256'}):
        raise ValueError('User rules snapshot changed')
    if digest(root / MODEL) != MODEL_HASH or book['modelSha256'] != MODEL_HASH:
        raise ValueError('User rules configuration changed')
    for name, expected in book['inputHashes'].items():
        if digest(root / name) != expected: raise ValueError('User rules frozen inputs changed')
    return book


def freeze(root, target, ledger=None, index=None, now=None):
    root = Path(root)
    if (root / FILE).exists():
        book = verify(root)
        if book['targetDate'] != target: raise ValueError('User rules day mismatch')
        return book
    if ledger is None or index is None: raise ValueError('Cannot regenerate missing rules snapshot in Control')
    now = now or datetime.now(timezone.utc)
    write(root / 'user-rules-history-before-results.json', ledger)
    identities = [dict(v, sport=k[0], date=k[1], eventId=k[2]) for k, v in index.items() if k[1] == target]
    write(root / 'user-rules-identities-before-results.json', identities)
    (root / MODEL).write_text(MODEL_TEXT)
    systems = {}
    inputs = {}
    for sport in KEYS:
        entries = []
        inputs[sport] = []
        for row in read(root / (sport + '-replay.json')):
            if row['date'] != target: continue
            inputs[sport].append({k:copy.deepcopy(row.get(k)) for k in ('date','eventId','name','time','odds','userRuleHistory')})
            entry = calculate(row, sport, ledger['matches'], index.get((sport, target, str(row['eventId']))))
            try: before = now < datetime.fromisoformat(target + 'T' + row['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
            except (ValueError, KeyError, TypeError): before = False
            entry['prospectiveBeforeKickoff'] = before
            entry['odds'] = copy.deepcopy(row.get('odds') or {})
            entries.append(entry)
        systems[sport] = {'experiment': entries}
    write(root/'user-rules-fixtures-before-results.json',inputs)
    book = {'policy': POLICY, 'targetDate': target, 'createdAt': now.isoformat(), 'previewOnly': False,
            'modelSha256': MODEL_HASH, 'systems': systems,
            'inputHashes': {n: digest(root / n) for n in ('user-rules-history-before-results.json', 'user-rules-identities-before-results.json','user-rules-fixtures-before-results.json')}}
    book['snapshotSha256'] = signature(book); write(root / FILE, book)
    return book


def tied_prefix(ranked, fraction):
    """Include every match equal to the nominal percentile boundary (no fake decimals)."""
    if not ranked:return []
    limit=math.ceil(len(ranked)*fraction)
    if limit<=0:return []
    threshold=ranked[min(limit,len(ranked))-1]['chosen']['confidence']
    return [e for e in ranked if e['chosen']['confidence']>threshold or math.isclose(e['chosen']['confidence'],threshold,rel_tol=0,abs_tol=1e-12)]


def tied_positions(ranked):
    positions={};anchor=None;start=0
    for i,e in enumerate(ranked):
        p=e['chosen']['confidence']
        if anchor is None or not math.isclose(p,anchor,rel_tol=0,abs_tol=1e-12):anchor=p;start=i
        positions[str(e['eventId'])]=start
    return positions


def settle(root):
    """Results only: never refreeze; no score forecasts or model-dependent metrics."""
    book = verify(root); blocks = {}
    for sport, systems in book['systems'].items():
        rows = {str(r['eventId']): r for r in read(Path(root) / (sport + '-replay.json')) if r['date'] == book['targetDate']}
        metrics = []
        for before in (True, False):
            ranked = sorted([e for e in systems['experiment'] if e['chosen'] and (not before or e['prospectiveBeforeKickoff'])], key=lambda e: (-e['chosen']['confidence'], str(e['eventId'])))
            for fraction in (.25, .5, .75, 1.):
                group = tied_prefix(ranked,fraction); samples = []; pending = push = missing = 0
                for e in group:
                    r = rows.get(str(e['eventId']))
                    if r is None: missing += 1; continue
                    r = dict(r, odds=e['odds'])
                    for choice in e['choices']:
                        y = result(r, sport, choice['market'])
                        if y is None:
                            if r.get('realScore'): push += 1
                            else: pending += 1
                        else: samples.append((choice['confidence'], int(y == choice['option'])))
                n = len(samples)
                metrics.append({'beforeKickoff': before, 'fraction': fraction, 'plannedCount': len(group), 'plannedChoiceCount':sum(len(e['choices']) for e in group), 'count': n,
                                'hits': sum(y for p, y in samples), 'accuracy': sum(y for p, y in samples) / n if n else None,
                                'brier': sum((p-y)**2 for p,y in samples)/n if n else None,
                                'logLoss': -sum(math.log(max(1e-12, p if y else 1-p)) for p,y in samples)/n if n else None,
                                'pending': pending, 'pushOrUnverified': push, 'missing': missing})
        blocks[sport] = metrics
    report = {'policy': POLICY, 'targetDate': book['targetDate'], 'snapshotSha256': book['snapshotSha256'], 'sports': blocks}
    write(Path(root) / 'user-rules-evaluation.json', report)
    return report


def detail_html(entry, sport):
    d = entry['calculation']; lines = []
    def esc(s): return html.escape(str(s))
    def pct(v): return f'%{100*v:.1f}'
    for market, values in d['markets'].items():
        for v in values:
            name = label(sport, market, v['option'])
            nums = v['teamNumerators']; den = sum(v['teamDenominators'])
            lines.append(f'<div><b>{esc(name)}</b>: ({nums[0]} + {nums[1]}) / {den} × {v["teamWeight"]:g} = {pct(v["teamPart"])}</div>')
    hlines = []
    for market, values in d['markets'].items():
        for v in values:
            hlines.append(f'<div><b>{esc(label(sport, market, v["option"]))}</b>: '+
                          (f'{v["h2hNumerator"]} / {v["h2hDenominator"]} × 0.2 = {pct(v["h2hPart"])}' if v['h2hDenominator'] else 'Rekabet yok / geçerli örnek yok → takım geçmişi × 1')+'</div>')
            hlines.append(f'<div class="calculation-total">{pct(v["teamPart"])} + {pct(v["h2hPart"])} = <b>{pct(v["confidence"])}</b></div>')
    top = d['topTwo']
    decision = ''.join(f'<div><b>{esc(label(sport, v["market"], v["option"]))}</b>: {pct(v["confidence"])} · son maç desteği <b>{v["supportHits"]}/{v["supportCount"]}</b></div>' for v in top)
    if d.get('skippedMarkets'):decision='<small>Kararsız pazarlar atlandı: '+esc(', '.join(d['skippedMarkets']))+'</small>'+decision
    scopes = ' · '.join(f'{"Ev" if side == "home" else "Dep"}: {scope}, {d["teamCounts"][side]} maç' for side, scope in d['teamScopes'].items())
    choice = '<br>'.join(esc(label(sport,c['market'],c['option'])+' · '+pct(c['confidence'])) for c in entry.get('choices',[])) or 'Tahmin yok'
    return '<details class="calculation-detail"><summary>Hesap detayı <span aria-hidden="true">＋</span></summary><ol>'+\
           '<li><strong>Takım geçmişi</strong><small>'+esc(scopes)+'</small>'+''.join(lines)+'</li>'+\
           '<li><strong>Rekabet ve birleşik yüzdeler</strong>'+''.join(hlines)+'<small>Satırdaki yüzdeler: takım katkısı + rekabet katkısı.</small></li>'+\
           '<li><strong>İlk iki aday ve son maç kontrolü</strong>'+decision+'<small>'+esc(d['reason'])+'</small><div class="calculation-choice">Seçim:<br>'+choice+'</div></li></ol></details>'
