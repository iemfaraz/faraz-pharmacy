/* Inventory -> "Extract from bill (Invoice AI)".
   Sends the chosen supplier bill to the pharmacy's own Invoice AI service (OCR) and loads the
   result into the existing editable receipt draft. Nothing is saved until the owner reviews every
   row and clicks Confirm & add stock. */
(()=>{'use strict';
const $=id=>document.getElementById(id),el=(t,x)=>{const e=document.createElement(t);if(x!==undefined)e.textContent=x;return e};
const base=()=>String(window.INVOICE_AI_URL||'').replace(/\/+$/,'');
const types=['image/jpeg','image/png','image/webp','application/pdf'];
let running=false;
function say(text){const s=$('inv-status');if(s)s.textContent=text}
function strength(name){return name.match(/\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|ml|iu|%)\b(?:\s*\/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))?/i)?.[0]||''}
function form(name){return name.match(/\b(tablets?|capsules?|syrup|suspension|injection|cream|ointment|drops?|gel)\b/i)?.[0]||''}
const num=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
function toRows(result){
  const lowConf=0.6;
  return (result.items||[]).map(item=>{
    const name=String(item.description||'').replace(/\s+/g,' ').trim().slice(0,120),w=[];
    const qty=num(item.quantity),unit=num(item.unit_price),line=num(item.line_total);
    let packs='',price='';
    if(qty!==null&&Number.isInteger(qty)&&qty>0)packs=qty;else w.push('Packs received were not read clearly. Enter the quantity from the bill.');
    if(unit!==null&&unit>=0)price=unit;
    else if(line!==null&&qty&&qty>0){price=Math.round(line/qty*100)/100;w.push('Purchase price per pack was calculated from the line total ÷ quantity. Check it against the bill.')}
    else w.push('Purchase price per pack was not read. Enter it from the bill.');
    if(typeof item.confidence==='number'&&item.confidence<lowConf)w.push('Low OCR confidence for this row. Check the name, quantity and price.');
    for(const f of item.flags||[])w.push(String(f));
    w.push('Batch, dates, manufacturer and selling price are usually not read from bills this way. Enter them from the packaging or bill.');
    return{name,strength:strength(name),form:form(name),receivedPacks:packs,purchasePrice:price,warnings:w}
  }).filter(r=>r.name)
}
async function run(button){
  if(running)return;
  const inventory=window.pharmacyInventory;
  try{
    const token=inventory?.session?.();
    if(!token)throw Error('Connect the pharmacy owner account first.');
    const url=base();
    if(!url)throw Error('The Invoice AI service is not set up yet. Deploy invoice-ai/ and set its address in invoice-ai-config.js.');
    const file=$('inv-bill')?.files[0];
    if(!file)throw Error('Choose a bill photo or PDF above first, then click Extract from bill (Invoice AI).');
    if(file.size>5*1024*1024||!types.includes(file.type))throw Error('Choose a JPEG, PNG, WebP photo or PDF up to 5 MB.');
    running=true;button.disabled=true;
    say('Sending the bill to your Invoice AI service. The first request can take a minute while it wakes up…');
    const body=new FormData();body.append('file',file,file.name);
    const r=await fetch(url+'/api/extract',{method:'POST',headers:{Authorization:'Bearer '+token},body,cache:'no-store',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(150000)});
    let data;try{data=await r.json()}catch{data={}}
    if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Invoice AI could not read this bill (error '+r.status+').');
    if(inventory.session()!==token)return; // owner session changed while reading
    const rows=toRows(data),warnings=(data.warnings||[]).map(String);
    if(data.currency&&!/^(PKR|RS\.?|₨)$/i.test(data.currency))warnings.push('The bill currency was detected as '+data.currency+'. Inventory prices must be in PKR.');
    if(typeof data.ocr_confidence==='number'&&data.ocr_confidence<0.8)warnings.push('Text recognition confidence is low ('+Math.round(data.ocr_confidence*100)+'%). Check every value against the bill.');
    const total=num(data.total);
    inventory.applyBill({rows,supplier:data.vendor||'',invoice:data.invoice_number||'',purchaseDate:data.date||'',warnings,text:data.text||'',
      summary:'Invoice AI read '+rows.length+' medicine rows'+(total!==null?' · bill total '+total.toLocaleString('en-PK',{minimumFractionDigits:2,maximumFractionDigits:2}):'')+'. Check every value against the original bill; no stock has been saved.'});
  }catch(e){say(e?.name==='TimeoutError'?'Invoice AI took too long. Try again in a moment.':(e.message||'Invoice AI failed. Try a clearer photo or use manual entry.'))}
  finally{running=false;button.disabled=false}
}
function install(){
  const ai=$('inv-ai-extract');if(!ai||$('inv-invoice-ai'))return;
  const button=el('button','Extract from bill (Invoice AI)');button.type='button';button.id='inv-invoice-ai';
  button.title='Reads the selected bill with your own Invoice AI service';
  button.onclick=()=>run(button);ai.after(button);
  const help=el('p','Invoice AI sends the selected bill to the pharmacy\'s own Invoice AI service for OCR; the bill is not stored there. You still review every row before stock is saved.');
  help.className='inv-help';ai.parentElement.after(help);
  const top=el('button','Extract from bill (Invoice AI)');top.type='button';top.id='inv-invoice-ai-top';
  top.onclick=()=>{$('inv-bill-reader')?.click()};
  $('inv-bill-reader')?.after(top);
}
install();
})();
