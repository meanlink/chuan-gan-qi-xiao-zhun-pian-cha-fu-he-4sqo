import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const equipment={list:()=>api('/equipment'),timeline:(id,from,to)=>api('/equipment/'+id+'/timeline?from_ts='+from+'&to_ts='+to)};
export const bookings={
 list:()=>api('/bookings'),get:id=>api('/bookings/'+id),create:data=>api('/bookings',{method:'POST',body:JSON.stringify(data)}),
 start:id=>api('/bookings/'+id+'/start',{method:'POST'}),seal:id=>api('/bookings/'+id+'/seal',{method:'POST'}),
 reschedule:id=>api('/bookings/'+id+'/reschedule',{method:'POST'}),
 submitReadings:data=>api('/readings',{method:'POST',body:JSON.stringify(data)})};
export const downtimes={list:()=>api('/downtimes'),create:data=>api('/downtimes',{method:'POST',body:JSON.stringify(data)})};
export const batches={list:()=>api('/batches')};
