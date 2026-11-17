from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class EquipmentKind(str, Enum):
    bath = 'bath'
    standard = 'standard'
class BookingStatus(str, Enum):
    booked = 'booked'
    in_progress = 'in_progress'
    sealed = 'sealed'
    pending_reschedule = 'pending_reschedule'
