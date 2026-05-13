from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    patient = db.relationship('Patient', backref='user', uselist=False)

class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    full_name = db.Column(db.String(120), nullable=False)
    patient_type = db.Column(db.String(20), default='new')
    priority_status = db.Column(db.String(20), default='none')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Queue(db.Model):
    __tablename__ = 'queue'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    concern = db.Column(db.String(200), nullable=False)
    priority_score = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    is_emergency = db.Column(db.Boolean, default=False)
    queued_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('Patient', backref='queue_entries')

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    concern = db.Column(db.String(200), nullable=False)
    priority_status = db.Column(db.String(20), default='none')
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(10), nullable=False, default='09:00')  # e.g. "09:00"
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('Patient', backref='appointments')