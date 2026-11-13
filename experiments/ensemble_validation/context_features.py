"""Identity-safe, date-causal opponent/competition features; separate research ledger."""
import copy,hashlib,json,math,re,time,urllib.parse
from collections import defaultdict,Counter
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
from live_history import schedule_row,flatten,Client,RateLimitError,RequestBudgetError,dump

STRENGTH=['eloDifference','homeElo','awayElo','opponentAdjustedMarginDifference','homeOpponentStrength','awayOpponentStrength','strengthMinimumMatches']
LEAGUE=['leagueExpectedTotal','leagueHomeAdvantage','leagueTotalSigma','leagueMeanBtts','leagueMeanOver','leagueSampleCount','leagueRelativeExpectedTotal','sameLeagueHomeCount','sameLeagueAwayCount']


def number_id(value):
    return str(value) if isinstance(value,(str,int)) and str(value).isdigit() and int(value)>0 else None


def canonical(sport,namespace,own,row,collected):
    opponent=number_id(row.get('opponentId'));own=number_id(own)
    if not own or not opponent or own==opponent:return None
    if row.get('venue') not in ('home','away') or not row.get('regulationKnown'):return None
    values=[row.get('for'),row.get('against')]
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in values):return None
    home=row['venue']=='home';h,a=(own,opponent) if home else (opponent,own)
    gf,ga=values if home else list(reversed(values))
    ff,fa=(row.get('finalFor'),row.get('finalAgainst')) if home else (row.get('finalAgainst'),row.get('finalFor'))
    return {'key':sport+':'+namespace+':'+str(row['id']),'sport':sport,'namespace':namespace,'date':row['date'],
            'home':namespace+':'+h,'away':namespace+':'+a,'homeScore':gf,'awayScore':ga,'homeFinal':ff,'awayFinal':fa,
            'tournamentId':number_id(row.get('tournamentId')),'seasonId':row.get('seasonId'),
            'tournament':row.get('tournament',''),'firstCollectedAt':collected}


def merge_records(records):
    grouped=defaultdict(list)
    for r in records:grouped[r['key']].append(r)
    kept=[];conflicts=[]
    fields=['sport','namespace','date','home','away','homeScore','awayScore','homeFinal','awayFinal','tournamentId']
    for key,rs in grouped.items():
        if len({json.dumps([r.get(k) for k in fields]) for r in rs})>1:conflicts.append(key);continue
        kept.append(min(rs,key=lambda r:r.get('firstCollectedAt','9999')))
    return sorted(kept,key=lambda r:(r['date'],r['key'])),conflicts


def cache_records(root,request_rows,target,collected):
    root=Path(root);found=[];validated=set();payloads=[];rejected=0
    for req in request_rows:
        url=urllib.parse.urlsplit(req.get('url',''))
        if not url.path.endswith('/widget/team/schedule') or req.get('status')!=200 or not req.get('cache'):continue
        sport='football' if url.path.startswith('/soccer/') else 'basketball' if url.path.startswith('/basketball/') else None
        own=number_id(urllib.parse.parse_qs(url.query).get('teId',[None])[0])
        if not sport or not own:continue
        files=list(root.glob('http-cache/*/'+req['cache']))+list(root.glob('context-http-cache/*/'+req['cache']))
        if not files:continue
        data=json.loads(files[0].read_text()).get('data',{});mid=number_id(data.get('metaData',{}).get('team',{}).get('id'))
        if mid and mid!=own:rejected+=1;continue
        if mid==own:validated.add((sport,own))
        payloads.append((sport,own,data))
    for sport,own,data in payloads:
        if (sport,own) not in validated:rejected+=1;continue
        for raw in flatten(data.get('initialData')):
            r=schedule_row(raw,date.fromisoformat(target),sport)
            if not r:continue
            c=canonical(sport,'broadage',own,r,collected)
            if c:found.append(c)
    return found,rejected


def fixture_index(journal):
    result={}
    for day in journal:
        for f in day.get('fixtures',[]):
            if len(f.get('sides',[]))!=2:continue
            sides=f['sides'];ids=[];leagues=[]
            for side in sides:
                ns='broadage' if side.get('source')=='broadage-team-schedule' else 'nesine' if side.get('source')=='nesine-summary-general-and-venue' else None
                tid=number_id(side.get('teamId'));ids.append(ns+':'+tid if ns and tid else None)
                leagues.append(number_id(side.get('targetTournamentId')))
            if all(ids) and ids[0].split(':')[0]==ids[1].split(':')[0]:
                result[(f['sport'],day['targetDate'],str(f['eventId']))]={'home':ids[0],'away':ids[1],'namespace':ids[0].split(':')[0],
                   'tournamentId':leagues[0] if leagues[0]==leagues[1] else None,'collectedAt':f.get('collectedAt')}
    return result


def build_ledger(root,previous,target,extra_requests=(),extra_bindings=()):
    root=Path(root);previous=Path(previous) if previous else root
    old=previous/'context-ledger.json';prior=json.loads(old.read_text()) if old.exists() else {};records=prior.get('matches',[])
    journal=json.loads((root/'live-history-journal.json').read_text());live=json.loads((root/'live-history.json').read_text())
    current,rejected=cache_records(root,live.get('requests',[]),target,live.get('completedAt') or datetime.now(timezone.utc).isoformat());records+=current
    extra,extra_rejected=cache_records(root,list(extra_requests),target,datetime.now(timezone.utc).isoformat());records+=extra;rejected+=extra_rejected
    # New snapshots keep opponent IDs; old snapshots are never edited or name-joined.
    for day in journal:
        for f in day.get('fixtures',[]):
            for side in f.get('sides',[]):
                ns='broadage' if side.get('source')=='broadage-team-schedule' else 'nesine' if side.get('source')=='nesine-summary-general-and-venue' else None
                if not ns:continue
                for r in side.get('rows',[]):
                    if r.get('date','9999')>=day['targetDate']:continue
                    c=canonical(f['sport'],ns,side.get('teamId'),r,f.get('collectedAt',''))
                    if c:records.append(c)
    records,conflicts=merge_records(records);conflicts=sorted(set(conflicts)|set(prior.get('conflictingMatchKeys',[])));records=[r for r in records if r['key'] not in conflicts]
    index=fixture_index(journal);bindings={};identity_conflicts=list(prior.get('identityConflicts',[]))
    for binding in prior.get('identities',[])+list(extra_bindings):
        key=(binding['sport'],binding['date'],str(binding['eventId']))
        if list(key) in identity_conflicts:continue
        current=index.get(key) or bindings.get(key)
        if current and any(current.get(k)!=binding.get(k) for k in ['home','away','namespace','tournamentId']):identity_conflicts.append(list(key));continue
        bindings.setdefault(key,binding)
    for key,binding in bindings.items():
        if list(key) not in identity_conflicts:index.setdefault(key,binding)
    out={'identities':[b for k,b in bindings.items() if list(k) not in identity_conflicts],'identityConflicts':identity_conflicts,'createdAt':datetime.now(timezone.utc).isoformat(),'targetDate':target,'matches':records,'conflictingMatchKeys':conflicts,
         'rejectedCacheIdentities':rejected,'seasonPolicy':'Provider season ID if supplied; otherwise explicit missing. League features use trailing 365 days, no guessed season.',
         'policy':'IDs only; exact sport/provider namespaces; one row per finished match; all feature outcomes strictly before fixture day. Backfilled historical features are retrospective.'}
    dump(root/'context-ledger.json',out);return out,index


def identity_from_page(text,row,sport,collected):
    def field(name):
        m=re.search(r"model\."+name+r"\s*=\s*[\"']?(\d+)",text)
        if not m:return None
        return number_id(m[1])
    if field('SportId')!=('1' if sport=='football' else '2'):raise ValueError('Fixture sport mismatch')
    h,a=field('HomeTeamId'),field('AwayTeamId')
    if not h or not a or h==a:raise ValueError('Fixture team IDs absent')
    return {'sport':sport,'date':row['date'],'eventId':str(row['eventId']),'home':'broadage:'+h,'away':'broadage:'+a,'namespace':'broadage','tournamentId':field('TournamentId'),'collectedAt':collected,'source':'exact historical event p1 identity'}


def bounded_enrichment(root,target,ledger,seconds=90,max_teams=8,client=None,clock=time.monotonic,data=None,index=None,train_cutoffs=None):
    """One hop only, at most two endpoint-supplied months; shared serial 500ms client, global 429 stop."""
    root=Path(root);live=json.loads((root/'live-history.json').read_text());accounts={};bases={}
    for req in live.get('requests',[]):
        if req.get('status')!=200:continue
        u=urllib.parse.urlsplit(req.get('url',''))
        if u.path.endswith('/widget/team/schedule'):
            sport='football' if u.path.startswith('/soccer/') else 'basketball' if u.path.startswith('/basketball/') else None
            if sport:bases[sport]=urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,'',''))
        if req.get('cache','').endswith('.txt'):
            files=list(root.glob('http-cache/*/'+req['cache']))
            if not files:continue
            text=files[0].read_text();a=re.search(r'model\.AccountId\s*=\s*[\"\']?([\w-]+)',text);s=re.search(r'model\.SportId\s*=\s*[\"\']?(\d+)',text)
            if a and s:accounts['football' if s[1]=='1' else 'basketball' if s[1]=='2' else 'unknown']=a[1]
    counts=Counter();frequency=Counter()
    for m in ledger['matches']:
        if m['namespace']!='broadage':continue
        for k in ['home','away']:counts[m['sport'],m[k]]+=1
    by_key={m['key']:m for m in ledger['matches']}
    for f in live['fixtures']:
        for side in f['sides']:
            own='broadage:'+str(side.get('teamId'))
            for r in side['rows']:
                opponent=number_id(r.get('opponentId'))
                if opponent:frequency[f['sport'],'broadage:'+opponent]+=1
                elif side.get('source')=='broadage-team-schedule':
                    m=by_key.get(f['sport']+':broadage:'+str(r.get('id')))
                    if m and own in (m['home'],m['away']):frequency[f['sport'],m['away'] if own==m['home'] else m['home']]+=1
    if not frequency:
        frequency.update({k:1 for k in counts})
    # Alternate sports so the small budget cannot be monopolised by football.
    queues={s:sorted([k for k in frequency if k[0]==s and counts[k]<6],key=lambda k:(-frequency[k],counts[k],k[1])) for s in ['football','basketball']}
    chosen=[]
    while len(chosen)<max_teams and any(queues.values()):
        for s in queues:
            if queues[s] and len(chosen)<max_teams:chosen.append(queues[s].pop(0))
    start=clock();client=client or Client(root/'context-http-cache'/target,deadline=time.monotonic()+seconds);errors=[];done=[];rate_limited=False;budget=False
    bindings=[];identity_attempted=0;attempted=0
    if data and index is not None and train_cutoffs:
        context=Context(ledger,index);available={s:sum('eloDifference' in context.features(r,s) for r in rs if r['date']<train_cutoffs.get(s,'0000')) for s,rs in data.items()}
        pending=[(s,r) for s,rs in data.items() for r in rs if r['date']<train_cutoffs.get(s,'0000') and (s,r['date'],str(r['eventId'])) not in index]
        pending.sort(key=lambda sr:(available.get(sr[0],0)>=30,available.get(sr[0],0),-date.fromisoformat(sr[1]['date']).toordinal(),str(sr[1]['eventId'])))
        for sport,row in pending[:60]:
            if clock()-start>=seconds:budget=True;break
            identity_attempted+=1
            try:
                text=client.get('https://istatistik.nesine.com/p1/'+str(row['eventId']),text=True)
                bindings.append(identity_from_page(text,row,sport,datetime.now(timezone.utc).isoformat()))
            except RateLimitError:rate_limited=True;break
            except RequestBudgetError:budget=True;break
            except Exception as error:errors.append({'sport':sport,'eventId':str(row['eventId']),'reason':type(error).__name__})
    for sport,team in chosen:
        if rate_limited:break
        if clock()-start>=seconds:budget=True;break
        if sport not in bases or sport not in accounts:errors.append({'sport':sport,'team':team,'reason':'verified endpoint/account missing'});continue
        attempted+=1
        query={'teId':team.split(':')[1],'tId':0,'calculation':'overall','options':json.dumps({'lang':'tr-TR','timeZone':3,'rowPerPage':30},separators=(',',':'))}
        try:
            url=bases[sport]+'?'+urllib.parse.urlencode(query);first=client.get(url,accounts[sport]);data=first.get('data',{});meta=data.get('metaData',{})
            if str(meta.get('team',{}).get('id'))!=query['teId']:raise ValueError('Team ID mismatch')
            months=sorted([r['id'] for r in meta.get('rounds',[]) if isinstance(r.get('id'),int) and 190001<=r['id']<=int(target[:4]+target[5:7])],reverse=True)[:2]
            for month in months:
                if clock()-start>=seconds:budget=True;break
                if any(r.get('selected') and r.get('id')==month for r in meta.get('rounds',[])):continue
                client.get(bases[sport]+'?'+urllib.parse.urlencode(dict(query,rId=month)),accounts[sport])
            done.append({'sport':sport,'team':team})
        except RateLimitError:
            rate_limited=True;break
        except RequestBudgetError:
            budget=True;break
        except Exception as error:errors.append({'sport':sport,'team':team,'reason':type(error).__name__})
    audit={'targetDate':target,'attempted':attempted,'selectedTeamCount':len(chosen),'identityLookups':identity_attempted,'identityBindings':bindings,'completed':done,'errors':errors,'rateLimited':rate_limited,'budgetReached':budget,
           'maxTeams':max_teams,'maxSeconds':seconds,'requests':client.audit,'policy':'No recursive crawl; endpoint months only; missing coverage explicit; 429 stops all additional requests.'}
    dump(root/'context-enrichment.json',audit);return audit


class Context:
    def __init__(self,ledger,index):self.matches=ledger['matches'];self.index=index;self.cache={}
    def state(self,sport,cutoff):
        key=sport,cutoff
        if key in self.cache:return self.cache[key]
        rows=[m for m in self.matches if m['sport']==sport and m['date']<cutoff];rating=defaultdict(float);games=Counter();team=defaultdict(list)
        dates=defaultdict(list)
        for m in rows:dates[m['date']].append(m)
        for day,rs in sorted(dates.items()):
            updates=defaultdict(float)
            for m in rs:
                h,a=m['home'],m['away'];delta=rating[h]-rating[a];expected=1/(1+math.exp(-max(-20,min(20,delta))))
                hf,af=(m['homeScore'],m['awayScore']) if sport=='football' else (m['homeFinal'],m['awayFinal'])
                if hf is not None and af is not None and (sport=='football' or hf!=af):
                    actual=1 if hf>af else 0 if hf<af else .5;change=.15*(actual-expected);updates[h]+=change;updates[a]-=change
                # Adjusted margin uses only the opponent rating before this historical day's outcomes.
                scale=1 if sport=='football' else 10
                team[h].append((m,m['homeScore']-m['awayScore']+scale*rating[a],rating[a]));team[a].append((m,m['awayScore']-m['homeScore']+scale*rating[h],rating[h]))
                games[h]+=1;games[a]+=1
            for k,v in updates.items():rating[k]+=v
        self.cache[key]=(rows,rating,games,team);return self.cache[key]
    def features(self,row,sport):
        ident=self.index.get((sport,row['date'],str(row['eventId'])))
        if not ident:return {}
        rows,rating,games,team=self.state(sport,row['date']);h,a=ident['home'],ident['away'];out={}
        if games[h] and games[a]:
            # Sparse ratings pull towards zero; all constants are fixed development hypotheses.
            rh=rating[h]*games[h]/(games[h]+5);ra=rating[a]*games[a]/(games[a]+5)
            out.update(eloDifference=rh-ra,homeElo=rh,awayElo=ra,strengthMinimumMatches=min(games[h],games[a]))
            def adjusted(t):
                rs=team[t][-(20 if sport=='football' else 25):];return sum(x[1] for x in rs)/len(rs),sum(x[2] for x in rs)/len(rs)
            hm,ho=adjusted(h);am,ao=adjusted(a);out.update(opponentAdjustedMarginDifference=hm-am,homeOpponentStrength=ho,awayOpponentStrength=ao)
        start=(date.fromisoformat(row['date'])-timedelta(days=365)).isoformat();pool=[m for m in rows if m['date']>=start and m['namespace']==ident['namespace']]
        league=[m for m in pool if m['tournamentId']==ident['tournamentId']] if ident['tournamentId'] else []
        if pool and league:
            def mean(rs,fn):return sum(fn(r) for r in rs)/len(rs)
            total=lambda r:r['homeScore']+r['awayScore'];glob=mean(pool,total);weight=len(league)/(len(league)+30);mu=weight*mean(league,total)+(1-weight)*glob
            adv=weight*mean(league,lambda r:r['homeScore']-r['awayScore'])+(1-weight)*mean(pool,lambda r:r['homeScore']-r['awayScore'])
            variance=weight*mean(league,lambda r:(total(r)-mu)**2)+(1-weight)*mean(pool,lambda r:(total(r)-mu)**2)
            out.update(leagueExpectedTotal=mu,leagueHomeAdvantage=adv,leagueTotalSigma=math.sqrt(variance),leagueSampleCount=len(league),
                       sameLeagueHomeCount=sum(m['tournamentId']==ident['tournamentId'] for m,v,o in team[h]),sameLeagueAwayCount=sum(m['tournamentId']==ident['tournamentId'] for m,v,o in team[a]))
            if sport=='football':
                out['leagueMeanBtts']=weight*mean(league,lambda r:int(r['homeScore']>0 and r['awayScore']>0))+(1-weight)*mean(pool,lambda r:int(r['homeScore']>0 and r['awayScore']>0))
                out['leagueMeanOver']=weight*mean(league,lambda r:int(total(r)>2.5))+(1-weight)*mean(pool,lambda r:int(total(r)>2.5))
            from outcome_learning import features
            expected=features(row,sport).get('expectedTotal')
            if expected is not None:out['leagueRelativeExpectedTotal']=expected-mu
        return out
