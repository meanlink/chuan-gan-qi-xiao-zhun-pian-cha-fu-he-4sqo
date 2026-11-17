import time, json
from sqlalchemy import select, func
from src.config.database import Session
from migrations.initial import migrate
from src.models import User, Dataset, Job, Report, Delivery, Audit, Equipment, Booking
from src.services.business import metadata, seed_records, analyze
from src.services.reports import deliver
from src.utils.security import hash_password
from src.utils.serialization import checksum
def seed():
    migrate()
    with Session() as db:
        for role,name in [('admin','林知 · 业务负责人'),('analyst','陈舟 · 分析员'),('viewer','周禾 · 观察员')]:
            email=role+'@demo.local'
            if not db.scalar(select(User).where(User.email==email)):
                db.add(User(email=email,name=name,role=role,password=hash_password('Demo123!')))
        db.flush()
        for code,name,kind in [('BATH-01','恒温槽 BATH-01 · 低温槽','bath'),('BATH-02','恒温槽 BATH-02 · 高温槽','bath'),
                               ('STD-01','标准仪 STD-01 · 标准铂电阻','standard'),('STD-02','标准仪 STD-02 · 精密测温电桥','standard')]:
            if not db.scalar(select(Equipment).where(Equipment.code==code)):
                db.add(Equipment(code=code,name=name,kind=kind))
        db.flush()
        m=metadata()
        d=db.scalar(select(Dataset).where(Dataset.name==m['dataset_name']))
        if not d:
            rows=seed_records()
            d=Dataset(name=m['dataset_name'],source=m['short']+'-202611.csv',records=rows,checksum=checksum(rows),created_at=time.time())
            db.add(d); db.flush()
        if not db.scalar(select(Job).where(Job.name=='基线复核 · '+m['name'])):
            params={p['key']:p['default'] for p in m.get('parameters',[])}
            result=analyze(d.records,params)
            json.dumps(result,ensure_ascii=False,allow_nan=False)
            admin=db.scalar(select(User).where(User.role=='admin'))
            j=Job(name='基线复核 · '+m['name'],dataset_id=d.id,params=params,status='completed',result=result,created_by=admin.id,created_at=time.time()-3600,finished_at=time.time()-3595,approved=True)
            db.add(j);db.flush()
            r=Report(name='每日业务复核简报',job_id=j.id,destination='业务复核组 · 本地收件箱',interval_seconds=86400,next_run=time.time()+86400,enabled=True)
            db.add(r);db.flush();deliver(db,r)
            db.add(Audit(actor='seed',action='demo.baseline',detail={'dataset':d.id},at=time.time()))
        if not db.scalar(select(Booking).limit(1)):
            admin=db.scalar(select(User).where(User.role=='admin'))
            bath=db.scalar(select(Equipment).where(Equipment.code=='BATH-01'))
            std=db.scalar(select(Equipment).where(Equipment.code=='STD-01'))
            day=86400
            tomorrow=int(time.time()//day+1)*day
            b=Booking(code='TMP-SEED',request_key='seed-demo-booking',title='T-24 探头批次 · 高温区抽校',bath_id=bath.id,standard_id=std.id,
                      start_at=tomorrow+9*3600,end_at=tomorrow+12*3600,clean_minutes=30,stabilize_minutes=20,
                      status='booked',created_by=admin.id,created_at=time.time())
            db.add(b);db.flush();b.code=f'BK-{b.id:04d}'
            db.add(Audit(actor='seed',action='demo.booking',detail={'booking':b.code},at=time.time()))
        db.commit()
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in [User,Dataset,Job,Report,Delivery,Audit,Equipment,Booking]}
        print(json.dumps(counts,ensure_ascii=False))
        return counts
if __name__=='__main__':seed()
