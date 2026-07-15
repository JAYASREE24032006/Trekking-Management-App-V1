import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'trekora_secure_secret_key'

# Configure SQLite database
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'trekora.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import models and initialize database integration
from models import db, User, Trek, Booking
db.init_app(app)

# ----------------- SESSION HELPERS -----------------

def is_logged_in():
    return 'user_id' in session

def get_current_user():
    if is_logged_in():
        return db.session.get(User, session['user_id'])
    return None

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

# ----------------- ROUTES -----------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'error')
            return redirect(url_for('login'))
        if user.status == 'pending':
            flash('Your staff registration is pending approval by the Admin.', 'error')
            return redirect(url_for('login'))
        if user.status == 'blacklisted':
            flash('Your account has been deactivated or blacklisted.', 'error')
            return redirect(url_for('login'))
            
        session['user_id'] = user.id
        session['email'] = user.email
        session['name'] = user.name
        session['role'] = user.role
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if is_logged_in():
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        contact = request.form.get('contact', '').strip()
        role = request.form.get('role', '')
        password = request.form.get('password', '')
        
        if User.query.filter_by(email=email).first():
            flash('Email address is already registered.', 'error')
            return redirect(url_for('register'))
            
        status = 'pending' if role == 'staff' else 'approved'
        new_user = User(
            name=name, email=email, contact=contact, role=role,
            password_hash=generate_password_hash(password), status=status
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# ----------------- ADMIN ROUTES -----------------

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
        
    active_tab = request.args.get('tab', 'dashboard')
    edit_id = request.args.get('edit')
    search_query = request.args.get('query', '').strip()
    
    editing_trek = db.session.get(Trek, edit_id) if edit_id else None
    approved_staff = User.query.filter_by(role='staff', status='approved').all()
    
    # Stats
    total_treks = Trek.query.count()
    total_users = User.query.filter_by(role='user').count()
    total_staff = User.query.filter_by(role='staff').count()
    total_bookings = Booking.query.count()
    
    bookings = Booking.query.order_by(Booking.id.desc()).all()
    treks = Trek.query.all()
    pending_staff = User.query.filter_by(role='staff', status='pending').all()
    approved_staff_list = User.query.filter_by(role='staff', status='approved').all()
    blacklisted_staff = User.query.filter_by(role='staff', status='blacklisted').all()
    users = User.query.filter_by(role='user').all()
    
    search_treks, search_staff, search_users = [], [], []
    if search_query:
        search_treks = Trek.query.filter(Trek.name.like(f'%{search_query}%')).all()
        search_staff = User.query.filter_by(role='staff').filter((User.name.like(f'%{search_query}%')) | (User.email.like(f'%{search_query}%'))).all()
        search_users = User.query.filter_by(role='user').filter((User.name.like(f'%{search_query}%')) | (User.email.like(f'%{search_query}%'))).all()
        
    return render_template(
        'admin.html', active_tab=active_tab, total_treks=total_treks, total_users=total_users,
        total_staff=total_staff, total_bookings=total_bookings, bookings=bookings, treks=treks,
        pending_staff=pending_staff, approved_staff=approved_staff, approved_staff_list=approved_staff_list,
        blacklisted_staff=blacklisted_staff, users=users, editing_trek=editing_trek, search_query=search_query,
        search_treks=search_treks, search_staff=search_staff, search_users=search_users
    )

@app.route('/admin/trek/new', methods=['POST'])
def admin_new_trek():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    staff_id = request.form.get('staff_id')
    slots = int(request.form.get('slots', 1))
    
    new_trek = Trek(
        name=request.form.get('name'),
        location=request.form.get('location'),
        difficulty=request.form.get('difficulty'),
        duration=int(request.form.get('duration', 1)),
        slots=slots,
        available_slots=slots,
        staff_id=int(staff_id) if staff_id else None,
        status=request.form.get('status'),
        start_date=request.form.get('start_date'),
        end_date=request.form.get('end_date'),
        description=request.form.get('description')
    )
    db.session.add(new_trek)
    db.session.commit()
    flash('New trek route created successfully!', 'success')
    return redirect('/admin?tab=treks')

@app.route('/admin/trek/edit/<int:trek_id>', methods=['POST'])
def admin_edit_trek(trek_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    trek = db.session.get(Trek, trek_id)
    if not trek:
        return redirect('/admin?tab=treks')
        
    slots = int(request.form.get('slots', 1))
    booked_slots = trek.slots - trek.available_slots
    if slots < booked_slots:
        flash(f'Cannot decrease slots below currently booked count ({booked_slots}).', 'error')
        return redirect(f'/admin?edit={trek_id}')
        
    trek.name = request.form.get('name')
    trek.location = request.form.get('location')
    trek.difficulty = request.form.get('difficulty')
    trek.duration = int(request.form.get('duration', 1))
    trek.slots = slots
    trek.available_slots = slots - booked_slots
    trek.start_date = request.form.get('start_date')
    trek.end_date = request.form.get('end_date')
    staff_id = request.form.get('staff_id')
    trek.staff_id = int(staff_id) if staff_id else None
    trek.status = request.form.get('status')
    trek.description = request.form.get('description')
    
    db.session.commit()
    flash('Trek details updated successfully.', 'success')
    return redirect('/admin?tab=treks')

@app.route('/admin/trek/delete/<int:trek_id>')
def admin_delete_trek(trek_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    trek = db.session.get(Trek, trek_id)
    if trek:
        db.session.delete(trek)
        db.session.commit()
        flash('Trek route and its bookings deleted successfully.', 'success')
    return redirect('/admin?tab=treks')

@app.route('/admin/staff/approve/<int:staff_id>')
def admin_approve_staff(staff_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    staff = db.session.get(User, staff_id)
    if staff:
        staff.status = 'approved'
        db.session.commit()
        flash(f'Staff member {staff.name} is now approved.', 'success')
    return redirect('/admin?tab=staff')

@app.route('/admin/staff/blacklist/<int:staff_id>')
def admin_blacklist_staff(staff_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    staff = db.session.get(User, staff_id)
    if staff:
        staff.status = 'blacklisted'
        Trek.query.filter_by(staff_id=staff_id).update({Trek.staff_id: None})
        db.session.commit()
        flash(f'Staff member {staff.name} has been blacklisted and unassigned from all treks.', 'success')
    return redirect('/admin?tab=staff')

@app.route('/admin/user/approve/<int:user_id>')
def admin_approve_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    user = db.session.get(User, user_id)
    if user:
        user.status = 'approved'
        db.session.commit()
        flash(f'Trekker {user.name} is now activated.', 'success')
    return redirect('/admin?tab=users')

@app.route('/admin/user/blacklist/<int:user_id>')
def admin_blacklist_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    user = db.session.get(User, user_id)
    if user:
        user.status = 'blacklisted'
        db.session.commit()
        flash(f'Trekker {user.name} has been blacklisted.', 'success')
    return redirect('/admin?tab=users')

# ----------------- STAFF ROUTES -----------------

@app.route('/staff')
def staff_dashboard():
    if session.get('role') != 'staff':
        return redirect(url_for('index'))
    user = get_current_user()
    if not user or user.status != 'approved':
        session.clear()
        return redirect(url_for('login'))
        
    manage_id = request.args.get('manage')
    managing_trek = db.session.get(Trek, manage_id) if manage_id else None
    
    if managing_trek and managing_trek.staff_id != user.id:
        return redirect(url_for('staff_dashboard'))
        
    bookings = Booking.query.filter_by(trek_id=manage_id).all() if manage_id else []
    assigned_treks = Trek.query.filter_by(staff_id=user.id).all()
    
    total_assigned = len(assigned_treks)
    total_hikers = sum(len([b for b in t.bookings if b.status == 'Booked']) for t in assigned_treks)
    total_open = sum(1 for t in assigned_treks if t.status == 'Open')
            
    return render_template(
        'staff.html', assigned_treks=assigned_treks, total_assigned=total_assigned,
        total_hikers=total_hikers, total_open=total_open, managing_trek=managing_trek, bookings=bookings
    )

@app.route('/staff/trek/update/<int:trek_id>', methods=['POST'])
def staff_update_trek(trek_id):
    if session.get('role') != 'staff':
        return redirect(url_for('index'))
    user = get_current_user()
    trek = db.session.get(Trek, trek_id)
    if not trek or trek.staff_id != user.id:
        return redirect(url_for('staff_dashboard'))
        
    slots = int(request.form.get('slots', 0))
    booked_slots = trek.slots - trek.available_slots
    if slots < booked_slots:
        flash(f'Cannot decrease slots below currently booked count ({booked_slots}).', 'error')
        return redirect(f'/staff?manage={trek_id}')
        
    trek.slots = slots
    trek.available_slots = slots - booked_slots
    trek.status = request.form.get('status')
    db.session.commit()
    flash('Trek settings updated successfully.', 'success')
    return redirect(f'/staff?manage={trek_id}')

@app.route('/staff/trek/start/<int:trek_id>')
def staff_start_trek(trek_id):
    if session.get('role') != 'staff':
        return redirect(url_for('index'))
    trek = db.session.get(Trek, trek_id)
    if trek and trek.staff_id == session.get('user_id'):
        trek.status = 'Started'
        db.session.commit()
        flash(f'Trek {trek.name} is now marked as Started!', 'success')
    return redirect(f'/staff?manage={trek_id}')

@app.route('/staff/trek/complete/<int:trek_id>')
def staff_complete_trek(trek_id):
    if session.get('role') != 'staff':
        return redirect(url_for('index'))
    trek = db.session.get(Trek, trek_id)
    if trek and trek.staff_id == session.get('user_id'):
        trek.status = 'Completed'
        for b in Booking.query.filter_by(trek_id=trek.id, status='Booked').all():
            b.status = 'Completed'
        db.session.commit()
        flash(f'Trek {trek.name} marked as Completed. All bookings updated to Completed.', 'success')
    return redirect(f'/staff?manage={trek_id}')

# ----------------- USER ROUTES -----------------

@app.route('/user')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('index'))
    user = get_current_user()
    if not user or user.status == 'blacklisted':
        session.clear()
        return redirect(url_for('login'))
        
    active_tab = request.args.get('tab', 'browse')
    diff_filter = request.args.get('difficulty', '')
    loc_filter = request.args.get('location', '').strip()
    
    treks_query = Trek.query.filter(Trek.status.in_(['Approved', 'Open']))
    if diff_filter:
        treks_query = treks_query.filter_by(difficulty=diff_filter)
    if loc_filter:
        treks_query = treks_query.filter(Trek.location.like(f'%{loc_filter}%'))
    treks = treks_query.all()
    
    bookings = Booking.query.filter_by(user_id=user.id, status='Booked').order_by(Booking.id.desc()).all()
    history = Booking.query.filter_by(user_id=user.id).filter(Booking.status.in_(['Cancelled', 'Completed'])).order_by(Booking.id.desc()).all()
    
    return render_template(
        'user.html', active_tab=active_tab, treks=treks, bookings=bookings,
        history=history, user_profile=user, difficulty_filter=diff_filter, location_filter=loc_filter
    )

@app.route('/user/profile', methods=['POST'])
def user_update_profile():
    if session.get('role') != 'user':
        return redirect(url_for('index'))
    user = get_current_user()
    name = request.form.get('name', '').strip()
    contact = request.form.get('contact', '').strip()
    if name and contact:
        user.name, user.contact = name, contact
        db.session.commit()
        session['name'] = name
        flash('Profile updated.', 'success')
    return redirect('/user?tab=profile')

@app.route('/trek/<int:trek_id>')
def trek_details(trek_id):
    if not is_logged_in():
        return redirect(url_for('login'))
    trek = db.session.get(Trek, trek_id)
    return render_template('trek_details.html', trek=trek)

@app.route('/trek/<int:trek_id>/book')
def user_book_trek(trek_id):
    if session.get('role') != 'user':
        return redirect(url_for('index'))
    user = get_current_user()
    trek = db.session.get(Trek, trek_id)
    
    if trek and trek.status == 'Open' and trek.available_slots > 0:
        if not Booking.query.filter_by(user_id=user.id, trek_id=trek_id, status='Booked').first():
            trek.available_slots -= 1
            new_booking = Booking(user_id=user.id, trek_id=trek_id, status='Booked')
            db.session.add(new_booking)
            db.session.commit()
            flash(f'Trek "{trek.name}" booked successfully!', 'success')
            return redirect('/user?tab=bookings')
    flash('Unable to book trek.', 'error')
    return redirect('/user')

@app.route('/booking/cancel/<int:booking_id>')
def user_cancel_booking(booking_id):
    if session.get('role') != 'user':
        return redirect(url_for('index'))
    booking = db.session.get(Booking, booking_id)
    if booking and booking.user_id == session.get('user_id') and booking.status == 'Booked':
        booking.trek.available_slots += 1
        booking.status = 'Cancelled'
        db.session.commit()
        flash('Booking cancelled successfully.', 'success')
    return redirect('/user?tab=bookings')

# ----------------- REST API ENDPOINTS -----------------

@app.route('/api/treks')
def api_get_treks():
    treks = Trek.query.all()
    return jsonify([{
        'id': t.id, 'name': t.name, 'location': t.location, 'difficulty': t.difficulty,
        'duration': t.duration, 'slots': t.slots, 'available_slots': t.available_slots,
        'status': t.status, 'start_date': t.start_date, 'end_date': t.end_date,
        'assigned_staff': t.staff.name if t.staff else None
    } for t in treks])

@app.route('/api/bookings')
def api_get_bookings():
    bookings = Booking.query.all()
    return jsonify([{
        'id': b.id, 'user_id': b.user_id, 'user_name': b.user.name, 'trek_id': b.trek_id,
        'trek_name': b.trek.name, 'booking_date': b.booking_date, 'status': b.status
    } for b in bookings])

# ----------------- APP INITIATOR -----------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Seed default admin if not exists
        if not User.query.filter_by(email='admin@trekora.com').first():
            db.session.add(User(
                name='System Admin',
                email='admin@trekora.com',
                contact='9999999999',
                role='admin',
                password_hash=generate_password_hash('admin123'),
                status='approved'
            ))
            db.session.commit()
            print("Seeded default admin (admin@trekora.com / admin123)")
    app.run(debug=True, port=5000)
