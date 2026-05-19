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
    Fetches all active queue entries that are either waiting in the lobby 
    or currently inside the examination room with the doctor.
    """
    return Queue.query.filter(Queue.status.in_(['waiting', 'in_progress'])).all()

def get_current_patient():
    """Returns the patient currently being seen (status = in_progress)."""
    return Queue.query.filter_by(status='in_progress').first()

def estimate_wait_time(queue_position):
    """
    Estimates wait time in minutes based on the number of people ahead.
    Assumes an average of 15 minutes per dental/medical checkup consultation.
    """
    if queue_position <= 0:
        return 0
        
    AVERAGE_MINUTES_PER_PATIENT = 15
    estimated_minutes = queue_position * AVERAGE_MINUTES_PER_PATIENT
    
    # Safety guard: Ensure we never return a negative calculation tracking glitch
    return max(0, estimated_minutes)