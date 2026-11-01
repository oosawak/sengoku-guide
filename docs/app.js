
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
  map = L.map('map');
  const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'© OpenStreetMap contributors', maxZoom:18});
  const gsi = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', {attribution:'地理院タイル', maxZoom:18});
  const photo = L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg', {attribution:'地理院タイル（航空写真）', maxZoom:18});
  gsi.addTo(map);
  L.control.layers({'地理院 標準':gsi, 'OpenStreetMap':osm, '航空写真':photo}).addTo(map);
  const pts = DATA.places.map(p=>[p.lat,p.lng]);
  map.fitBounds(pts, {padding:[30,30]});
  DATA.places.forEach(p=>{
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
    ev.preventDefault(); goTo(a.dataset.go);
  });
  // places
  $('#places').innerHTML = DATA.places.map(p=>{
    const tl = p.timeline;
    const bands = tl.stages.map(s=>'<div class="tl-band" style="left:'+s.left_pct+'%;width:'+s.width_pct+'%;background:'+s.color+'">'+esc(s.name)+'</div>').join('');
    const rows = tl.events.map(e=>'<tr><td style="white-space:nowrap">'+esc(e.year_label)+'</td><td>'+esc(e.text)+'</td><td>'+(e.persons_at.length ? e.persons_at.map(x=>'<a class="chip" href="#person-'+x.person_id+'" data-go="person-'+x.person_id+'">'+esc(x.name)+'</a>').join('') : '<span class="meta">―</span>')+'</td></tr>').join('');
    const modern = tl.modern_events.length ? '<h3>その後</h3>'+tl.modern_events.map(e=>'<p class="note">'+esc(e.year_label)+'：'+esc(e.text)+'</p>').join('') : '';
    const ppl = p.people.length ? '<h3>この城にいた人物</h3>'+p.people.map(x=>'<a class="chip" href="#person-'+x.person_id+'" data-go="person-'+x.person_id+'">'+esc(x.name)+'（'+esc(x.role||'')+'）</a>').join('') : '';
    return '<section class="card" id="place-'+p.id+'"><h2>'+p.number+'. '+esc(p.name)+'（'+esc(p.yomi)+'）</h2>'
      +'<div class="meta">'+esc(p.address)+' ／ '+esc(p.castle_type)+' ／ 座標の確かさ: '+esc(p.coord_precision)+'</div>'
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
