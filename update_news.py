#!/usr/bin/env python3
"""Build a static, source-linked roster news feed for GitHub Pages."""
import concurrent.futures, datetime as dt, email.utils, json, os, pathlib, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text()
m=re.search(r'var PUBLISHED_LEAGUE_ID = "(\d+)";',HTML)
if not m: raise SystemExit('Published league ID missing')
LEAGUE=m.group(1)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; APFFNewsBot/1.0)'}
def get(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=18) as r: return r.read()
def api(path): return json.loads(get('https://api.sleeper.app/v1'+path))
def articles(player):
    name=player['name']; query='"'+name+'" NFL when:7d'
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})
    try:
        root=ET.fromstring(get(url)); out=[]
        for item in root.findall('./channel/item')[:5]:
            title=(item.findtext('title') or '').strip(); link=(item.findtext('link') or '').strip()
            source=item.find('source'); publisher=(source.text or '').strip() if source is not None else 'Google News'
            published=item.findtext('pubDate') or ''
            try: stamp=email.utils.parsedate_to_datetime(published).astimezone(dt.timezone.utc)
            except Exception: continue
            if not link.startswith('https://') or not title: continue
            if name.casefold() not in title.casefold(): continue
            if (dt.datetime.now(dt.timezone.utc)-stamp).days>8: continue
            out.append({'player_id':player['id'],'player':name,'position':player['position'],'title':title,'url':link,'source':publisher,'published':stamp.isoformat()})
        return out
    except Exception as exc:
        print('Feed unavailable:',name,str(exc)[:100]); return []
def main():
    rosters=api('/league/'+LEAGUE+'/rosters'); players=api('/players/nfl')
    lookup={}; roster_players={}
    for r in rosters:
        rid=str(r['roster_id']); ids=list(dict.fromkeys((r.get('starters') or [])+(r.get('players') or [])))
        roster_players[rid]=[str(x) for x in ids if x and x!='0']
        for pid in roster_players[rid]:
            p=players.get(pid) or {}; name=p.get('full_name') or (str(p.get('first_name') or '')+' '+str(p.get('last_name') or '')).strip()
            if name and p.get('position') in ('QB','RB','WR','TE','K','LB','DL','DE','DT','DB','CB','S'):
                lookup[pid]={'id':pid,'name':name,'position':p.get('position')}
    # Favor starters, but include the full roster when gathering candidates.
    selected=list(lookup.values()); print('Fetching',len(selected),'player feeds')
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for items in pool.map(articles,selected): results.extend(items)
    seen=set(); unique=[]
    for a in sorted(results,key=lambda x:x['published'],reverse=True):
        key=(a['player_id'],a['title'].casefold())
        if key not in seen: seen.add(key); unique.append(a)
    previous=ROOT/'data'/'team-news.json'
    if not unique and previous.exists():
        print('No new results; preserving last successful news file'); return
    payload={'league_id':LEAGUE,'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'articles':unique[:1000]}
    previous.parent.mkdir(exist_ok=True);previous.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print('Saved',len(payload['articles']),'articles')
if __name__=='__main__': main()
