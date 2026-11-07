(()=>{
'use strict';
if(window.parent===window&&document.documentElement.classList.contains('pharmacy-android-client')){if(location.hash==='#order'){const request=new URL('request.html',location.href);request.search=location.search;location.replace(request.href)}return;}
const embedded=window.parent!==window&&new URLSearchParams(location.search).get('layout')==='embedded';
const views=['home','shop','request','track','contact','app'],shopViews=['shop','cart','account','orders'];
const pageFor={shop:'shop.html',request:'request.html',track:'track.html',app:'android-app.html?v=1.6.0'};
function routeFor(href){let u;try{u=new URL(href,location.href)}catch{return null}if(u.origin!==location.origin)return null;const file=u.pathname.split('/').pop();if(file==='android-app.html')return{view:'app',url:u};if(file==='shop.html')return{view:'shop',url:u};if(file==='request.html')return{view:'request',url:u};if(file==='track.html')return{view:'track',url:u};if(!file||file==='index.html')return{view:u.hash==='#contact'||u.hash==='#visit'?'contact':'home',url:u};return null}
if(embedded){
 document.documentElement.classList.add('customer-tab-embedded');
 const main=document.querySelector('main');if(!main)return;
 let scheduled=false,previous=0,shopReady=false,desiredShopView=null;
 const send=(type,data={})=>parent.postMessage({source:'faraz-customer-tab',type,...data},location.origin);
 function measure(){scheduled=false;const box=main.getBoundingClientRect(),height=Math.max(320,Math.ceil(box.bottom+scrollY+24));if(height!==previous){previous=height;send('resize',{height})}}
 function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(measure)}}
 new ResizeObserver(schedule).observe(main);
 new MutationObserver(schedule).observe(main,{subtree:true,childList:true,attributes:true,characterData:true});
 addEventListener('resize',schedule);document.addEventListener('load',schedule,true);document.fonts?.ready.then(schedule);
 if(document.body.classList.contains('customer-shop')){
   const search=document.getElementById('search-form');if(search)main.insertBefore(search,main.firstChild);
   addEventListener('faraz-shop-ready',()=>{shopReady=true;if(desiredShopView){document.querySelector('[data-view="'+desiredShopView+'"]')?.click();desiredShopView=null}schedule()});
   addEventListener('faraz-shop-view',e=>{send('shop-view',{view:e.detail});schedule()});
 }
 addEventListener('message',e=>{if(e.source!==parent||e.origin!==location.origin||e.data?.source!=='faraz-customer-shell')return;
   if(e.data.type==='language')document.dispatchEvent(new Event('faraz-language'));
   if(e.data.type==='shop-view'&&shopViews.includes(e.data.view)){desiredShopView=e.data.view;if(shopReady){document.querySelector('[data-view="'+desiredShopView+'"]')?.click();desiredShopView=null}}
 });
 document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a||e.defaultPrevented||e.ctrlKey||e.metaKey||e.shiftKey||a.target==='_blank'||a.hasAttribute('download'))return;const target=routeFor(a.href);if(!target)return;e.preventDefault();send('navigate',{href:a.href})});
 schedule();send('ready');return;
}
if(!document.body.classList.contains('pharmacy-home'))return;
document.documentElement.classList.add('customer-tabs-active');
const main=document.querySelector('main'),nav=document.getElementById('main-nav'),header=document.querySelector('.clean-header'),frames=new Map();
let active='home';
const panel=document.createElement('section');panel.id='customer-tab-panel';panel.hidden=true;panel.setAttribute('aria-label','Pharmacy page content');
const loading=document.createElement('p');loading.className='customer-tab-loading';loading.setAttribute('role','status');
const fallback=document.createElement('a');fallback.className='customer-tab-fallback';fallback.textContent='Open this page directly';fallback.hidden=true;
panel.append(loading,fallback);main.append(panel);
function offset(){document.documentElement.style.setProperty('--customer-header-height',Math.ceil(header.getBoundingClientRect().height)+'px')}new ResizeObserver(offset).observe(header);offset();
function canonical(view,url){let hash='#'+view;if(view==='shop'){const p=new URLSearchParams();for(const key of ['view','search','category'])if(url.searchParams.has(key))p.set(key,url.searchParams.get(key).slice(0,150));if(p.size)hash+='?'+p.toString()}return hash}
function setURL(view,url,push){const hash=canonical(view,url);if(location.hash!==hash)history[push?'pushState':'replaceState']({pharmacyView:view},'',location.pathname+location.search+hash)}
function language(){for(const item of frames.values())item.frame.contentWindow?.postMessage({source:'faraz-customer-shell',type:'language'},location.origin)}
new MutationObserver(language).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
function mark(view){for(const a of nav.querySelectorAll('a')){if(routeFor(a.href)?.view===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')}for(const item of frames.values())item.frame.hidden=item.view!==view}
function open(view,url=new URL(pageFor[view]||'./',location.href),push=true,scroll=true){
 if(!views.includes(view))view='home';active=view;document.body.dataset.customerView=view;mark(view);panel.hidden=!pageFor[view];document.title=({home:'Faraz Pharmacy | Barikot, Swat',shop:'Shop | Faraz Pharmacy',request:'Request a medicine | Faraz Pharmacy',track:'Track order | Faraz Pharmacy',contact:'Contact | Faraz Pharmacy',app:'App download | Faraz Pharmacy'})[view];setURL(view,url,push);
 if(pageFor[view]){
  let item=frames.get(view);const clean=new URL(pageFor[view],location.href);for(const [key,value]of url.searchParams)if(['view','search','category','add'].includes(key))clean.searchParams.set(key,value);clean.searchParams.set('layout','embedded');clean.hash=url.hash;
  const navigationIntent=view==='shop'&&['search','category','add'].some(k=>url.searchParams.has(k))||view==='track'&&!!url.hash;
  if(!item){const frame=document.createElement('iframe');frame.className='customer-tab-frame';frame.title=({shop:'Shop, cart and customer account',request:'Request a medicine',track:'Track your pharmacy request',app:'Download the Faraz Pharmacy Android app'})[view];frame.setAttribute('allow','geolocation '+location.origin);frame.setAttribute('scrolling','no');frame.referrerPolicy='same-origin';item={frame,view,loaded:false,src:''};frames.set(view,item);panel.append(frame);frame.addEventListener('load',()=>{item.loaded=true;if(active===view){loading.hidden=true;fallback.hidden=true}language()});}
  item.frame.hidden=false;
  if(!item.src||navigationIntent&&item.src!==clean.href){item.loaded=false;item.src=clean.href;item.frame.src=clean.href;}
  else if(view==='shop'){item.frame.contentWindow?.postMessage({source:'faraz-customer-shell',type:'shop-view',view:url.searchParams.get('view')||'shop'},location.origin)}
  loading.textContent='Loading '+({shop:'shop',request:'medicine request',track:'order tracking',app:'app downloads'})[view]+'…';loading.hidden=item.loaded;fallback.href=url.href;fallback.hidden=item.loaded;
 }
 if(scroll){window.scrollTo({top:0,behavior:'instant'});main.setAttribute('tabindex','-1');main.focus({preventScroll:true})}
}
document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(!a||e.defaultPrevented||e.button!==0||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||a.target==='_blank'||a.hasAttribute('download')||a===fallback)return;const route=routeFor(a.href);if(!route)return;e.preventDefault();open(route.view,route.url)});
document.querySelector('.clean-search').addEventListener('submit',e=>{e.preventDefault();const u=new URL('shop.html',location.href),query=document.getElementById('home-search').value.trim();if(query)u.searchParams.set('search',query);open('shop',u)});
addEventListener('message',e=>{if(e.origin!==location.origin||e.data?.source!=='faraz-customer-tab')return;const item=[...frames.values()].find(f=>f.frame.contentWindow===e.source);if(!item)return;
 if(e.data.type==='resize'&&Number.isFinite(e.data.height)&&e.data.height>=320&&e.data.height<=200000)item.frame.style.height=Math.ceil(e.data.height)+'px';
 if(e.data.type==='navigate'){const route=routeFor(e.data.href);if(route)open(route.view,route.url)}
 if(e.data.type==='shop-view'&&active==='shop'&&shopViews.includes(e.data.view)){const u=new URL('shop.html',location.href);u.searchParams.set('view',e.data.view);setURL('shop',u,false)}
});
function fromLocation(scroll=false){const raw=location.hash.slice(1),[name,query='']=raw.split('?');if(name==='order'){open('request',new URL('request.html',location.href),false,scroll);return}const view=views.includes(name)?name:'home',url=new URL(pageFor[view]||'./',location.href);if(view==='shop')url.search=query;open(view,url,false,scroll)}
addEventListener('popstate',()=>fromLocation(true));addEventListener('hashchange',()=>fromLocation(true));
fromLocation();
})();