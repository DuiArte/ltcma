/* Dark-mode gate, REAL-BROWSER half (wave r2, 2026-11-10). Load it into any page of the served docs/ (same origin):
     var s=document.createElement('script');s.src='<url of this file>';document.head.appendChild(s);
   then window.ltcmaThemeCheck(cfg) -> a Promise of the report (also kept in window.__TG while it runs).
   cfg = {pages:[...], widths:[1440,375], themes:['light','dark'], wait:4300}
   For every page x width x theme it loads the page in a same-origin iframe of that width with the theme set the way a
   viewer sets it (localStorage 'ltcma-theme' read by the head boot script) and measures, on the live DOM:
     text   every visible text node's computed colour vs its effective background (ancestor backgrounds composited);
            >= 4.5:1, >= 3:1 for large text (24 px, or 18.66 px bold). Text inside an image hero is not measured here
            (its ground is a photograph: tools/hero_contrast.py measures the decoded pixels) but it must be identical
            in both themes (hero invariance).
     charts every Plotly chart: SVG text fills vs the chart's effective paper colour (>= 3:1; < 4.5 counted), every
            trace's stroke / marker / bar vs the effective plot colour (>= 3:1), hover label font vs its ground
            (>= 4.5:1), and that no colour of the other theme is left on the chart (palette map applied both ways).
   The control round trip (every press flips light / dark; the device's own look is Auto) and the no-JS fallback are
   not automated here: they are exercised by hand in a browser (DEPLOY_NOTES part B4 and round 1). */
(function(){
var W=window;
function pc(s){if(!s)return null;s=String(s).trim();if(s==='transparent')return [0,0,0,0];var m=/^rgba?\(([^)]*)\)$/.exec(s);
 if(m){var p=m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);return [p[0],p[1],p[2],p.length>3?p[3]:1];}
 if(s[0]==='#'){var h=s.slice(1);if(h.length===3||h.length===4)h=h.replace(/./g,'$&$&');if(h.length===6)h+='ff';
  return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16),parseInt(h.substr(6,2),16)/255];}
 if(s==='white')return [255,255,255,1];if(s==='black')return [0,0,0,1];return null;}
function over(t,b){var a=t[3];return [t[0]*a+b[0]*(1-a),t[1]*a+b[1]*(1-a),t[2]*a+b[2]*(1-a),1];}
function L(c){var f=function(v){v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4);};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]);}
function cr(a,b){var x=L(a),y=L(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);}
function hex(c){return '#'+[0,1,2].map(function(i){return ('0'+Math.round(c[i]).toString(16)).slice(-2);}).join('');}
function bgOf(el,win){var layers=[],e=el;while(e&&e.nodeType===1){var cs=win.getComputedStyle(e);
 if(cs.backgroundImage&&cs.backgroundImage!=='none'&&!/gradient/.test(cs.backgroundImage))return {img:true};
 var c=pc(cs.backgroundColor);if(c&&c[3]>0){layers.push(c);if(c[3]>=1)break;}e=e.parentElement;}
 var base=[255,255,255,1];if(!layers.length||layers[layers.length-1][3]<1){var cv=win.getComputedStyle(win.document.documentElement).colorScheme;
  if(/dark/.test(cv||''))base=[18,18,18,1];}
 for(var i=layers.length-1;i>=0;i--)base=over(layers[i],base);return {rgb:base};}
function path(el){var p=[],e=el;for(var i=0;i<4&&e&&e.nodeType===1;i++){p.unshift(e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(e.className&&typeof e.className==='string'?'.'+e.className.trim().split(/\s+/).slice(0,2).join('.'):''));e=e.parentElement;}return p.join('>');}
function textCheck(win,doc,res){var all=doc.body.querySelectorAll('*'),n=0;
 for(var i=0;i<all.length;i++){var el=all[i],tg=el.tagName;if(/^(SCRIPT|STYLE|NOSCRIPT|svg|SVG|TITLE|OPTION)$/.test(tg))continue;
  if(el.closest('svg'))continue;
  var own='';for(var k=0;k<el.childNodes.length;k++){var c=el.childNodes[k];if(c.nodeType===3)own+=c.nodeValue;}
  if(!/\S/.test(own))continue;var r=el.getClientRects();if(!r.length)continue;var cs=win.getComputedStyle(el);
  if(cs.visibility!=='visible')continue;var bb=el.getBoundingClientRect();if(bb.width<=1||bb.height<=1)continue;
  if(cs.clip&&cs.clip!=='auto'&&/rect\(0/.test(cs.clip))continue;
  var hero=el.closest('.hero--img');if(hero){continue;}
  var fg=pc(cs.color);if(!fg)continue;var op=1,e=el;while(e&&e.nodeType===1){if(!e.classList.contains('rv')){var o=parseFloat(win.getComputedStyle(e).opacity);if(o<1)op*=o;}e=e.parentElement;}
  var b=bgOf(el,win);if(b.img){res.textImg++;continue;}var f2=over([fg[0],fg[1],fg[2],fg[3]*op],b.rgb),q=cr(f2,b.rgb);
  var px=parseFloat(cs.fontSize),wt=parseInt(cs.fontWeight,10)||400,large=px>=24||(px>=18.66&&wt>=700),need=large?3:4.5;n++;
  if(op<0.6){res.textDim++;continue;}               /* deliberately dimmed (an empty filter chip): inactive, WCAG-exempt */
  if(q<need){res.textFail.push({el:path(el),t:own.trim().slice(0,40),fg:hex(f2),bg:hex(b.rgb),r:+q.toFixed(2),need:need});}
 }res.textN=n;}
function heroSig(win,doc){var o=[];[].forEach.call(doc.querySelectorAll('.hero--img, .hero--img *'),function(e){var cs=win.getComputedStyle(e);
 o.push(cs.color+'|'+cs.backgroundColor+'|'+cs.borderTopColor);});return o;}
function chartCheck(win,doc,res){var M=win.ltcmaTheme,dark=doc.documentElement.getAttribute('data-theme')==='dark';
 [].forEach.call(doc.querySelectorAll('.js-plotly-plot'),function(g){var F=g._fullLayout;if(!F)return;res.charts++;
  var rect=g.getBoundingClientRect();if(!rect.width)return;
  var under=bgOf(g,win);under=under.img?[255,255,255,1]:under.rgb;var paper=over(pc(F.paper_bgcolor)||[255,255,255,1],under),plot=over(pc(F.plot_bgcolor)||[0,0,0,0],paper);
  [].forEach.call(g.querySelectorAll('svg text'),function(t){if(!/\S/.test(t.textContent))return;var cs=win.getComputedStyle(t);
   if(cs.display==='none'||cs.visibility==='hidden'||parseFloat(cs.opacity)===0)return;if(t.closest('.legend')&&false)return;
   var bb=t.getBoundingClientRect();if(!bb.width)return;var f=pc(cs.fill);if(!f)return;var fo=parseFloat(cs.fillOpacity);if(!isNaN(fo))f[3]*=fo;
   var ff=over(f,paper),q=cr(ff,paper);res.svgText++;if(q<4.5)res.svgText45++;
   if(q<3)res.svgFail.push({c:g.id,t:t.textContent.slice(0,30),fg:hex(ff),bg:hex(paper),r:+q.toFixed(2)});});
  function mark(sel,attr,kind){[].forEach.call(g.querySelectorAll(sel),function(p){if(p.closest('.legend'))return;var cs=win.getComputedStyle(p);
   if(cs.display==='none'||cs.visibility==='hidden')return;var c=pc(attr==='stroke'?cs.stroke:cs.fill);if(!c||c[3]===0)return;
   if(attr==='stroke'&&parseFloat(cs.strokeWidth)===0)return;var a=parseFloat(attr==='stroke'?cs.strokeOpacity:cs.fillOpacity);if(!isNaN(a))c[3]*=a;
   var e=p;while(e&&e!==g){var o=parseFloat(win.getComputedStyle(e).opacity);if(o<1)c[3]*=o;e=e.parentElement;}
   if(c[3]<0.05)return;var cc=over(c,plot),q=cr(cc,plot);res.marks++;
   if(q<3)res.markFail.push({c:g.id,k:kind,fg:hex(cc),a:+c[3].toFixed(2),bg:hex(plot),r:+q.toFixed(2)});});}
  mark('.scatterlayer .trace path.js-line','stroke','line');mark('.scatterlayer .trace .points path','fill','marker');
  mark('.barlayer .trace .point path','fill','bar');mark('.pielayer .slice path','fill','slice');
  (g._fullData||[]).forEach(function(fd){if(fd.visible===false||!fd.hoverlabel)return;var hb=fd.hoverlabel.bgcolor||(F.hoverlabel||{}).bgcolor,
   hf=(fd.hoverlabel.font||{}).color||((F.hoverlabel||{}).font||{}).color;if(typeof hb!=='string'||typeof hf!=='string')return;
   var b2=over(pc(hb),paper),q=cr(over(pc(hf),b2),b2);res.hover++;if(q<4.5)res.hoverFail.push({c:g.id,bg:hb,fg:hf,r:+q.toFixed(2)});});
  /* a colour the palette map would still change in this theme is a colour of the OTHER theme left on the chart */
  if(M&&M.map){var bad=[];function chk(v,w){if(typeof v==='string'){if(M.map(v,dark)!==v)bad.push(w+'='+v);}
    else if(Array.isArray(v))v.forEach(function(x){chk(x,w);});}
   ['paper_bgcolor','plot_bgcolor'].forEach(function(k){chk(F[k],k);});chk((F.font||{}).color,'font');
   g.data.forEach(function(t,i){chk((t.line||{}).color,'line'+i);chk((t.marker||{}).color,'marker'+i);chk(t.fillcolor,'fill'+i);});
   if(bad.length)res.wrongTheme.push({c:g.id,bad:bad.slice(0,6)});}
 });}
function load(page,width,theme,wait){return new Promise(function(done){
 try{localStorage.setItem('ltcma-theme',theme);}catch(e){}
 var f=document.createElement('iframe');f.style.cssText='position:absolute;left:-30000px;top:0;border:0;height:900px;width:'+width+'px';
 var to=setTimeout(function(){fin({err:'timeout'});},wait+20000);
 function fin(extra){clearTimeout(to);var res={page:page,width:width,theme:theme,textFail:[],textN:0,textImg:0,textDim:0,charts:0,svgText:0,svgText45:0,
   svgFail:[],marks:0,markFail:[],hover:0,hoverFail:[],wrongTheme:[],err:null};
  try{var win=f.contentWindow,doc=f.contentDocument;if(extra&&extra.err)res.err=extra.err;
   res.dataTheme=doc.documentElement.getAttribute('data-theme');res.pref=doc.documentElement.getAttribute('data-theme-pref');
   res.thm=!!doc.getElementById('thm')&&win.getComputedStyle(doc.getElementById('thm')).display!=='none';
   res.bodyBg=win.getComputedStyle(doc.body).backgroundColor;
   res.overflowX=doc.documentElement.scrollWidth>width+1;
   textCheck(win,doc,res);chartCheck(win,doc,res);res.hero=heroSig(win,doc);res.errors=(win.__errs||[]).slice(0,5);
  }catch(e){res.err=String(e);}
  f.remove();done(res);}
 f.onload=function(){try{var w=f.contentWindow;w.__errs=w.__errs||[];}catch(e){}setTimeout(fin,wait);};
 f.src=page+(page.indexOf('?')<0?'?':'&')+'tg='+Date.now();document.body.appendChild(f);});}
W.ltcmaThemeCheck=function(cfg){cfg=cfg||{};var pages=cfg.pages,widths=cfg.widths||[1440,375],themes=cfg.themes||['light','dark'],wait=cfg.wait||4300;
 var jobs=[];pages.forEach(function(p){widths.forEach(function(w){themes.forEach(function(t){jobs.push([p,w,t]);});});});
 W.__TG={status:'running',done:0,total:jobs.length,results:[]};
 return jobs.reduce(function(pr,j){return pr.then(function(){return load(j[0],j[1],j[2],wait).then(function(r){W.__TG.results.push(r);W.__TG.done++;});});},Promise.resolve())
 .then(function(){try{localStorage.removeItem('ltcma-theme');}catch(e){}W.__TG.status='done';return W.__TG;});};
W.ltcmaThemeSummary=function(){var T=W.__TG,out={status:T.status,done:T.done,total:T.total,rows:[],heroDiff:[]},hs={};
 T.results.forEach(function(r){out.rows.push([r.page,r.width,r.theme,r.dataTheme,r.thm?'ctl':'NOCTL',r.textN,r.textFail.length,r.charts,r.svgText,r.svgFail.length,
  r.svgText45,r.marks,r.markFail.length,r.hoverFail.length,r.wrongTheme.length,r.overflowX?'OVERFLOW':'',r.err||'']);
  var k=r.page+'@'+r.width;if(!hs[k])hs[k]={};hs[k][r.theme]=JSON.stringify(r.hero);});
 Object.keys(hs).forEach(function(k){if(hs[k].light!==undefined&&hs[k].dark!==undefined&&hs[k].light!==hs[k].dark)out.heroDiff.push(k);});return out;};
W.ltcmaThemeFails=function(theme,kind,max){var o=[];(W.__TG.results||[]).forEach(function(r){if(theme&&r.theme!==theme)return;
 (r[kind]||[]).forEach(function(x){o.push([r.page,r.width].concat(Object.keys(x).map(function(k){return x[k];})));});});return o.slice(0,max||80);};
})();
