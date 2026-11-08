(()=>{
const inApp=new URLSearchParams(location.search).get('app')==='android'||/FarazPharmacyAndroid\//.test(navigator.userAgent);
if(!inApp)return;
document.documentElement.classList.add('pharmacy-android-client');
const style=document.createElement('style');style.id='pharmacy-android-chrome';
style.textContent='html.pharmacy-android-client body.faraz-app-order #order>.order-layout{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:0!important}html.pharmacy-android-client body.faraz-app-order #order>.order-layout>div:first-child:not(.order-panel){display:none!important}html.pharmacy-android-client body.faraz-app-order #order .order-panel{display:block!important;min-width:0;width:100%;box-sizing:border-box}html.pharmacy-android-client body>header,html.pharmacy-android-client .utility,html.pharmacy-android-client .mobile-dock,html.pharmacy-android-client .app-promo,html.pharmacy-android-client #android-app,html.pharmacy-android-client a[href*="android-app.html"],html.pharmacy-android-client a[href$=".apk"],html.pharmacy-android-client body>footer{display:none!important}html.pharmacy-android-client{scroll-padding-top:16px}html.pharmacy-android-client body.pharmacy-tracking main{padding:18px;max-width:100%}html.pharmacy-android-client body.pharmacy-tracking main>h1,html.pharmacy-android-client body.pharmacy-tracking main>small,html.pharmacy-android-client body.pharmacy-tracking main>p:not(#status){display:none!important}html.pharmacy-android-client body.pharmacy-tracking #track-form{margin:0 0 18px;border-radius:16px;padding:20px;box-shadow:none}html.pharmacy-android-client body.pharmacy-tracking #result{margin:18px 0;border-radius:16px;padding:20px}';
document.head.append(style);
})();

// Keep customer app styling separate from the public storefront.
(()=>{
 if(!document.documentElement.classList.contains('pharmacy-android-client'))return;
 const link=document.createElement('link');link.rel='stylesheet';link.href=new URL('android-client.css?v=4',document.currentScript.src).href;document.head.append(link);
})();
