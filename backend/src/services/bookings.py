"""校准预约：两类设备成组占用、停用改期、读数接报与封卷建批。

并发约定：先按 id 升序锁设备行，再锁预约单行；开工/封卷/接报只锁预约单。
所有改期与建批都在单事务内完成，中断回滚即恢复原单，重试由唯一键兜底。
"""
import math
import secrets
import time
from fastapi import HTTPException
from sqlalchemy import select, or_
from src.models import Equipment, Booking, Downtime, Reading, AnalysisBatch, Dataset
from src.utils.serialization import checksum

ACTIVE = ('booked', 'in_progress')  # 占用设备的状态；待重排不占档
HORIZON_DAYS = 14  # 共同空档搜索范围


def fmt(t):
    return time.strftime('%m-%d %H:%M', time.localtime(t))


def occupancy(b):
    """清洗与稳定时间计入占用：占用区间 = [开工窗口起点 - 缓冲, 窗口终点]。"""
    return (b.start_at - (b.clean_minutes + b.stabilize_minutes) * 60, b.end_at)


def _overlaps(s1, e1, s2, e2):
    return s1 < e2 and s2 < e1


def lock_equipment(db, ids):
    ids = sorted({int(i) for i in ids})
    return db.scalars(select(Equipment).where(Equipment.id.in_(ids)).order_by(Equipment.id).with_for_update()).all()


def lock_booking(db, booking_id):
    return db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())


def _equipment_busy(db, equipment_id, ignore_booking_id=None):
    """设备上的全部占用区间（生效中的预约 + 停用），供冲突与找空档共用。"""
    busy = []
    q = select(Booking).where(Booking.status.in_(ACTIVE), or_(Booking.bath_id == equipment_id, Booking.standard_id == equipment_id))
    for b in db.scalars(q):
        if ignore_booking_id and b.id == ignore_booking_id:
            continue
        s, e = occupancy(b)
        busy.append(('booking', b, s, e))
    for d in db.scalars(select(Downtime).where(Downtime.equipment_id == equipment_id)):
        busy.append(('downtime', d, d.start_at, d.end_at))
    return busy


def conflict_reasons(db, equipment, start, end, ignore_booking_id=None):
    reasons = []
    for kind, obj, s, e in _equipment_busy(db, equipment.id, ignore_booking_id):
        if not _overlaps(start, end, s, e):
            continue
        if kind == 'booking':
            reasons.append(f'{equipment.name} {fmt(s)}–{fmt(e)} 已被预约 {obj.code}「{obj.title}」成组占用（含清洗与稳定）')
        else:
            reasons.append(f'{equipment.name} {fmt(s)}–{fmt(e)} 停用（{obj.reason}）')
    return reasons


def find_slot(db, booking, earliest):
    """为整组预约找两类设备的共同空档，返回测量窗口起点；找不到返回 None。"""
    buffer = (booking.clean_minutes + booking.stabilize_minutes) * 60
    total = booking.end_at - booking.start_at + buffer
    busy = []
    for equipment_id in (booking.bath_id, booking.standard_id):
        busy += [(s, e) for _, _, s, e in _equipment_busy(db, equipment_id, ignore_booking_id=booking.id)]
    busy.sort()
    candidate = max(earliest, time.time())
    limit = candidate + HORIZON_DAYS * 86400
    while candidate + total <= limit:
        hit = None
        for s, e in busy:
            if e <= candidate:
                continue
            if s >= candidate + total:
                break
            hit = (s, e)
            break
        if hit is None:
            return candidate + buffer
        candidate = hit[1]
    return None


def create_booking(db, data, user):
    existing = db.scalar(select(Booking).where(Booking.request_key == data.request_key))
    if existing:  # 重试不新增占用
        return existing, False
    if data.end_at <= data.start_at:
        raise HTTPException(422, '结束时间必须晚于开始时间')
    if data.end_at - data.start_at > 24 * 3600:
        raise HTTPException(422, '单次测量窗口最长 24 小时')
    if data.start_at < time.time() - 600:
        raise HTTPException(422, '不能预约过去的时段')
    if data.bath_id == data.standard_id:
        raise HTTPException(422, '恒温槽与标准仪必须是两台不同设备')
    title = data.title.strip()
    if len(title) < 2:
        raise HTTPException(422, '预约名称去除空格后至少需要两个字符')
    equipment = {e.id: e for e in lock_equipment(db, [data.bath_id, data.standard_id])}
    bath, standard = equipment.get(data.bath_id), equipment.get(data.standard_id)
    if not bath or bath.kind != 'bath':
        raise HTTPException(422, '所选恒温槽不存在或类型不符')
    if not standard or standard.kind != 'standard':
        raise HTTPException(422, '所选标准仪不存在或类型不符')
    # 锁内复查：并发同键请求等待行锁期间对方已落库，按幂等返回原单
    existing = db.scalar(select(Booking).where(Booking.request_key == data.request_key))
    if existing:
        return existing, False
    b = Booking(code='TMP-' + secrets.token_hex(8), request_key=data.request_key, title=title, bath_id=bath.id, standard_id=standard.id,
                start_at=data.start_at, end_at=data.end_at, clean_minutes=data.clean_minutes,
                stabilize_minutes=data.stabilize_minutes, status='booked', created_by=user.id, created_at=time.time())
    start, end = occupancy(b)
    reasons = conflict_reasons(db, bath, start, end) + conflict_reasons(db, standard, start, end)
    if reasons:
        raise HTTPException(409, '；'.join(reasons))
    db.add(b)
    db.flush()
    b.code = f'BK-{b.id:04d}'
    db.flush()
    return b, True


def start_work(db, booking_id):
    b = lock_booking(db, booking_id)
    if not b:
        raise HTTPException(404, '预约单不存在')
    if b.status == 'in_progress':
        return b
    if b.status != 'booked':
        raise HTTPException(409, '仅已预约状态可以开工')
    b.status = 'in_progress'
    b.started_at = time.time()
    db.flush()
    return b


def seal(db, booking_id):
    b = lock_booking(db, booking_id)
    if not b:
        raise HTTPException(404, '预约单不存在')
    batch = db.scalar(select(AnalysisBatch).where(AnalysisBatch.booking_id == b.id))
    if b.status == 'sealed' and batch:  # 建批幂等：中断恢复后重试不重复建批
        return b, batch
    if b.status != 'in_progress':
        raise HTTPException(409, '仅进行中的预约可以封卷')
    readings = db.scalars(select(Reading).where(Reading.booking_id == b.id).order_by(Reading.id)).all()
    if not readings:
        raise HTTPException(409, '尚无读数，不能封卷')
    records = [{'sample': r.sample, 'band': r.band, 'reference': r.reference, 'measured': r.measured} for r in readings]
    batch_no = 'CAL-' + time.strftime('%Y%m%d') + f'-{b.id:04d}'
    ds = Dataset(name=f'{batch_no} · {b.title}'[:160], source=f'预约封卷 · {b.code}', records=records,
                 checksum=checksum(records), created_at=time.time())
    db.add(ds)
    db.flush()
    batch = AnalysisBatch(batch_no=batch_no, booking_id=b.id, dataset_id=ds.id, rows=len(records),
                          checksum=checksum(records), created_at=time.time())
    db.add(batch)
    b.status = 'sealed'
    b.sealed_at = time.time()
    db.flush()
    return b, batch


def add_readings(db, data):
    b = lock_booking(db, data.booking_id)  # 与封卷互斥：先落定者生效
    if not b:
        raise HTTPException(404, '预约单不存在')
    if b.status == 'sealed':
        raise HTTPException(409, f'预约 {b.code} 已封卷，晚到读数不再接收')
    if b.status != 'in_progress':
        raise HTTPException(409, f'预约 {b.code} 未开工，读数拒收')
    if b.bath_id != data.bath_id or b.standard_id != data.standard_id:
        raise HTTPException(409, '上报设备与预约成组设备不符，读数拒收')
    rows = []
    for i, row in enumerate(data.records):
        try:
            sample, band = str(row['sample']).strip(), str(row['band']).strip()
            reference, measured = float(row['reference']), float(row['measured'])
            if not sample or not band or not all(map(math.isfinite, (reference, measured))):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, f'第 {i+1} 条读数需含读数编号、温区和两个有限数值')
        rows.append(Reading(booking_id=b.id, sample=sample, band=band, reference=reference,
                            measured=measured, received_at=time.time()))
    db.add_all(rows)
    db.flush()
    return b, len(rows)


def create_downtime(db, data, user):
    if data.request_key:
        existing = db.scalar(select(Downtime).where(Downtime.request_key == data.request_key))
        if existing:  # 重试不新增停用
            return existing, [], []
    if data.end_at <= data.start_at:
        raise HTTPException(422, '停用结束时间必须晚于开始时间')
    equipment = {e.id: e for e in lock_equipment(db, [data.equipment_id])}.get(data.equipment_id)
    if not equipment:
        raise HTTPException(404, '设备不存在')
    d = Downtime(equipment_id=equipment.id, start_at=data.start_at, end_at=data.end_at,
                 reason=data.reason.strip(), request_key=data.request_key, created_by=user.id, created_at=time.time())
    db.add(d)
    db.flush()
    rescheduled, pending = [], []
    q = (select(Booking).where(Booking.status == 'booked', or_(Booking.bath_id == equipment.id, Booking.standard_id == equipment.id))
         .order_by(Booking.id).with_for_update())
    for b in db.scalars(q):
        s, e = occupancy(b)
        if not _overlaps(s, e, d.start_at, d.end_at):
            continue
        new_start = find_slot(db, b, earliest=d.end_at)
        if new_start is None:
            b.status = 'pending_reschedule'
            b.reschedule_reason = f'{equipment.name} {fmt(d.start_at)}–{fmt(d.end_at)} 停用（{d.reason}），{HORIZON_DAYS} 天内无共同空档，待重排'
            pending.append(b)
        else:
            old = f'{fmt(b.start_at)}–{fmt(b.end_at)}'
            b.end_at = new_start + (b.end_at - b.start_at)
            b.start_at = new_start
            b.reschedule_reason = f'因 {equipment.name} 停用（{d.reason}），自 {old} 整组改期'
            rescheduled.append(b)
    db.flush()
    return d, rescheduled, pending


def reschedule(db, booking_id):
    b0 = db.get(Booking, booking_id)
    if not b0:
        raise HTTPException(404, '预约单不存在')
    lock_equipment(db, [b0.bath_id, b0.standard_id])
    b = lock_booking(db, booking_id)
    if b.status != 'pending_reschedule':
        raise HTTPException(409, '仅待重排的预约需要重排')
    new_start = find_slot(db, b, earliest=max(time.time(), b.start_at))  # 改期不提前于原计划
    if new_start is None:
        raise HTTPException(409, f'{HORIZON_DAYS} 天内仍无共同空档，保持待重排')
    b.end_at = new_start + (b.end_at - b.start_at)
    b.start_at = new_start
    b.status = 'booked'
    b.reschedule_reason = f'已重排至 {fmt(b.start_at)}–{fmt(b.end_at)}'
    db.flush()
    return b


def timeline(db, equipment_id, from_ts, to_ts):
    e = db.get(Equipment, equipment_id)
    if not e:
        raise HTTPException(404, '设备不存在')
    bookings = []
    q = select(Booking).where(Booking.status.in_(ACTIVE), or_(Booking.bath_id == e.id, Booking.standard_id == e.id))
    for b in db.scalars(q):
        s, occ_end = occupancy(b)
        if _overlaps(s, occ_end, from_ts, to_ts):
            bookings.append({'code': b.code, 'title': b.title, 'status': b.status, 'start_at': s, 'end_at': occ_end})
    downtimes = [{'reason': d.reason, 'start_at': d.start_at, 'end_at': d.end_at}
                 for d in db.scalars(select(Downtime).where(Downtime.equipment_id == e.id))
                 if _overlaps(d.start_at, d.end_at, from_ts, to_ts)]
    return {'equipment': e, 'bookings': bookings, 'downtimes': downtimes}
