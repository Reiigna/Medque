import heapq
from models import Queue, db

def get_priority_score(patient_type, priority_status):
    """
    Returns a numeric score — lower = higher priority.
    0 = Emergency
    1 = PWD / Senior / Pregnant
    2 = Returning patient
    3 = New patient
    """
    if priority_status == 'emergency':
        return 0
    if priority_status in ('pwd', 'senior', 'pregnant'):
        return 1
    if patient_type == 'returning':
        return 2
    return 3

def get_sorted_queue():
    """
    Returns all waiting queue entries sorted by priority score,
    then by time they joined (FIFO within same priority).
    Uses Python's heapq for heap-based sorting.
    """
    waiting = Queue.query.filter_by(status='waiting').all()
    heap = []
    for entry in waiting:
        # Tuple: (score, datetime, entry) — heapq sorts by first element, then second
        heapq.heappush(heap, (entry.priority_score, entry.queued_at, entry))
    sorted_queue = []
    while heap:
        _, _, entry = heapq.heappop(heap)
        sorted_queue.append(entry)
    return sorted_queue

def get_current_patient():
    """Returns the patient currently being seen (status = in_progress)."""
    return Queue.query.filter_by(status='in_progress').first()

def estimate_wait_time(position, avg_minutes_per_patient=12):
    """Estimates wait time in minutes based on queue position."""
    return position * avg_minutes_per_patient