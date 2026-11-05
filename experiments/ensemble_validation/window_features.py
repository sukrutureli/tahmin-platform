"""All available 90-day team observations, no row quota; six-game form remains separate."""
import math,copy
from collections import defaultdict
from datetime import date
from history_context_trial import weight as broad_weight,WeightedContext as BroadContext

def prior(r,target):
    try:return 0<(date.fromisoformat(target)-date.fromisoformat(r['date'])).days<=90
    except (ValueError,TypeError,KeyError):return False

def pools(root,ledger,index,target,read):
    """Exact provider team IDs or same-event sides only. Never join team names."""
    teams=defaultdict(dict);events={};conflicts=set(ledger.get('conflictingMatchKeys',[]));rejected=0
    def put(bank,r,key):
        nonlocal rejected
        if key in conflicts:return
        if not prior(r,target):return
        if not all(isinstance(r.get(k),(int,float)) and math.isfinite(r[k]) and r[k]>=0 for k in ('for','against')):return
        if r.get('dateInferred'):rejected+=1;return
        old=bank.get(key)
        if old and (old['for'],old['against'],old['date'])!=(r['for'],r['against'],r['date']):
            rejected+=1;conflicts.add(key);bank.pop(key,None);return
        bank[key]=r
    for m in ledger['matches']:
        if m.get('key') in conflicts or not prior(m,target):continue
        for side in ('home','away'):
            other='away' if side=='home' else 'home';gf,ga=m[side+'Score'],m[other+'Score']
            ff,fa=m.get(side+'Final'),m.get(other+'Final');known=m['sport']=='football' or (ff is not None and fa is not None and ff!=fa)
            win=int(gf>ga) if m['sport']=='football' else int(ff>fa) if known else None
            r={'id':m['key'],'date':m['date'],'venue':side,'for':gf,'against':ga,'win':win,'draw':int(gf==ga) if m['sport']=='football' else 0 if known else None,'tournamentId':m.get('tournamentId')}
            put(teams[(m['sport'],m[side])],r,m['key'])
    journal=read(root/'live-history-journal.json')
    for day in journal:
        if day.get('targetDate','9999')>target:continue
        for event in day.get('fixtures',[]):
            sides=event.get('sides',[])
            if len(sides)!=2:continue
            key=(event['sport'],day['targetDate'],str(event['eventId']))
            pair=[]
            for side in sides:
                bank={}
                ns='broadage' if side.get('source')=='broadage-team-schedule' else 'nesine' if side.get('source')=='nesine-summary-general-and-venue' else None
                team=ns+':'+str(side['teamId']) if ns and side.get('teamId') else None
                for r in side.get('rows',[]):
                    mid=event['sport']+':'+str(ns)+':'+str(r.get('id'))
                    put(bank,copy.deepcopy(r),mid)
                    if team:put(teams[(event['sport'],team)],copy.deepcopy(r),mid)
                pair.append(bank)
            if day['targetDate']==target:events[key]=pair
    # An event missing a stable identity may still have exact original six-match rows.
    result={}
    for sport in ('football','basketball'):
        for row in read(root/(sport+'-replay.json')):
            if row['date']!=target:continue
            key=(sport,target,str(row['eventId']));ident=index.get(key);pair=[]
            for i,side in enumerate(('home','away')):
                bank=copy.deepcopy(teams.get((sport,ident[side]),{})) if ident else {}
                if key in events:bank.update(events[key][i])
                if not bank:
                    for variant in ('wide-balanced','six-simple'):
                        for r in row.get('variants',{}).get(variant,{}).get('audit',{}).get(side,{}).get('rows',[]):put(bank,copy.deepcopy(r),str(r.get('id')))
                pair.append(sorted([v for k,v in bank.items() if k not in conflicts],key=lambda r:(r['date'],str(r.get('id',''))),reverse=True))
            result[key]=pair
    return result,{'rejectedInferredOrConflicting':rejected,'source':'Existing exact-identity ledger, uncapped saved HTTP rows and original same-event audits; no new crawl. Ninety-day completeness is not guaranteed.'}

def w(r,target,sport,tournament,arm):
    if not prior(r,target):return 0.
    return broad_weight(r,target,sport,tournament,arm)
def features(row,sport,arm,ident):
    target=row['date'];tournament=(ident or {}).get('tournamentId');h,a=row['_window90Rows']
    def avg(rs,fn):
        pairs=[(fn(r),w(r,target,sport,tournament,arm)) for r in rs];pairs=[(v,q) for v,q in pairs if v is not None and q>0]
        total=sum(q for v,q in pairs)
        return sum(v*q for v,q in pairs)/total if total else None
    def margin(rs):return avg(rs,lambda r:r['for']-r['against'])
    counts=[len(h),len(a)];short=[h[:6],a[:6]]
    audit={'historyCounts':counts,'shortCounts':list(map(len,short)),'maximumMatches':None,'missingShort':not all(counts),'missingCompetition':not bool(tournament),
           'oldestAgeDays':[max(((date.fromisoformat(target)-date.fromisoformat(r['date'])).days for r in rs),default=None) for rs in (h,a)],
           'sameCompetitionCounts':[sum(bool(tournament) and str(r.get('tournamentId'))==str(tournament) for r in rs) for rs in (h,a)],
           'recentMargins':[margin(rs) if rs else None for rs in short]}
    if not all(counts):return {},audit
    hf,ha,af,aa=[avg(rs,lambda r,k=k:r[k]) for rs,k in [(h,'for'),(h,'against'),(a,'for'),(a,'against')]]
    f=dict(attackDefenceDiff=hf-af+aa-ha,absoluteStrengthDifference=abs(hf-af+aa-ha),expectedTotal=(hf+ha+af+aa)/2,
           minimumHistory=min(6,min(counts)),homeFor=hf,homeAgainst=ha,awayFor=af,awayAgainst=aa)
    def variance(rs):
        mu=avg(rs,lambda r:r['for']+r['against']);return avg(rs,lambda r:(r['for']+r['against']-mu)**2)
    f['totalSigma']=math.sqrt((variance(h)+variance(a))/2)
    hw,aw=avg(h,lambda r:r.get('win')),avg(a,lambda r:r.get('win'))
    if hw is not None and aw is not None:f['winRateDifference']=hw-aw
    hs,as_=short
    if len(hs)==6 and len(as_)==6:f['formTrendDifference']=(margin(hs[:3])-margin(hs[3:]))-(margin(as_[:3])-margin(as_[3:]))
    hv=[r for r in h if r.get('venue')=='home'];av=[r for r in a if r.get('venue')=='away']
    if len(hv)>=2 and len(av)>=2:
        f['venueMarginDifference']=margin(hv)-margin(av)
        f['venueExpectedTotal']=(avg(hv,lambda r:r['for']+r['against'])+avg(av,lambda r:r['for']+r['against']))/2
    if min(counts)>=10:
        f['recentVsWideMarginDifference']=(margin(hs)-margin(h))-(margin(as_)-margin(a));f['wideMinimumCount']=min(counts)
    if sport=='football':
        for key,fn in [('meanBlankRate',lambda r:int(r['for']==0)),('meanBttsRate',lambda r:int(r['for']>0 and r['against']>0)),('meanOverRate',lambda r:int(r['for']+r['against']>2.5))]:f[key]=(avg(h,fn)+avg(a,fn))/2
    else:
        line=(row.get('odds') or {}).get('hOverUnderValue',0)
        if line>0:f['expectedTotalMinusLine']=f['expectedTotal']-line
    return f,audit

class StrengthContext(BroadContext):
    def __init__(self,ledger,index,tournament,arm):
        # Broad opponent strength remains decayed, even in the plain 90-day arm.
        super().__init__(ledger,index,tournament,'combined' if arm in ('competition','combined') else 'recency')
    def features(self,row,sport):
        ident=self.index.get((sport,row['date'],str(row['eventId'])))
        if not ident:return {}
        target=row['date'];rows,rating,games,team=self.state(sport,target);h,a=ident['home'],ident['away']
        if not games[h] or not games[a]:return {}
        rh=rating[h]*games[h]/(games[h]+5);ra=rating[a]*games[a]/(games[a]+5)
        def adjusted(t):
            rs=team[t];ws=[broad_weight(r,target,sport,self.tournament,self.arm) for r,v,o in rs];total=sum(ws)
            return sum(v*q for (r,v,o),q in zip(rs,ws))/total,sum(o*q for (r,v,o),q in zip(rs,ws))/total
        hm,ho=adjusted(h);am,ao=adjusted(a)
        return dict(eloDifference=rh-ra,homeElo=rh,awayElo=ra,strengthMinimumMatches=min(games[h],games[a]),
                    opponentAdjustedMarginDifference=hm-am,homeOpponentStrength=ho,awayOpponentStrength=ao)
