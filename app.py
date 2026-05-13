from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Patient, Queue, Appointment
from queue_logic import get_priority_score, get_sorted_queue, get_current_patient, estimate_wait_time
from datetime import date, datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'medque-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medque.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Available time slots for appointments
TIME_SLOTS = [
    '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '13:00', '13:30', '14:00', '14:30',
    '15:00', '15:30', '16:00', '16:30'
]

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.role + '_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for(user.role + '_dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        priority_status = request.form.get('priority_status', 'none')

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('register.html')

        hashed_pw = generate_password_hash(password)
        user = User(username=username, password=hashed_pw, role='patient')
        db.session.add(user)
        db.session.flush()

        patient = Patient(user_id=user.id, full_name=full_name,
                          patient_type='new', priority_status=priority_status)
        db.session.add(patient)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# ── Secretary ─────────────────────────────────────────────────────────────────

@app.route('/secretary')
@login_required
@role_required('secretary')
def secretary_dashboard():
    queue = get_sorted_queue()
    current = get_current_patient()
    served_today = Queue.query.filter_by(status='done').count()
    priority_count = sum(1 for q in queue if q.priority_score <= 1)
    appointments = Appointment.query.filter_by(status='pending').order_by(
        Appointment.appointment_date, Appointment.appointment_time).all()
    return render_template('secretary/dashboard.html',
                           queue=queue, current=current,
                           served_today=served_today,
                           priority_count=priority_count,
                           appointments=appointments)

@app.route('/secretary/add_patient', methods=['POST'])
@login_required
@role_required('secretary')
def add_patient():
    full_name = request.form['full_name']
    patient_type = request.form['patient_type']
    priority_status = request.form['priority_status']
    concern = request.form['concern']

    existing_patient = Patient.query.filter(
        Patient.full_name.ilike(full_name)).first()

    if existing_patient:
        patient = existing_patient
        patient.patient_type = patient_type
        patient.priority_status = priority_status
    else:
        patient = Patient(full_name=full_name, patient_type=patient_type,
                          priority_status=priority_status)
        db.session.add(patient)
        db.session.flush()

    score = get_priority_score(patient_type, priority_status)
    entry = Queue(patient_id=patient.id, concern=concern, priority_score=score)
    db.session.add(entry)
    db.session.commit()
    flash(f'{full_name} added to queue.', 'success')
    return redirect(url_for('secretary_dashboard'))

@app.route('/secretary/admit_appointment/<int:appt_id>', methods=['POST'])
@login_required
@role_required('secretary')
def admit_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    appt.status = 'admitted'
    patient = appt.patient
    patient.priority_status = appt.priority_status
    score = get_priority_score(patient.patient_type, appt.priority_status)
    entry = Queue(patient_id=patient.id, concern=appt.concern, priority_score=score)
    db.session.add(entry)
    db.session.commit()
    flash(f'{patient.full_name} admitted into the queue.', 'success')
    return redirect(url_for('secretary_dashboard'))

@app.route('/secretary/cancel_appointment/<int:appt_id>', methods=['POST'])
@login_required
@role_required('secretary')
def cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    appt.status = 'cancelled'
    db.session.commit()
    flash('Appointment cancelled.', 'warning')
    return redirect(url_for('secretary_dashboard'))

@app.route('/secretary/emergency', methods=['POST'])
@login_required
@role_required('secretary')
def emergency_override():
    full_name = request.form['full_name']
    concern = request.form.get('concern', 'EMERGENCY')
    patient = Patient(full_name=full_name, patient_type='returning',
                      priority_status='emergency')
    db.session.add(patient)
    db.session.flush()
    entry = Queue(patient_id=patient.id, concern=concern,
                  priority_score=0, is_emergency=True)
    db.session.add(entry)
    db.session.commit()
    flash(f'EMERGENCY: {full_name} added to front of queue!', 'danger')
    return redirect(url_for('secretary_dashboard'))

@app.route('/secretary/remove/<int:queue_id>', methods=['POST'])
@login_required
@role_required('secretary')
def remove_from_queue(queue_id):
    entry = Queue.query.get_or_404(queue_id)
    entry.status = 'done'
    db.session.commit()
    return redirect(url_for('secretary_dashboard'))

# ── Doctor ────────────────────────────────────────────────────────────────────

@app.route('/doctor')
@login_required
@role_required('doctor')
def doctor_dashboard():
    current = get_current_patient()
    upcoming = get_sorted_queue()[:5]
    served_today = Queue.query.filter_by(status='done').count()
    waiting_count = Queue.query.filter_by(status='waiting').count()
    appointments = Appointment.query.filter_by(status='pending').order_by(
        Appointment.appointment_date, Appointment.appointment_time).all()
    return render_template('doctor/dashboard.html',
                           current=current, upcoming=upcoming,
                           served_today=served_today,
                           waiting_count=waiting_count,
                           appointments=appointments)

@app.route('/doctor/next', methods=['POST'])
@login_required
@role_required('doctor')
def next_patient():
    current = get_current_patient()
    if current:
        current.status = 'done'
        db.session.commit()
    queue = get_sorted_queue()
    if queue:
        queue[0].status = 'in_progress'
        db.session.commit()
    else:
        flash('No more patients in queue.', 'info')
    return redirect(url_for('doctor_dashboard'))

# ── Patient ───────────────────────────────────────────────────────────────────

@app.route('/patient')
@login_required
@role_required('patient')
def patient_dashboard():
    queue = get_sorted_queue()
    my_entry = None
    my_position = None
    show_up_time = None

    if current_user.patient:
        for i, entry in enumerate(queue):
            if entry.patient_id == current_user.patient.id:
                my_entry = entry
                my_position = i + 1
                break

    if my_position:
        arrive_position = max(1, my_position - 2)
        show_up_time = estimate_wait_time(arrive_position - 1)

    wait_time = estimate_wait_time(my_position - 1) if my_position else None
    current = get_current_patient()

    my_appointments = []
    if current_user.patient:
        my_appointments = Appointment.query.filter_by(
            patient_id=current_user.patient.id,
            status='pending'
        ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    # Get booked time slots for the booking form (used by JS)
    return render_template('patient/dashboard.html',
                           my_entry=my_entry,
                           my_position=my_position,
                           wait_time=wait_time,
                           show_up_time=show_up_time,
                           current=current,
                           queue_length=len(queue),
                           my_appointments=my_appointments,
                           time_slots=TIME_SLOTS)

@app.route('/patient/book', methods=['POST'])
@login_required
@role_required('patient')
def book_appointment():
    concern = request.form['concern']
    appt_date = request.form['appointment_date']
    appt_time = request.form['appointment_time']
    priority_status = request.form.get('priority_status', 'none')

    # Check if that time slot is already taken
    existing = Appointment.query.filter_by(
        appointment_date=date.fromisoformat(appt_date),
        appointment_time=appt_time,
        status='pending'
    ).first()

    if existing:
        flash(f'Sorry, {appt_time} on that date is already booked. Please choose another time.', 'danger')
        return redirect(url_for('patient_dashboard'))

    appt = Appointment(
        patient_id=current_user.patient.id,
        concern=concern,
        priority_status=priority_status,
        appointment_date=date.fromisoformat(appt_date),
        appointment_time=appt_time
    )
    db.session.add(appt)
    db.session.commit()
    flash('Appointment booked! The secretary will admit you to the queue on your chosen date.', 'success')
    return redirect(url_for('patient_dashboard'))

# ── API (real-time) ───────────────────────────────────────────────────────────

@app.route('/api/queue')
@login_required
def api_queue():
    queue = get_sorted_queue()
    current = get_current_patient()
    appointments = Appointment.query.filter_by(status='pending').order_by(
        Appointment.appointment_date, Appointment.appointment_time).all()
    data = {
        'queue_length': len(queue),
        'pending_appointments': len(appointments),
        'current': {
            'name': current.patient.full_name,
            'concern': current.concern
        } if current else None,
        'queue': [
            {
                'id': e.id,
                'name': e.patient.full_name,
                'concern': e.concern,
                'score': e.priority_score,
                'priority_status': e.patient.priority_status,
                'is_emergency': e.is_emergency
            } for e in queue
        ],
        'appointments': [
            {
                'id': a.id,
                'name': a.patient.full_name,
                'concern': a.concern,
                'date': a.appointment_date.strftime('%b %d, %Y'),
                'time': a.appointment_time,
                'priority': a.priority_status
            } for a in appointments
        ]
    }
    return jsonify(data)

@app.route('/api/booked_slots')
@login_required
def api_booked_slots():
    """Returns booked time slots for a given date — used by patient booking form."""
    selected_date = request.args.get('date')
    if not selected_date:
        return jsonify({'booked': []})
    booked = Appointment.query.filter_by(
        appointment_date=date.fromisoformat(selected_date),
        status='pending'
    ).all()
    return jsonify({'booked': [a.appointment_time for a in booked]})

# ── Seed ──────────────────────────────────────────────────────────────────────

def seed_users():
    if not User.query.filter_by(username='secretary').first():
        db.session.add(User(username='secretary',
                            password=generate_password_hash('secretary123'),
                            role='secretary'))
    if not User.query.filter_by(username='doctor').first():
        db.session.add(User(username='doctor',
                            password=generate_password_hash('doctor123'),
                            role='doctor'))
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_users()
        print("✓ Database ready")
        print("✓ Secretary login: secretary / secretary123")
        print("✓ Doctor login:    doctor / doctor123")
        print("✓ Patients register at /register")
    app.run(debug=True)