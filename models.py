from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'staff', 'user'
    status = db.Column(db.String(20), default='approved')  # 'pending', 'approved', 'blacklisted'
    contact = db.Column(db.String(20), nullable=True)
    
    bookings = db.relationship('Booking', backref='user', lazy=True, cascade="all, delete-orphan")
    assigned_treks = db.relationship('Trek', backref='staff', lazy=True)

class Trek(db.Model):
    __tablename__ = 'treks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # 'Easy', 'Moderate', 'Hard'
    duration = db.Column(db.Integer, nullable=False)
    slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(20), default='Pending')  # 'Pending', 'Approved', 'Open', 'Closed', 'Completed'
    start_date = db.Column(db.String(10), nullable=False)
    end_date = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    bookings = db.relationship('Booking', backref='trek', lazy=True, cascade="all, delete-orphan")

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('treks.id'), nullable=False)
    booking_date = db.Column(db.String(19), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    status = db.Column(db.String(20), default='Booked')  # 'Booked', 'Cancelled', 'Completed'
