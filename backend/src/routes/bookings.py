import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.config.database import get_db
from src.models import Equipment, Booking, Downtime, Reading, AnalysisBatch
from src.schemas.booking import BookingInput, DowntimeInput, ReadingInput
from src.middlewares.auth import current_user, can_write
from src.services import bookings
from src.services.audit import record
from src.utils.serialization import (equipment_dict, booking_dict, downtime_dict,
                                     reading_dict, batch_dict)
router = APIRouter()

@router.get('/equipment')
def equipment_list(db=Depends(get_db), u=Depends(current_user)):
    return [equipment_dict(e) for e in db.scalars(select(Equipment).order_by(Equipment.kind, Equipment.id))]

@router.get('/equipment/{id}/timeline')
def equipment_timeline(id: int, from_ts: float | None = None, to_ts: float | None = None,
                       db=Depends(get_db), u=Depends(current_user)):
    now = time.time()
    from_ts = from_ts if from_ts is not None else now - 86400
    to_ts = to_ts if to_ts is not None else now + 6 * 86400
    if to_ts <= from_ts or to_ts - from_ts > 31 * 86400:
        raise HTTPException(422, '时间轴窗口需为 31 天内的有效区间')
    t = bookings.timeline(db, id, from_ts, to_ts)
    return {'equipment': equipment_dict(t['equipment']), 'from_ts': from_ts, 'to_ts': to_ts,
            'bookings': t['bookings'], 'downtimes': t['downtimes']}

@router.get('/bookings')
def booking_list(db=Depends(get_db), u=Depends(current_user)):
    return [booking_dict(b) for b in db.scalars(select(Booking).order_by(Booking.id.desc()).limit(200))]

@router.post('/bookings', status_code=201)
def booking_create(data: BookingInput, db=Depends(get_db), u=Depends(can_write)):
    try:
        b, created = bookings.create_booking(db, data, u)
        if created:
            record(db, u.email, 'booking.create', {'id': b.id, 'code': b.code})
        db.commit()
    except IntegrityError:  # 同一 request_key 并发落库：唯一键兜底，返回已建单
        db.rollback()
        b = db.scalar(select(Booking).where(Booking.request_key == data.request_key))
        if not b:
            raise
    return booking_dict(b)

@router.get('/bookings/{id}')
def booking_detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    b = db.get(Booking, id)
    if not b:
        raise HTTPException(404, '预约单不存在')
    batch = db.scalar(select(AnalysisBatch).where(AnalysisBatch.booking_id == id))
    rows = db.scalars(select(Reading).where(Reading.booking_id == id).order_by(Reading.id)).all()
    return {**booking_dict(b), 'readings': [reading_dict(r) for r in rows],
            'batch': batch_dict(batch) if batch else None}

@router.post('/bookings/{id}/start')
def booking_start(id: int, db=Depends(get_db), u=Depends(can_write)):
    b = bookings.start_work(db, id)
    record(db, u.email, 'booking.start', {'id': b.id, 'code': b.code})
    db.commit()
    return booking_dict(b)

@router.post('/bookings/{id}/seal')
def booking_seal(id: int, db=Depends(get_db), u=Depends(can_write)):
    b, batch = bookings.seal(db, id)
    record(db, u.email, 'booking.seal', {'id': b.id, 'code': b.code, 'batch': batch.batch_no, 'rows': batch.rows})
    db.commit()
    return {**booking_dict(b), 'batch': batch_dict(batch)}

@router.post('/bookings/{id}/reschedule')
def booking_reschedule(id: int, db=Depends(get_db), u=Depends(can_write)):
    b = bookings.reschedule(db, id)
    record(db, u.email, 'booking.reschedule', {'id': b.id, 'code': b.code})
    db.commit()
    return booking_dict(b)

@router.post('/readings', status_code=201)
def readings_submit(data: ReadingInput, db=Depends(get_db), u=Depends(can_write)):
    b, count = bookings.add_readings(db, data)
    record(db, u.email, 'reading.submit', {'booking': b.code, 'rows': count})
    db.commit()
    return {'booking_id': b.id, 'accepted': count}

@router.get('/downtimes')
def downtime_list(db=Depends(get_db), u=Depends(current_user)):
    return [downtime_dict(d) for d in db.scalars(select(Downtime).order_by(Downtime.id.desc()).limit(100))]

@router.post('/downtimes', status_code=201)
def downtime_create(data: DowntimeInput, db=Depends(get_db), u=Depends(can_write)):
    try:
        d, rescheduled, pending = bookings.create_downtime(db, data, u)
        record(db, u.email, 'downtime.create', {'equipment_id': d.equipment_id,
               'rescheduled': [b.code for b in rescheduled], 'pending': [b.code for b in pending]})
        db.commit()
    except IntegrityError:  # 同一 request_key 并发落库：唯一键兜底
        db.rollback()
        if not data.request_key:
            raise
        d = db.scalar(select(Downtime).where(Downtime.request_key == data.request_key))
        rescheduled, pending = [], []
    return {'downtime': downtime_dict(d),
            'rescheduled': [booking_dict(b) for b in rescheduled],
            'pending': [booking_dict(b) for b in pending]}

@router.get('/batches')
def batch_list(db=Depends(get_db), u=Depends(current_user)):
    return [batch_dict(x) for x in db.scalars(select(AnalysisBatch).order_by(AnalysisBatch.id.desc()).limit(100))]
