/* Layout gate, REAL-BROWSER half (wave r3 fix round 1, 2026-11-11; review RG-1). The static half is ds_gate R12
   (_css_fix_checks: the rules below are in the emitted style.css). Load it into any page of the served docs/ (same
   origin), exactly like tools/theme_browser_check.js:
     var s=document.createElement('script');s.src='<url of this file>';document.head.appendChild(s);
   then window.ltcmaLayoutCheck(cfg) -> a Promise of the report (also kept in window.__LG while it runs).
   cfg = {pages:[...], widths:[1440,375], wait:2500}
   For every page x width it loads the page in a same-origin iframe of that width and measures, on the live DOM:
     sticky  every table.ptable with a head: at rest the head sits on its table's top and never covers row 1; scrolled
             half-way through the table, the head is either stuck right below the sticky cover (the site header + the
             On-this-page bar) or -- only inside a deliberate sideways scroller (overflow-x auto / scroll), where a head
             cannot stick to the viewport -- has left with its table; never visible UNDER the cover, never held inside
             an overflow:hidden tile (r3 bug a: such a tile made heads stick inside it, never under the header)
     clip    every headline figure (.metric .mv, .kv, .kpi b, .mtile .v, .hero-stat .v, .xbig, .hp-big, .hp-row b) and
             every numeric table cell: no scrollWidth > clientWidth, no text past its card, nothing past the viewport
             (r3 bug b: the 5-tile money row clipped at 375 px)
     print   no rule inside an @media print block (CSSOM of the page's sheets) hides the footer (.shell-foot: the
             disclaimer and the image credit) or anything inside it (r3 bug c)
   Run it at 1440 and 375 (an iframe of that width; for real phone emulation use the CDP probes in DEPLOY_NOTES).
   report.fails = the number of failures; report.pages[i] = {page, width, sticky:{n, fail}, clip:{n, fail}, print:{fail}}. */
(function(){
var W=window;
function sleep(ms){return new Promise(function(r){setTimeout(r,ms);});}
function cover(doc){var c=0,h=doc.querySelector('header.shell');if(h)c=h.getBoundingClientRect().bottom;
 var b=doc.querySelector('nav.otp');if(b&&doc.defaultView.getComputedStyle(b).position==='sticky'){var r=b.getBoundingClientRect();if(r.top<c+2)c=Math.max(c,r.bottom);}
 return c;}
async function sticky(win,doc,res){var T=[].slice.call(doc.querySelectorAll('table.ptable'));
 for(var i=0;i<T.length;i++){var t=T[i],th=t.querySelector('thead th'),tr=t.querySelector('tbody tr');
  if(!th||!tr||t.offsetParent===null)continue;
  if(win.getComputedStyle(t.tHead).display==='none'||th.getBoundingClientRect().height===0)continue;   /* phone cards: no head */
  var id=t.id||((t.closest('[id]')||{}).id)||('#'+i);
  var abs=t.getBoundingClientRect().top+win.scrollY;win.scrollTo(0,Math.max(0,abs-300));await sleep(120);
  var r1=t.getBoundingClientRect(),h1=th.getBoundingClientRect(),f1=tr.getBoundingClientRect();res.n++;
  if(!(Math.abs(h1.top-r1.top)<=1.5&&f1.top>=h1.bottom-1.5)){res.fail.push({t:id,why:'at rest the head is not on its table (covers row 1)',th:+h1.top.toFixed(1),table:+r1.top.toFixed(1)});continue;}
  var room=r1.height-h1.height-f1.height;if(room<120)continue;
  win.scrollTo(0,abs-cover(doc)+Math.min(260,room/2));await sleep(160);
  var c=cover(doc),h2=th.getBoundingClientRect(),r2=t.getBoundingClientRect();
  var stuck=Math.abs(h2.top-(c-1))<=2,away=h2.bottom<=c+1&&Math.abs(h2.top-r2.top)<=1.5,side=sideways(th,win,doc);
  /* a head may leave with its table only inside a deliberate sideways scroller (overflow-x auto / scroll); anywhere
     else it must stick below the cover (r3 bug a: a .tile with overflow:hidden held every head inside the tile) */
  if(!stuck&&!(away&&side))res.fail.push({t:id,why:h2.top<c-2&&!away?'the head is stuck under the header / bar':away?'the head does not stick (no sideways scroller holds it: an overflow:hidden ancestor?)':'the head is neither stuck below the cover nor with its table',th:+h2.top.toFixed(1),cover:+c.toFixed(1),table:+r2.top.toFixed(1)});
 }win.scrollTo(0,0);}
function sideways(th,win,doc){for(var e=th.parentElement;e&&e!==doc.body;e=e.parentElement){var x=win.getComputedStyle(e).overflowX;
 if(x==='auto'||x==='scroll')return true;}return false;}
function inScroller(el,win,doc){for(var e=el.parentElement;e&&e!==doc.body;e=e.parentElement){var x=win.getComputedStyle(e).overflowX;
 if((x==='auto'||x==='scroll')&&e.scrollWidth>e.clientWidth+1)return true;}return false;}   /* reached by scrolling sideways */
var NUM=/^[\s−+\-$€≈~<>]*[\d][\d.,]*\s*(%|bp|pp|x|×|K|M|B|σ)?\s*$/;
function clip(win,doc,res){var sel='.metric .mv, .kv, .kpi b, .mtile .v, .hero-stat .v, .xbig, .hp-big, .hp-row b';
 var els=[].slice.call(doc.querySelectorAll(sel));
 [].forEach.call(doc.querySelectorAll('table td'),function(td){if(NUM.test(td.textContent))els.push(td);});
 els.forEach(function(el){if(el.offsetParent===null)return;var cs=win.getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden')return;
  res.n++;var box=el.closest('.metric,.kpi,.mtile,.hero-stat,.xcard,.hero-panel')||el;var br=box.getBoundingClientRect(),bs=win.getComputedStyle(box);
  var inner=br.right-parseFloat(bs.paddingRight)-parseFloat(bs.borderRightWidth);var rg=doc.createRange();rg.selectNodeContents(el);var tr=rg.getBoundingClientRect();
  var off=br.right>win.innerWidth+0.5&&!inScroller(el,win,doc);
  var bad=el.scrollWidth>el.clientWidth+1?'clipped (scrollWidth > clientWidth)':(box!==el&&tr.right>inner+1.5)?'text past its card':off?'past the viewport':'';
  if(bad)res.fail.push({t:el.textContent.trim().slice(0,30),why:bad});});}
function printRules(doc,res){var foot=doc.querySelector('.shell-foot');if(!foot){res.fail.push({why:'no footer (.shell-foot) on the page'});return;}
 var targets=[foot].concat([].slice.call(foot.querySelectorAll('*')));
 function walk(rules,inPrint){[].forEach.call(rules,function(r){
  if(r.type===4){var m=r.media&&r.media.mediaText||'';walk(r.cssRules,inPrint||/\bprint\b/.test(m)&&!/\bnot\s+print\b/.test(m));return;}
  if(r.cssRules&&r.type!==1){walk(r.cssRules,inPrint);return;}
  if(r.type!==1||!inPrint)return;if(r.style.getPropertyValue('display').trim()!=='none')return;
  var hit=targets.filter(function(t){try{return t.matches(r.selectorText);}catch(e){return false;}});
  if(hit.length)res.fail.push({why:'a print rule hides the footer',rule:r.cssText.slice(0,120)});});}
 [].forEach.call(doc.styleSheets,function(s){try{walk(s.cssRules,false);}catch(e){}});}
function load(url,width,wait){return new Promise(function(ok){var f=document.createElement('iframe');
 f.style.cssText='position:fixed;left:0;top:0;border:0;opacity:0;pointer-events:none;width:'+width+'px;height:900px';
 f.onload=function(){setTimeout(function(){ok(f);},wait);};f.src=url;document.body.appendChild(f);});}
W.ltcmaLayoutCheck=async function(cfg){cfg=cfg||{};var pages=cfg.pages||['index.html'],widths=cfg.widths||[1440,375],wait=cfg.wait||2500;
 var rep={pages:[],fails:0};W.__LG=rep;var base=location.href.replace(/[^\/]*([?#].*)?$/,'');
 for(var i=0;i<pages.length;i++){for(var j=0;j<widths.length;j++){var f=await load(base+pages[i],widths[j],wait);
  var win=f.contentWindow,doc=f.contentDocument;doc.documentElement.style.scrollBehavior='auto';
  [].forEach.call(doc.querySelectorAll('.rv'),function(e){e.classList.add('vis');});
  var r={page:pages[i],width:widths[j],sticky:{n:0,fail:[]},clip:{n:0,fail:[]},print:{fail:[]}};
  try{await sticky(win,doc,r.sticky);clip(win,doc,r.clip);printRules(doc,r.print);}catch(e){r.error=String(e);rep.fails++;}
  rep.fails+=r.sticky.fail.length+r.clip.fail.length+r.print.fail.length;rep.pages.push(r);f.remove();}}
 return rep;};
})();
