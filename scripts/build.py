#!/usr/bin/env python3
"""戦国ガイド試作 build: content/{places,people,organization} の Markdown(+frontmatter) から
dist/data.json と試作ページ (dist/index.html + app.js) を生成する。
正本は Markdown。人と城館の相互リンク、城館の年表、領地のおおよその範囲はここで自動生成する。
"""
import json, math, re, shutil, sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
DIST = ROOT / "dist"
VENDOR_SRC = Path.home() / "workspace/markdown-cms/tendo-gourmet/dist/assets/vendor/leaflet"

HOUSE_COLORS = {"nagai": "#8a9a5b", "date": "#3f6d9e", "gamo": "#b3543f", "uesugi": "#7a5c9e"}
CLAN_COLORS = {"大町氏": "#e08a2e", "安久津氏": "#2e9e7b", "片倉氏（分家）": "#6aa84f"}
UNKNOWN_COLOR = "#9aa3ab"
STAGES = [
    {"from": 1189, "to": 1380, "name": "長井氏の時代", "house_id": "nagai"},
    {"from": 1380, "to": 1591, "name": "伊達氏の時代", "house_id": "date"},
    {"from": 1591, "to": 1598, "name": "蒲生氏の時代", "house_id": "gamo"},
    {"from": 1598, "to": 1615, "name": "上杉氏の時代", "house_id": "uesugi"},
]
ERAS = [
    {"id": "nagai", "label": "〜1380 長井氏の領地", "house_id": "nagai", "house": "長井氏"},
    {"id": "date", "label": "1380〜1591 伊達氏の時代（中の領主で色分け）", "house_id": "date", "house": "伊達氏"},
    {"id": "gamo", "label": "1591〜1598 蒲生氏の領地", "house_id": "gamo", "house": "蒲生氏"},
    {"id": "uesugi", "label": "1598〜 上杉氏の領地", "house_id": "uesugi", "house": "上杉氏"},
]

def parse_md(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        raise ValueError(f"frontmatter not found: {path}")
    return yaml.safe_load(m.group(1)), m.group(2).strip()

def hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0: lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0: upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]

def expand_polygon(poly, margin=0.022):
    cx = sum(p[0] for p in poly)/len(poly); cy = sum(p[1] for p in poly)/len(poly)
    out = []
    for x, y in poly:
        dx, dy = x-cx, y-cy
        d = math.hypot(dx, dy) or 1.0
        out.append([round(y + dy + dy/d*margin, 5), round(x + dx + dx/d*margin, 5)])  # [lat, lng]
    return out

def main():
    errors = []
    places, people, orgs = [], {}, []
    for path in sorted((CONTENT/"places").glob("*.md")):
        fm, body = parse_md(path)
        fm["body_md"] = body; fm["_file"] = path.name
        places.append(fm)
    for path in sorted((CONTENT/"people").glob("*.md")):
        fm, body = parse_md(path)
        fm["body_md"] = body; fm["_file"] = path.name
        people[fm["id"]] = fm
    for path in sorted((CONTENT/"organization").glob("*.md")):
        fm, body = parse_md(path)
        fm["body_md"] = body; fm["_file"] = path.name
        orgs.append(fm)

    places.sort(key=lambda p: (p.get("number") is None, p.get("number") or 0))
    ids = [p["id"] for p in places]
    if len(ids) != len(set(ids)): errors.append("place id duplicated")
    for p in places:
        if (p.get("lat") is None) != (p.get("lng") is None):
            errors.append(f"{p['id']}: lat/lng must be both set or both null")
        if p.get("lat") is not None and not (30 < p["lat"] < 46 and 129 < p["lng"] < 147):
            errors.append(f"{p['id']}: coordinates out of Japan range")
        if p["_file"] != p["id"] + ".md": errors.append(f"file/id mismatch: {p['_file']}")
        for q in p.get("related_places", []):
            qid = q.get("place_id") if isinstance(q, dict) else q
            if qid not in ids: errors.append(f"{p['id']}: related_place missing {q}")
        for e in p.get("events_timeline", []):
            for pid in e.get("person_ids", []):
                if pid not in people: errors.append(f"{p['id']}: event person missing {pid}")
    for pid, person in people.items():
        for s in person.get("stays", []):
            if s["place_id"] not in ids: errors.append(f"{pid}: stay place missing {s['place_id']}")
        for r in person.get("related_people", []):
            if r["person_id"] not in people: errors.append(f"{pid}: related person missing {r['person_id']}")
    for org in orgs:
        for lv in org.get("levels", []):
            for pid in lv.get("examples", []):
                if pid not in people: errors.append(f"org {org['id']}: example person missing {pid}")
        def walk(node):
            if isinstance(node, dict):
                pid = node.get("person_id")
                if pid and pid not in people: errors.append(f"org {org['id']}: tree person missing {pid}")
                for v in node.values(): walk(v)
            elif isinstance(node, list):
                for v in node: walk(v)
        walk(org.get("tree", {}))

    # people -> places (単一の正: stays は人物側)
    for p in places:
        ppl = []
        for pid, person in people.items():
            for s in person.get("stays", []):
                if s["place_id"] == p["id"]:
                    ppl.append({"person_id": pid, "name": person["name"], "role": s.get("role"),
                                "from": s.get("from"), "to": s.get("to"), "certainty": s.get("certainty")})
        p["people"] = sorted(ppl, key=lambda x: (x["from"] or 0))
    for pid, person in people.items():
        pls = []
        for s in person.get("stays", []):
            pl = next(x for x in places if x["id"] == s["place_id"])
            pls.append({"place_id": pl["id"], "place_name": pl["name"], "role": s.get("role"),
                        "from": s.get("from"), "to": s.get("to")})
        person["places"] = pls

    # timelines per place
    for p in places:
        hist = [e for e in p.get("events_timeline", []) if e.get("era") == "historical"]
        modern = [e for e in p.get("events_timeline", []) if e.get("era") == "modern"]
        years = [e["sort_year"] for e in hist] + [s["from"] for s in p["people"] if s.get("from")] + [1598]
        start = (min(years) // 10) * 10 - 10 if years else 1400
        end = 1610
        events = []
        for e in sorted(hist, key=lambda x: x["sort_year"]):
            at = []
            for s in p["people"]:
                if s.get("from") and s["from"] <= e["sort_year"] <= (s.get("to") or s["from"]):
                    at.append(s["person_id"])
            for pid in e.get("person_ids", []):
                if pid not in at: at.append(pid)
            events.append({"sort_year": e["sort_year"], "year_label": e["year_label"], "text": e["text"],
                           "persons_at": [{"person_id": pid, "name": people[pid]["name"]} for pid in at]})
        stages = []
        for st in STAGES:
            a, b = max(st["from"], start), min(st["to"], end)
            if a < b:
                stages.append({**st, "color": HOUSE_COLORS[st["house_id"]],
                               "left_pct": round((a-start)/(end-start)*100, 2),
                               "width_pct": round((b-a)/(end-start)*100, 2)})
        p["timeline"] = {"window": {"start": start, "end": end}, "stages": stages,
                         "events": events,
                         "modern_events": [{"year_label": e["year_label"], "text": e["text"]} for e in modern]}

    # territories
    coord_places = [p for p in places if p.get("lat") is not None]
    pts = [(p["lng"], p["lat"]) for p in coord_places]
    area = expand_polygon(hull(pts)) if len(pts) >= 3 else []
    territories = {"area_polygon": area, "eras": ERAS, "house_colors": HOUSE_COLORS,
                   "local_areas": []}
    for p in coord_places:
        t = p.get("territory") or {}
        clan = t.get("local_clan")
        territories["local_areas"].append({
            "place_id": p["id"], "place_name": p["name"], "lat": p["lat"], "lng": p["lng"],
            "clan": clan, "label": clan if clan else "領主不明（伊達家の地）",
            "color": CLAN_COLORS.get(clan, UNKNOWN_COLOR),
            "radius_m": t.get("approx_radius_m", 1200),
            "basis": t.get("basis", ""), "certainty": t.get("certainty", "approximate")})

    # org map background (static map image + projected points)
    orgmap = None
    meta_path = ROOT / "assets" / "nagai-map-bg.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        def merc_y(lat):
            r = math.radians(lat)
            return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2
        y_top, y_bot = merc_y(meta["max_lat"]), merc_y(meta["min_lat"])
        def proj(lat, lng):
            xp = (lng - meta["min_lng"]) / (meta["max_lng"] - meta["min_lng"]) * 100
            yp = (merc_y(lat) - y_top) / (y_bot - y_top) * 100
            return {"x_pct": round(xp, 2), "y_pct": round(yp, 2),
                    "x": round(xp / 100 * meta["width"]), "y": round(yp / 100 * meta["height"])}
        orgmap = {**meta, "points": {pl["id"]: proj(pl["lat"], pl["lng"]) for pl in places if pl.get("lat") is not None},
                  "lord": {"x_pct": 50.0, "y_pct": 96.5,
                           "x": round(0.5 * meta["width"]), "y": round(0.965 * meta["height"])}}

    for p in places: p.pop("_file", None)
    for person in people.values(): person.pop("_file", None)
    for org in orgs: org.pop("_file", None)

    data = {"places": places, "people": list(people.values()), "organizations": orgs,
            "territories": territories, "orgmap": orgmap,
            "meta": {"note": "試作データ。座標は地理院地図・OpenStreetMapで取り直し、領地の範囲は推定（目安）。文章はオリジナル。",
                     "places_count": len(places), "people_count": len(people)}}
    if errors:
        print("VALIDATION ERRORS:"); [print(" -", e) for e in errors]; sys.exit(1)
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST/"data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (DIST/"index.html").write_text(SHELL, encoding="utf-8")
    (DIST/"app.js").write_text(APP_JS, encoding="utf-8")
    bg_src = ROOT / "assets" / "nagai-map-bg.png"
    if bg_src.exists():
        (DIST / "assets").mkdir(parents=True, exist_ok=True)
        shutil.copy(bg_src, DIST / "assets" / "nagai-map-bg.png")
    vendor_dst = DIST/"assets/vendor/leaflet"
    if VENDOR_SRC.exists():
        shutil.copytree(VENDOR_SRC, vendor_dst, dirs_exist_ok=True)
    print(f"OK: places={len(places)} people={len(people)} orgs={len(orgs)} -> {DIST}")

SHELL = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>戦国ガイド試作 ― 長井市の城館</title>
<link rel="stylesheet" href="assets/vendor/leaflet/leaflet.css">
<style>
body{margin:0;font-family:"Hiragino Mincho ProN","Yu Mincho",serif;background:#f7f5ef;color:#26303a}
header{background:#2e4a62;color:#f5f2eb;padding:14px 18px;display:flex;gap:14px;align-items:flex-start}
header .t{font-size:20px;font-weight:700}
header .s{font-size:12px;opacity:.85;margin-top:4px;max-width:860px;line-height:1.6}
#nav-toggle{display:none;background:transparent;border:1px solid rgba(255,255,255,.55);border-radius:8px;width:42px;height:42px;flex:0 0 42px;cursor:pointer;padding:10px 9px}
#nav-toggle span{display:block;height:2px;background:#f5f2eb;margin:4px 0;border-radius:2px}
.layout{display:flex;align-items:flex-start;max-width:1320px;margin:0 auto}
#sidebar{width:250px;flex:0 0 250px;position:sticky;top:0;height:100vh;overflow-y:auto;background:#fff;border-right:1px solid #d5dbe2;padding:18px 14px;box-sizing:border-box}
#sidebar .side-t{font-weight:700;font-size:14px;margin-bottom:8px}
#sidenav h4{font-size:12px;color:#68707a;margin:16px 0 6px;letter-spacing:.08em}
#sidenav a{display:block;padding:7px 10px;border-radius:8px;color:#26303a;text-decoration:none;font-size:13.5px;line-height:1.5}
#sidenav a:hover{background:#f2f5f8}
#sidenav a small{color:#68707a}
.content-wrap{flex:1;min-width:0}
main{max-width:1060px;margin:0 auto;padding:16px 14px 40px}
#nav-scrim{display:none}
#map{height:440px;border-radius:12px;border:1px solid #d5dbe2}
.eras{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.era-btn{font-size:12px;padding:7px 12px;border-radius:999px;border:1px solid #b9c2cc;background:#fff;cursor:pointer}
.era-btn.on{background:#2e4a62;color:#fff;border-color:transparent}
.note{font-size:12px;color:#68707a;line-height:1.7}
.card{background:#fff;border:1px solid #d5dbe2;border-radius:12px;padding:16px 18px;margin:18px 0}
.card h2{margin:0 0 4px;font-size:19px}.card h3{margin:16px 0 6px;font-size:15px}
.meta{font-size:12px;color:#68707a}
.chip{display:inline-block;font-size:12px;padding:3px 10px;border-radius:999px;border:1px solid #b9c2cc;background:#f2f5f8;margin:2px 4px 2px 0;text-decoration:none;color:#2e4a62}
.chip:hover{border-color:#2e4a62}
.body p{line-height:1.9;margin:8px 0}.body li{line-height:1.8}
.tl{position:relative;height:30px;border-radius:8px;overflow:hidden;border:1px solid #d5dbe2;margin:8px 0 4px;background:#eee}
.tl-band{position:absolute;top:0;height:30px;color:#fff;font-size:11px;line-height:30px;padding-left:8px;white-space:nowrap;overflow:hidden}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #e3e7ec;padding:6px 8px;text-align:left;vertical-align:top}
.term{border-top:1px solid #e3e7ec;padding:8px 0}.term b{font-size:14px}.term span{font-size:13px;line-height:1.7}
.flash{outline:3px solid #e08a2e;transition:outline .3s}
#orgmap{margin:10px 0}
.orgmap-wrap{position:relative;border:1px solid #d5dbe2;border-radius:12px;overflow:hidden;background:#e8ecef}
.orgmap-wrap img{width:100%;display:block}
.orgmap-svg{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}
.org-chip{position:absolute;transform:translate(-50%,-125%);background:rgba(255,255,255,.94);border:1px solid #2e4a62;border-radius:8px;padding:3px 8px;font-size:11px;white-space:nowrap;color:#26303a;z-index:2;line-height:1.5}
.org-chip.lord{transform:translate(-50%,-50%);background:#2e4a62;color:#fff;font-weight:700;font-size:12px}
.tree{list-style:none;padding-left:18px;position:relative}
.tree li{position:relative;padding:4px 0 4px 14px}
.tree li::before{content:'';position:absolute;left:-8px;top:0;bottom:0;border-left:2px solid #b9c2cc}
.tree li::after{content:'';position:absolute;left:-8px;top:20px;width:16px;border-top:2px solid #b9c2cc}
.tree>li::before{border-left:none}
.tnode{background:#f2f5f8;border:1px solid #d5dbe2;border-radius:8px;padding:6px 10px;display:inline-block;font-size:13px}
.tnode a{color:#2e4a62;font-weight:700}
footer{max-width:1060px;margin:0 auto;padding:14px;font-size:12px;color:#68707a;line-height:1.7}
@media (max-width:900px){
  #nav-toggle{display:block}
  #sidebar{position:fixed;left:0;top:0;z-index:1300;height:100dvh;transform:translateX(-106%);transition:transform .25s ease;box-shadow:0 0 32px rgba(0,0,0,.25)}
  body.nav-open #sidebar{transform:none}
  #nav-scrim{position:fixed;inset:0;background:rgba(20,28,36,.45);z-index:1250}
  body.nav-open #nav-scrim{display:block}
  #map{height:360px}
  .org-chip{font-size:10px;padding:2px 6px}
}
</style></head><body>
<header><button id="nav-toggle" aria-label="メニューを開く"><span></span><span></span><span></span></button>
<div><div class="t">戦国ガイド試作 ― 長井市の城館</div>
<div class="s">置賜の戦国を、城館・人物・年表・領地の地図で読む試作ページです。座標は地理院地図とOpenStreetMapで取り直し、文章はすべて書き下ろし。領地の色分けは境界の史料がないため、城館を中心とする推定の目安です。</div></div></header>
<div id="nav-scrim"></div>
<div class="layout">
<aside id="sidebar"><div class="side-t">目次</div><nav id="sidenav"></nav>
<div class="note" style="margin-top:16px">試作（長井市5館）。データの正本は Markdown ファイルで、城館データはゲーム『奥羽一生録』と共通です。</div></aside>
<div class="content-wrap">
<main>
<section id="map-top">
<div id="map"></div>
<div class="eras" id="eras"></div>
<div class="note">時代を選ぶと、地図の色分けがその時代の領主に切り替わります。色のついた範囲やピンを押すと、その城館の紹介へ飛びます。</div>
</section>
<div id="places"></div>
<div id="people"></div>
<div id="org"></div>
</main>
<footer>試作として公開中。座標・領地の範囲は推定を含むため、各紹介の注記を確認してください。</footer>
</div>
</div>
<script src="assets/vendor/leaflet/leaflet.js"></script>
<script src="app.js"></script>
</body></html>
"""

APP_JS = r"""
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function md(t){
  const lines = String(t||'').split('\n'); let html='', list=false;
  for(const ln of lines){
    if(ln.startsWith('## ')){ if(list){html+='</ul>';list=false;} html += '<h3>'+esc(ln.slice(3))+'</h3>'; }
    else if(ln.startsWith('- ')){ if(!list){html+='<ul>';list=true;} html += '<li>'+esc(ln.slice(2))+'</li>'; }
    else if(ln.trim()){ if(list){html+='</ul>';list=false;} html += '<p>'+esc(ln)+'</p>'; }
  }
  if(list) html+='</ul>';
  return html;
}
function goTo(id){
  const el = document.getElementById(id); if(!el) return;
  el.scrollIntoView({behavior:'smooth', block:'start'});
  el.classList.add('flash'); setTimeout(()=>el.classList.remove('flash'), 1600);
  history.replaceState(null,'','#'+id);
}
let DATA=null, map=null, territoryLayer=null;
function drawEra(eraId){
  if(!map) return;
  if(territoryLayer) territoryLayer.remove();
  territoryLayer = L.layerGroup();
  const T = DATA.territories;
  if(eraId === 'date'){
    L.polygon(T.area_polygon, {color:T.house_colors.date, weight:1, fillColor:T.house_colors.date, fillOpacity:.10}).addTo(territoryLayer);
    T.local_areas.forEach(a=>{
      const c = L.circle([a.lat,a.lng], {radius:a.radius_m, color:a.color, weight:1.5, fillColor:a.color, fillOpacity:.35});
      c.bindTooltip(a.place_name+' ― '+(a.clan ? a.clan+'の地（推定）' : '領主不明'));
      c.on('click', ()=>goTo('place-'+a.place_id));
      c.addTo(territoryLayer);
    });
  } else {
    const era = T.eras.find(e=>e.id===eraId);
    const poly = L.polygon(T.area_polygon, {color:T.house_colors[era.house_id], weight:2, fillColor:T.house_colors[era.house_id], fillOpacity:.30});
    poly.bindTooltip(era.house+'の領地（推定の範囲）');
    poly.addTo(territoryLayer);
  }
  territoryLayer.addTo(map);
}
async function main(){
  DATA = await (await fetch('data.json')).json();
  // sidebar navigation
  const nav = $('#sidenav');
  if(nav){
    nav.innerHTML =
      '<h4>地図</h4><a href="#map-top" data-go="map-top">領地の色分け地図</a>'
      + '<h4>城館</h4>' + DATA.places.map(p=>'<a href="#place-'+p.id+'" data-go="place-'+p.id+'">'+p.number+'. '+esc(p.name)+' <small>'+esc(p.yomi)+'</small></a>').join('')
      + '<h4>人物</h4>' + DATA.people.map(x=>'<a href="#person-'+x.id+'" data-go="person-'+x.id+'">'+esc(x.name)+'</a>').join('')
      + '<h4>仕組み</h4>' + DATA.organizations.map(o=>'<a href="#org-'+o.id+'" data-go="org-'+o.id+'">'+esc(o.name)+'（組織図）</a>').join('');
  }
  const toggle = $('#nav-toggle'), scrim = $('#nav-scrim');
  if(toggle) toggle.addEventListener('click', ()=>document.body.classList.toggle('nav-open'));
  if(scrim) scrim.addEventListener('click', ()=>document.body.classList.remove('nav-open'));
  map = L.map('map');
  const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'© OpenStreetMap contributors', maxZoom:18});
  const gsi = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', {attribution:'地理院タイル', maxZoom:18});
  const photo = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg', {attribution:'地理院タイル（航空写真）', maxZoom:18});
  gsi.addTo(map);
  L.control.layers({'地理院 標準':gsi, 'OpenStreetMap':osm, '航空写真':photo}).addTo(map);
  const pts = DATA.places.filter(p=>p.lat!=null).map(p=>[p.lat,p.lng]);
  if(pts.length) map.fitBounds(pts, {padding:[30,30]}); else map.setView([38.1,140.02], 11);
  DATA.places.filter(p=>p.lat!=null).forEach(p=>{
    const m = L.marker([p.lat,p.lng]).addTo(map);
    m.bindPopup('<b>'+esc(p.name)+'</b><br>'+esc(p.summary)+'<br><a href="#place-'+p.id+'" data-go="place-'+p.id+'">紹介を読む →</a>');
    m.on('click', ()=>{});
  });
  const erasEl = $('#eras');
  DATA.territories.eras.forEach((e,i)=>{
    const b = document.createElement('button');
    b.className = 'era-btn' + (i===1 ? ' on' : ''); b.textContent = e.label;
    b.onclick = ()=>{ document.querySelectorAll('.era-btn').forEach(x=>x.classList.remove('on')); b.classList.add('on'); drawEra(e.id); };
    erasEl.appendChild(b);
  });
  drawEra('date');
  document.addEventListener('click', ev=>{
    const a = ev.target.closest('[data-go]'); if(!a) return;
    ev.preventDefault(); document.body.classList.remove('nav-open'); goTo(a.dataset.go);
  });
  // places
  $('#places').innerHTML = DATA.places.map(p=>{
    const tl = p.timeline;
    const bands = tl.stages.map(s=>'<div class="tl-band" style="left:'+s.left_pct+'%;width:'+s.width_pct+'%;background:'+s.color+'">'+esc(s.name)+'</div>').join('');
    const rows = tl.events.map(e=>'<tr><td style="white-space:nowrap">'+esc(e.year_label)+'</td><td>'+esc(e.text)+'</td><td>'+(e.persons_at.length ? e.persons_at.map(x=>'<a class="chip" href="#person-'+x.person_id+'" data-go="person-'+x.person_id+'">'+esc(x.name)+'</a>').join('') : '<span class="meta">―</span>')+'</td></tr>').join('');
    const modern = tl.modern_events.length ? '<h3>その後</h3>'+tl.modern_events.map(e=>'<p class="note">'+esc(e.year_label)+'：'+esc(e.text)+'</p>').join('') : '';
    const ppl = p.people.length ? '<h3>この城にいた人物</h3>'+p.people.map(x=>'<a class="chip" href="#person-'+x.person_id+'" data-go="person-'+x.person_id+'">'+esc(x.name)+'（'+esc(x.role||'')+'）</a>').join('') : '';
    return '<section class="card" id="place-'+p.id+'"><h2>'+p.number+'. '+esc(p.name)+'（'+esc(p.yomi)+'）</h2>'
      +'<div class="meta">'+esc(p.address)+' ／ '+esc(p.castle_type)+' ／ '+(p.lat!=null ? '座標の確かさ: '+esc(p.coord_precision) : '座標はこれから（説明を先に公開し、近似または本人の現地写真で確定する）')+'</div>'
      +'<div class="body"><p>'+esc(p.summary)+'</p>'+md(p.body_md)+'</div>'
      + ppl
      + '<h3>年表 ― その頃、誰がいたか</h3><div class="tl">'+bands+'</div>'
      + '<div class="meta">'+tl.window.start+'年 〜 '+tl.window.end+'年（帯は領主の時代）</div>'
      + '<table><tr><th>時期</th><th>出来事</th><th>その頃この城にいた人物</th></tr>'+rows+'</table>'
      + modern
      + '<p class="note">'+esc(p.visit_note||'')+'</p></section>';
  }).join('');
  // people
  $('#people').innerHTML = '<h2 style="margin:22px 0 4px">人物</h2>' + DATA.people.map(x=>{
    const places = (x.places||[]).map(s=>'<a class="chip" href="#place-'+s.place_id+'" data-go="place-'+s.place_id+'">'+esc(s.place_name)+'（'+esc(s.role||'')+'）</a>').join('');
    const pyr = x.org_position ? '<div class="meta">組織図の中の位置： '+esc(x.org_position.level_name)+' ― <a href="#org-date-house" data-go="org-date-house">伊達家の組織図</a>／役職のことば： '+(x.org_position.role_terms||[]).map(t=>'<a href="#term-'+esc(t)+'" data-go="term-'+esc(t)+'">'+esc(t)+'</a>').join('、')+'</div>' : '';
    const rel = (x.related_people||[]).map(r=>'<a class="chip" href="#person-'+r.person_id+'" data-go="person-'+r.person_id+'">'+esc(DATA.people.find(q=>q.id===r.person_id)?.name||r.person_id)+'</a>').join('');
    return '<section class="card" id="person-'+x.id+'"><h2>'+esc(x.name)+(x.alias?'（'+esc(x.alias)+'）':'')+'</h2>'
      +'<div class="meta">'+esc(x.clan||'')+' ／ '+(x.born? x.born+'〜'+x.died : (x.lifespan_note||''))+'</div>'+pyr
      +'<div class="body"><p>'+esc(x.summary)+'</p>'+md(x.body_md)+'</div>'
      +(places?'<h3>関わる城館</h3>'+places:'')+(rel?'<h3>関係する人物</h3>'+rel:'')+'</section>';
  }).join('');
  // organization
  function treeNode(n){
    let h = '<li><div class="tnode">';
    const pp = n.person_id ? DATA.people.find(q=>q.id===n.person_id) : null;
    if(n.label) h += esc(n.label);
    if(pp) h += (n.label ? ' ― ' : '') + '<a href="#person-'+pp.id+'" data-go="person-'+pp.id+'">'+esc(pp.name)+'</a>';
    if(n.note) h += '<div class="meta">'+esc(n.note)+'</div>';
    h += '</div>';
    if(n.children && n.children.length) h += '<ul class="tree">'+n.children.map(treeNode).join('')+'</ul>';
    return h + '</li>';
  }
  $('#org').innerHTML = DATA.organizations.map(o=>{
    const root = Object.assign({}, o.tree.root, {children: o.tree.children||[]});
    const tree = '<ul class="tree">'+treeNode(root)+'</ul>';
    const levels = o.levels.map(lv=>'<div class="term"><b>'+lv.level+'. '+esc(lv.name)+'</b><br><span>'+esc(lv.description)+'</span></div>').join('');
    const terms = o.terms.map(t=>'<div class="term" id="term-'+esc(t.term)+'"><b>'+esc(t.term)+'（'+esc(t.yomi)+'）</b><br><span>'+esc(t.description)+'</span></div>').join('');
    return '<section class="card" id="org-'+o.id+'"><h2>'+esc(o.title)+'</h2><div class="body">'+md(o.body_md)+'</div>'
      +'<h3>組織図 ― 背景は長井の地図</h3><div id="orgmap"></div>'
      +'<div class="note">当主（米沢方面・南）から各城館へ線が伸びています。城館の札には、その地の領主の氏と、いた人物の名前を入れました。</div>'
      + tree
      +'<h3>家格の段（参考）</h3>'+levels+'<h3>役職・序列のことば</h3>'+terms+'</section>';
  }).join('');
  // org map: hierarchy over a static map image
  if(DATA.orgmap && document.getElementById('orgmap')){
    const om = DATA.orgmap, W = om.width, H = om.height;
    let lines = '';
    DATA.territories.local_areas.forEach(a=>{
      const pt = om.points[a.place_id];
      lines += '<line x1="'+om.lord.x+'" y1="'+om.lord.y+'" x2="'+pt.x+'" y2="'+pt.y+'" stroke="#2e4a62" stroke-width="3" stroke-dasharray="9 7" opacity="0.75"/>';
      lines += '<circle cx="'+pt.x+'" cy="'+pt.y+'" r="9" fill="'+a.color+'" stroke="#fff" stroke-width="3"/>';
    });
    let chips = DATA.territories.local_areas.map(a=>{
      const pt = om.points[a.place_id];
      const ppl = (DATA.places.find(p=>p.id===a.place_id).people||[]).map(x=>x.name).join('・');
      return '<span class="org-chip" style="left:'+pt.x_pct+'%;top:'+pt.y_pct+'%"><b>'+esc(a.place_name)+'</b> '+esc(a.clan||'領主不明')+(ppl? '<br>'+esc(ppl):'')+'</span>';
    }).join('');
    chips += '<span class="org-chip lord" style="left:'+om.lord.x_pct+'%;top:'+om.lord.y_pct+'%">伊達家当主 政宗（本拠・米沢は南）</span>';
    document.getElementById('orgmap').innerHTML =
      '<div class="orgmap-wrap"><img src="assets/nagai-map-bg.png" alt="長井市の地図">'
      + '<svg class="orgmap-svg" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'+lines+'</svg>'
      + chips + '</div><div class="note">背景は地理院タイル（標準地図）を切り出した画像です。</div>';
  }
  if(location.hash){ const id = location.hash.slice(1); setTimeout(()=>goTo(id), 300); }
}
main();
"""

if __name__ == "__main__":
    main()
