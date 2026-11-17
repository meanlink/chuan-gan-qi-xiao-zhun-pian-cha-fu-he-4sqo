import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def equipment_dict(e):
    return {k:getattr(e,k) for k in ['id','code','name','kind']}
def booking_dict(b):
    d={k:getattr(b,k) for k in ['id','code','title','bath_id','standard_id','start_at','end_at','clean_minutes','stabilize_minutes','status','reschedule_reason','created_at','started_at','sealed_at']}
    d['occ_start']=b.start_at-(b.clean_minutes+b.stabilize_minutes)*60
    d['occ_end']=b.end_at
    return d
def downtime_dict(d):
    return {k:getattr(d,k) for k in ['id','equipment_id','start_at','end_at','reason','created_at']}
def reading_dict(r):
    return {k:getattr(r,k) for k in ['id','booking_id','sample','band','reference','measured','received_at']}
def batch_dict(b):
    return {k:getattr(b,k) for k in ['id','batch_no','booking_id','dataset_id','rows','checksum','created_at']}
