import {equipment,bookings,downtimes,batches} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,notify,date} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {BookingStatus,EquipmentKind} from '../constants/enums.js';

const DAY=86400,localInput=ts=>{const d=new Date(ts*1000);d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,16);};
const canWrite=()=>session.user.role!=='viewer';

function gantt(timelines,from,to){
 const W=1240,left=150,right=18,pw=W-left-right,rowH=40,top=26,H=top+timelines.length*rowH+30;
 const x=t=>left+Math.min(Math.max((t-from)/(to-from),0),1)*pw;
 let svg='';
 for(let d=0;d<=7;d++){const gx=left+d/7*pw,label=new Date((from+d*DAY)*1000);svg+='<line x1="'+gx+'" y1="'+top+'" x2="'+gx+'" y2="'+(H-28)+'" class="grid"/><text x="'+(gx+4)+'" y="'+(top-8)+'">'+esc(String(label.getMonth()+1).padStart(2,'0')+'-'+String(label.getDate()).padStart(2,'0'))+'</text>';}
 timelines.forEach((t,i)=>{
  const y=top+i*rowH+8,bh=rowH-18;
  svg+='<text x="'+(left-12)+'" y="'+(y+bh/2+4)+'" text-anchor="end" class="lane">'+esc(t.equipment.code)+'</text><line x1="'+left+'" y1="'+(y+bh+4)+'" x2="'+(left+pw)+'" y2="'+(y+bh+4)+'" class="grid"/>';
  t.bookings.forEach(b=>{const cls=b.status==='in_progress'?'g-run':'g-book';svg+='<rect class="'+cls+'" x="'+x(b.start_at)+'" y="'+y+'" width="'+Math.max(2,x(b.end_at)-x(b.start_at))+'" height="'+bh+'"><title>'+esc(b.code+' '+b.title+' · '+BookingStatus[b.status]+'\n'+date(b.start_at)+' – '+date(b.end_at)+'（含清洗与稳定）')+'</title></rect>';});
  t.downtimes.forEach(d=>{svg+='<rect class="g-down" x="'+x(d.start_at)+'" y="'+y+'" width="'+Math.max(2,x(d.end_at)-x(d.start_at))+'" height="'+bh+'"><title>'+esc('停用 · '+d.reason+'\n'+date(d.start_at)+' – '+date(d.end_at))+'</title></rect>';});
 });
 return '<div class="legend"><span class="key">预约占用（含清洗与稳定）</span><span class="key k2">进行中</span><span class="key k3">设备停用</span></div><svg class="chart gantt" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="设备时间轴">'+svg+'</svg>';
}

function bookingItem(b,eq,batchNo){
 const actions=b.status==='booked'?'<button class="small" data-act="start" data-id="'+b.id+'">开工</button>'
  :b.status==='in_progress'?'<button class="small primary" data-act="seal" data-id="'+b.id+'">封卷建批</button>'
  :b.status==='pending_reschedule'?'<button class="small" data-act="reschedule" data-id="'+b.id+'">重排</button>'
  :'<span class="batch-tag">'+esc(batchNo||'已封卷')+'</span>';
 return '<article class="booking-item"><div><strong>'+esc(b.code)+' · '+esc(b.title)+'</strong><span class="status st-'+b.status+'">'+esc(BookingStatus[b.status])+'</span>'
  +'<p>'+esc(eq[b.bath_id]?.code||b.bath_id)+' + '+esc(eq[b.standard_id]?.code||b.standard_id)+' · 测量 '+esc(date(b.start_at))+' – '+esc(date(b.end_at))+'<br>占用 '+esc(date(b.occ_start))+' – '+esc(date(b.occ_end))+'（清洗 '+b.clean_minutes+' 分 + 稳定 '+b.stabilize_minutes+' 分）</p>'
  +(b.reschedule_reason?'<p class="conflict">'+esc(b.reschedule_reason)+'</p>':'')
  +'</div><div class="booking-actions">'+(canWrite()?actions:(b.status==='sealed'?'<span class="batch-tag">'+esc(batchNo||'已封卷')+'</span>':''))+'</div></article>';
}

export async function bookingPage(){
 const [eq,bs,ds,bt]=await Promise.all([equipment.list(),bookings.list(),downtimes.list(),batches.list()]);
 workspace.equipment=eq;workspace.bookings=bs;
 const eqMap=Object.fromEntries(eq.map(e=>[e.id,e])),batchMap=Object.fromEntries(bt.map(x=>[x.booking_id,x.batch_no]));
 const from=Math.floor(Date.now()/1000/DAY)*DAY-DAY,to=from+8*DAY;
 const timelines=await Promise.all(eq.map(e=>equipment.timeline(e.id,from,to)));
 const baths=eq.filter(e=>e.kind==='bath'),stds=eq.filter(e=>e.kind==='standard'),inProgress=bs.filter(b=>b.status==='in_progress');
 const key=crypto.randomUUID(),key2=crypto.randomUUID();
 const eqOptions=eq.map(e=>'<option value="'+e.id+'">'+esc(e.code)+' · '+esc(EquipmentKind[e.kind])+'</option>').join('');
 return heading('03 / SCHEDULING','校准预约与设备调度','每单成组占用一台恒温槽与一台标准仪，清洗与稳定时间计入占用；设备停用撞上预约时整组改期，无共同空档则待重排。')
 +'<div class="booking-grid"><section class="panel"><div class="section-title"><h2>新建预约</h2><span>成组占用 · 冲突拒单</span></div><form id="booking-form"><input type="hidden" name="request_key" value="'+key+'"><label>预约名称<input name="title" required minlength="2" value="探头批次 · 校准"></label><div class="parameter-grid"><label>恒温槽<select name="bath_id">'+baths.map(e=>'<option value="'+e.id+'">'+esc(e.code)+' · '+esc(e.name.split('·')[1]||e.name)+'</option>').join('')+'</select></label><label>标准仪<select name="standard_id">'+stds.map(e=>'<option value="'+e.id+'">'+esc(e.code)+' · '+esc(e.name.split('·')[1]||e.name)+'</option>').join('')+'</select></label></div><div class="parameter-grid"><label>测量开始<input type="datetime-local" name="start" required value="'+localInput(from+2*DAY+9*3600)+'"></label><label>测量结束<input type="datetime-local" name="end" required value="'+localInput(from+2*DAY+12*3600)+'"></label></div><div class="parameter-grid"><label>清洗时间（分钟）<input type="number" name="clean_minutes" min="0" max="240" value="30" required></label><label>稳定时间（分钟）<input type="number" name="stabilize_minutes" min="0" max="240" value="20" required></label></div><button type="submit" class="primary" '+(canWrite()?'':'disabled')+'>校验空档并预约 ↗</button><p class="hint">提交即占用两类设备的整段区间（含清洗与稳定）。与既有预约或停用冲突时拒单并说明原因；重复提交同一表单不会重复占档。</p></form>'
 +'<div class="section-title"><h2>设备停用</h2><span>撞上预约自动整组改期</span></div><form id="downtime-form"><input type="hidden" name="request_key" value="'+key2+'"><label>设备<select name="equipment_id">'+eqOptions+'</select></label><div class="parameter-grid"><label>停用开始<input type="datetime-local" name="start" required value="'+localInput(from+3*DAY)+'"></label><label>停用结束<input type="datetime-local" name="end" required value="'+localInput(from+3*DAY+4*3600)+'"></label></div><label>停用原因<input name="reason" required minlength="2" placeholder="例如：季度溯源 / 故障检修"></label><button type="submit" class="primary" '+(canWrite()?'':'disabled')+'>登记停用 ↗</button><p class="hint">已开工的预约留到结束；未开工的整组改期，14 天内无共同空档则转为待重排。</p></form>'
 +'<div class="section-title"><h2>读数接报</h2><span>绑定预约 · 封卷后拒收</span></div><form id="reading-form"><label>进行中预约<select name="booking_id" '+(inProgress.length?'':'disabled')+'>'+inProgress.map(b=>'<option value="'+b.id+'" data-bath="'+b.bath_id+'" data-std="'+b.standard_id+'">'+esc(b.code)+' · '+esc(b.title)+'</option>').join('')+'</select></label><label>读数 JSON<textarea name="records" rows="5" placeholder=\'[{"sample":"T24-高温-001","band":"高温","reference":70.01,"measured":70.62}]\' required></textarea></label><button type="submit" class="primary" '+(canWrite()&&inProgress.length?'':'disabled')+'>上报读数 ↗</button><p class="hint">仅接收已开工且设备相符的预约读数；封卷后晚到读数不改旧卷。</p></form></section>'
 +'<section class="panel"><div class="section-title"><h2>预约单</h2><span>'+bs.length+' 单</span></div><div class="booking-list">'+(bs.length?bs.map(b=>bookingItem(b,eqMap,batchMap[b.id])).join(''):'<div class="empty">暂无预约。左侧提交第一单。</div>')+'</div>'
 +'<div class="section-title"><h2>分析批次</h2><span>封卷生成 · 唯一建批</span></div>'+(bt.length?bt.map(x=>'<div class="delivery"><div><strong>'+esc(x.batch_no)+'</strong><p>预约 #'+x.booking_id+' · '+x.rows+' 条读数 · 数据批次 #'+x.dataset_id+'</p><small>SHA256 '+esc(x.checksum.slice(0,18))+'… · '+esc(date(x.created_at))+'</small></div></div>').join(''):'<div class="empty">封卷后在此生成唯一分析批次。</div>')
 +'<div class="section-title"><h2>停用记录</h2><span>'+ds.length+' 段</span></div>'+(ds.length?ds.map(d=>'<div class="delivery"><div><strong>'+esc(eqMap[d.equipment_id]?.code||d.equipment_id)+' · '+esc(d.reason)+'</strong><p>'+esc(date(d.start_at))+' – '+esc(date(d.end_at))+'</p></div></div>').join(''):'<div class="empty">暂无停用。</div>')+'</section></div>'
 +'<section class="panel"><div class="section-title"><h2>设备时间轴</h2><span>昨日 – 未来 7 天 · 悬停查看明细</span></div>'+gantt(timelines,from,to)+'</section>';
}

export function bindBookings(refresh){
 const ts=v=>Math.round(new Date(v).getTime()/1000);
 submit(document.querySelector('#booking-form'),async f=>{
  await bookings.create({request_key:f.get('request_key'),title:f.get('title'),bath_id:Number(f.get('bath_id')),standard_id:Number(f.get('standard_id')),start_at:ts(f.get('start')),end_at:ts(f.get('end')),clean_minutes:Number(f.get('clean_minutes')),stabilize_minutes:Number(f.get('stabilize_minutes'))});
  notify('预约成功，两类设备已成组占用');await refresh();});
 submit(document.querySelector('#downtime-form'),async f=>{
  const r=await downtimes.create({request_key:f.get('request_key'),equipment_id:Number(f.get('equipment_id')),start_at:ts(f.get('start')),end_at:ts(f.get('end')),reason:f.get('reason')});
  const parts=['停用已登记'];if(r.rescheduled.length)parts.push('整组改期 '+r.rescheduled.length+' 单');if(r.pending.length)parts.push('无共同空档待重排 '+r.pending.length+' 单');
  notify(parts.join('，'),!!r.pending.length);await refresh();});
 submit(document.querySelector('#reading-form'),async f=>{
  const opt=document.querySelector('#reading-form [name=booking_id] option:checked');
  const r=await bookings.submitReadings({booking_id:Number(f.get('booking_id')),bath_id:Number(opt.dataset.bath),standard_id:Number(opt.dataset.std),records:JSON.parse(f.get('records'))});
  notify('已接收 '+r.accepted+' 条读数');await refresh();});
 document.querySelectorAll('[data-act]').forEach(btn=>btn.onclick=async()=>{
  try{
   const id=btn.dataset.id;
   if(btn.dataset.act==='start'){await bookings.start(id);notify('已开工，可接报读数');}
   else if(btn.dataset.act==='seal'){const r=await bookings.seal(id);notify('已封卷，生成唯一分析批次 '+r.batch.batch_no);}
   else{const b=await bookings.reschedule(id);notify('已重排至 '+date(b.start_at));}
   await refresh();
  }catch(e){notify(e.message,true);}
 });
}
