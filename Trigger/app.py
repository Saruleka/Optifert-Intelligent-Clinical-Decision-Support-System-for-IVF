import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection, init_db
from ml_service import run_prediction

app = Flask(__name__)
# Generate a hardcoded random key for Phase 1 MVP
app.secret_key = "a4b5c6d7e8f90123456789abcdef0123"

# --- DECORATORS & MODULAR FUNCTIONS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'doctor':
            flash("Access denied. Doctor privileges required.", "danger")
            return redirect(url_for('patient_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def patient_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'patient':
            flash("Access denied. Patient privileges required.", "danger")
            return redirect(url_for('doctor_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def link_patient_to_doctor(doctor_id, patient_email):
    """
    Modular logic linking a patient by email.
    Allows easy expansion into approval workflows later.
    """
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT id, role FROM users WHERE email = ?', (patient_email,)).fetchone()
        if not user:
            return False, "User not found."
            
        if user['role'] != 'patient':
            return False, "Email belongs to a non-patient account."
            
        patient_user_id = user['id']
        profile = conn.execute('SELECT doctor_id FROM patient_profiles WHERE user_id = ?', (patient_user_id,)).fetchone()
        
        if profile:
            if profile['doctor_id']:
                if profile['doctor_id'] == doctor_id:
                    return False, "Patient is already successfully linked to you."
                return False, "Patient is currently assigned to another doctor. Workflows for transferring are disabled in Phase 2."
            # Exists but doctor_id is null
            conn.execute('UPDATE patient_profiles SET doctor_id = ? WHERE user_id = ?', (doctor_id, patient_user_id))
        else:
            conn.execute('INSERT INTO patient_profiles (user_id, doctor_id) VALUES (?, ?)', (patient_user_id, doctor_id))
            
        conn.commit()
        conn.close()
        return True, "Patient linked successfully!"
    except Exception as e:
        conn.rollback()
        return False, f"System error: {e}"
    finally:
        conn.close()

def get_patient_cycle_data_dict(patient_id):
    """
    Unified function to fetch and format cycle data for BOTH doctor and patient views.
    Ensures DRY logic across Data Visualizations.
    """
    conn = get_db_connection()
    cycles = conn.execute('''
        SELECT date(created_at) as c_date, time(created_at) as c_time, e2, f12, f18, estimated_mii, ohss_risk
        FROM cycles 
        WHERE patient_id = ?
        ORDER BY created_at ASC
    ''', (patient_id,)).fetchall()
    conn.close()
    
    if not cycles:
        return None
        
    return {
        'dates': [f"{row['c_date']} {row['c_time'][:5]}" for row in cycles],
        'e2': [row['e2'] for row in cycles],
        'f12': [row['f12'] for row in cycles],
        'f18': [row['f18'] for row in cycles],
        'mii': [row['estimated_mii'] for row in cycles],
        'latest_ohss': cycles[-1]['ohss_risk']
    }

# --- AUTH ROUTES ---

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        return redirect(url_for('patient_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        if not email or not password:
            flash('Email and password are required.', 'danger')
            return render_template('login.html')
            
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash('Logged in successfully.', 'success')
            if user['role'] == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            else:
                return redirect(url_for('patient_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'patient')
        doctor_code = request.form.get('doctor_code', '')
        
        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
            
        if role == 'doctor' and doctor_code != 'IVF123':
            flash('Invalid Doctor Access Code.', 'danger')
            return render_template('register.html')
            
        password_hash = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', (name, email, password_hash, role))
            
            user_id = cursor.lastrowid
            
            # Auto-create empty profiles
            if role == 'patient':
                cursor.execute('INSERT INTO patient_profiles (user_id) VALUES (?)', (user_id,))
            else:
                cursor.execute('INSERT INTO doctor_profiles (user_id) VALUES (?)', (user_id,))

            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.rollback()
            flash('Email already registered.', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# --- DOCTOR DASHBOARD ROUTES ---

@app.route('/doctor/dashboard')
@login_required
@doctor_only
def doctor_dashboard():
    doc_id = session.get('user_id')
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    
    # 1. Total Patients
    total_patients_row = conn.execute('SELECT COUNT(*) as cnt FROM patient_profiles WHERE doctor_id = ?', (doc_id,)).fetchone()
    total_patients = total_patients_row['cnt'] if total_patients_row else 0
    
    # 2. Today's Appointments with patient details
    appointments = conn.execute('''
        SELECT a.id, a.date, a.time, a.status, u.name as patient_name, u.email as patient_email
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.doctor_id = ? AND a.date = ?
        ORDER BY a.time ASC
    ''', (doc_id, today_str)).fetchall()
    
    # 3. Alerts (Unread only)
    alerts = conn.execute('''
        SELECT al.id, al.message, al.severity, al.created_at, u.name as patient_name
        FROM alerts al
        JOIN users u ON al.patient_id = u.id
        WHERE al.doctor_id = ? AND al.is_read = 0
        ORDER BY al.severity DESC, al.created_at DESC
    ''', (doc_id,)).fetchall()
    
    high_risk_count = sum(1 for alt in alerts if alt['severity'] == 'high')
    
    conn.close()
    
    return render_template(
        'doctor_dashboard.html', 
        name=session.get('name'),
        total_patients=total_patients,
        appointments=appointments,
        today_appointments_count=len(appointments),
        alerts=alerts,
        high_risk_count=high_risk_count
    )

@app.route('/doctor/patients', methods=['GET'])
@login_required
@doctor_only
def doctor_patients():
    doc_id = session.get('user_id')
    conn = get_db_connection()
    patients = conn.execute('''
        SELECT u.id as user_id, u.name, u.email, p.age, p.last_visit 
        FROM patient_profiles p
        JOIN users u ON p.user_id = u.id
        WHERE p.doctor_id = ?
        ORDER BY u.name ASC
    ''', (doc_id,)).fetchall()
    conn.close()
    
    return render_template('doctor_patients.html', patients=patients, name=session.get('name'))

@app.route('/doctor/add-patient', methods=['POST'])
@login_required
@doctor_only
def doctor_add_patient():
    email = request.form.get('email', '').strip()
    if not email:
        flash("Email is required.", 'danger')
        return redirect(url_for('doctor_patients'))
        
    doc_id = session.get('user_id')
    success, message = link_patient_to_doctor(doc_id, email)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'warning')
        
    return redirect(url_for('doctor_patients'))

# --- DOCTOR APPOINTMENTS & ALERTS ROUTES ---

@app.route('/doctor/appointments')
@login_required
@doctor_only
def doctor_appointments():
    doc_id = session.get('user_id')
    conn = get_db_connection()
    appointments = conn.execute('''
        SELECT a.id, a.date, a.time, a.status, a.notes, u.name as patient_name, u.email as patient_email
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.doctor_id = ?
        ORDER BY a.date ASC, a.time ASC
    ''', (doc_id,)).fetchall()
    conn.close()
    return render_template('doctor_appointments.html', appointments=appointments, name=session.get('name'))

@app.route('/doctor/alerts')
@login_required
@doctor_only
def doctor_alerts():
    doc_id = session.get('user_id')
    conn = get_db_connection()
    alerts = conn.execute('''
        SELECT al.id, al.message, al.severity, al.created_at, al.is_read, u.name as patient_name
        FROM alerts al
        JOIN users u ON al.patient_id = u.id
        WHERE al.doctor_id = ?
        ORDER BY al.created_at DESC
    ''', (doc_id,)).fetchall()
    conn.close()
    return render_template('doctor_alerts.html', alerts=alerts, name=session.get('name'))

# --- PHASE 4: APPOINTMENTS & PATIENT DASHBOARD ---

@app.route('/api/available-slots/<int:doctor_id>/<date>')
@login_required
def available_slots(doctor_id, date):
    # Standard slots 09:00 to 16:00
    all_slots = [
        "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
        "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00"
    ]
    conn = get_db_connection()
    # Fetch booked slots for the date where status active
    booked = conn.execute('''
        SELECT time FROM appointments
        WHERE doctor_id = ? AND date = ? AND status IN ('scheduled', 'rescheduled')
    ''', (doctor_id, date)).fetchall()
    conn.close()
    
    booked_times = [row['time'] for row in booked]
    free_slots = [slot for slot in all_slots if slot not in booked_times]
    
    return jsonify({'success': True, 'slots': free_slots})

@app.route('/patient/dashboard')
@login_required
@patient_only
def patient_dashboard():
    patient_id = session.get('user_id')
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    
    # Check if linked to a doctor
    profile = conn.execute('SELECT doctor_id FROM patient_profiles WHERE user_id = ?', (patient_id,)).fetchone()
    has_doctor = bool(profile and profile['doctor_id'])
    
    # Fetch upcoming appointments
    upcoming = conn.execute('''
        SELECT a.id, a.date, a.time, a.status, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND a.date >= ? AND a.status = 'scheduled'
        ORDER BY a.date ASC, a.time ASC
    ''', (patient_id, today_str)).fetchall()
    
    # Fetch past/completed appointments
    past = conn.execute('''
        SELECT a.id, a.date, a.time, a.status, u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ? AND (a.date < ? OR a.status != 'scheduled')
        ORDER BY a.date DESC, a.time DESC
    ''', (patient_id, today_str)).fetchall()
    
    conn.close()
    return render_template('patient_dashboard.html', name=session.get('name'), upcoming=upcoming, past=past, has_doctor=has_doctor)

@app.route('/patient/book-appointment', methods=['GET', 'POST'])
@login_required
@patient_only
def book_appointment():
    patient_id = session.get('user_id')
    conn = get_db_connection()
    
    # Verify doctor link natively
    profile = conn.execute('SELECT doctor_id FROM patient_profiles WHERE user_id = ?', (patient_id,)).fetchone()
    if not profile or not profile['doctor_id']:
        conn.close()
        flash("You must be linked to a clinic by a doctor before booking appointments.", "warning")
        return redirect(url_for('patient_dashboard'))
        
    doctor_id = profile['doctor_id']
    
    if request.method == 'POST':
        appt_date = request.form.get('date')
        appt_time = request.form.get('time')
        notes = request.form.get('notes', '')
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if not appt_date or not appt_time:
            flash("Date and Time are absolutely required.", "danger")
        elif appt_date < today_str:
            flash("Cannot book appointments in the past.", "danger")
        else:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO appointments (doctor_id, patient_id, date, time, status, notes)
                    VALUES (?, ?, ?, ?, 'scheduled', ?)
                ''', (doctor_id, patient_id, appt_date, appt_time, notes))
                conn.commit()
                flash("Appointment successfully scheduled!", "success")
                return redirect(url_for('patient_dashboard'))
            except sqlite3.IntegrityError:
                conn.rollback()
                flash("This time slot has already been booked. Please choose an available slot.", "warning")
            finally:
                conn.close()
                return redirect(url_for('book_appointment'))
                
    # Fetch doctor details for rendering
    doctor = conn.execute('SELECT id, name FROM users WHERE id = ?', (doctor_id,)).fetchone()
    conn.close()
    
    return render_template('book_appointment.html', name=session.get('name'), doctor_name=doctor['name'], doctor_id=doctor['id'])

@app.route('/doctor/appointment/<int:appt_id>/status', methods=['POST'])
@login_required
@doctor_only
def update_appointment_status(appt_id):
    doc_id = session.get('user_id')
    new_status = request.form.get('status')
    
    if new_status not in ['completed', 'cancelled']:
        flash('Invalid status operation natively rejected.', 'danger')
        return redirect(url_for('doctor_dashboard'))
        
    conn = get_db_connection()
    # Verify appointment belongs to this doctor
    appt = conn.execute('SELECT id, status FROM appointments WHERE id = ? AND doctor_id = ?', (appt_id, doc_id)).fetchone()
    
    if not appt:
        flash('Unauthorized access to appointment.', 'danger')
    elif appt['status'] in ['completed', 'cancelled']:
        flash('Cannot change status of a finalized appointment.', 'warning')
    else:
        conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (new_status, appt_id))
        conn.commit()
        flash('Appointment status updated securely.', 'success')
        
    conn.close()
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/appointment/<int:appt_id>/reschedule', methods=['GET', 'POST'])
@login_required
@doctor_only
def reschedule_appointment(appt_id):
    doc_id = session.get('user_id')
    conn = get_db_connection()
    
    # Verify appointment belongs to this doctor and isn't finalized
    appt = conn.execute('''
        SELECT a.id, a.date, a.time, a.status, u.name as patient_name
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.id = ? AND a.doctor_id = ?
    ''', (appt_id, doc_id)).fetchone()
    
    if not appt or appt['status'] in ['completed', 'cancelled']:
        conn.close()
        flash('Appointment not found or already finalized.', 'danger')
        return redirect(url_for('doctor_appointments'))
        
    if request.method == 'POST':
        new_date = request.form.get('date')
        new_time = request.form.get('time')
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if not new_date or not new_time:
            flash("Date and Time are required to reschedule.", "danger")
        elif new_date < today_str:
            flash("Cannot reschedule to a past date.", "danger")
        else:
            try:
                conn.execute('''
                    UPDATE appointments 
                    SET date = ?, time = ?, status = 'rescheduled'
                    WHERE id = ?
                ''', (new_date, new_time, appt_id))
                conn.commit()
                flash("Appointment successfully rescheduled!", "success")
                conn.close()
                return redirect(url_for('doctor_appointments'))
            except sqlite3.IntegrityError:
                conn.rollback()
                flash("This time slot is already booked. Please choose an available slot.", "warning")
                
    conn.close()
    return render_template('reschedule_appointment.html', appt=appt, name=session.get('name'))

# --- PHASE 3: ML INTEGRATION & PATIENT PROFILE ---

@app.route('/doctor/patient/<int:patient_id>')
@login_required
@doctor_only
def doctor_patient_profile(patient_id):
    doc_id = session.get('user_id')
    conn = get_db_connection()
    
    # Verify patient belongs to logged in doctor
    patient = conn.execute('''
        SELECT u.id, u.name, u.email, p.age, p.bmi, p.amh, p.afc, p.last_visit 
        FROM users u
        JOIN patient_profiles p ON u.id = p.user_id
        WHERE u.id = ? AND p.doctor_id = ? AND u.role = 'patient'
    ''', (patient_id, doc_id)).fetchone()
    
    if not patient:
        conn.close()
        flash('Patient not found or unauthorized access.', 'danger')
        return redirect(url_for('doctor_patients'))
        
    # Fetch history limit for preview purposes on main dash if needed, but per requirements 
    # we just need to pass the patient profile for the prediction form
    conn.close()
    return render_template('doctor_patient_profile.html', patient=patient)

@app.route('/doctor/patient/<int:patient_id>/profile', methods=['GET', 'POST'])
@login_required
@doctor_only
def doctor_patient_profile_edit(patient_id):
    doc_id = session.get('user_id')
    conn = get_db_connection()
    
    # Verify patient belongs to logged in doctor
    patient = conn.execute('''
        SELECT u.id, u.name, u.email, p.age, p.bmi, p.amh, p.afc, p.last_visit 
        FROM users u
        JOIN patient_profiles p ON u.id = p.user_id
        WHERE u.id = ? AND p.doctor_id = ? AND u.role = 'patient'
    ''', (patient_id, doc_id)).fetchone()
    
    if not patient:
        conn.close()
        flash('Patient not found.', 'danger')
        return redirect(url_for('doctor_patients'))
        
    if request.method == 'POST':
        try:
            age = float(request.form.get('age', 0))
            bmi = float(request.form.get('bmi', 0))
            amh = float(request.form.get('amh', 0))
            afc = int(request.form.get('afc', 0))
            
            # Validation
            if age <= 0: flash("Age must be greater than 0.", "danger")
            elif bmi < 10 or bmi > 60: flash("BMI must be between 10 and 60.", "danger")
            elif amh < 0: flash("AMH cannot be negative.", "danger")
            elif afc < 0: flash("AFC cannot be negative.", "danger")
            else:
                conn.execute('''
                    UPDATE patient_profiles 
                    SET age = ?, bmi = ?, amh = ?, afc = ? 
                    WHERE user_id = ? AND doctor_id = ?
                ''', (age, bmi, amh, afc, patient_id, doc_id))
                conn.commit()
                flash('Baseline profile updated safely.', 'success')
                conn.close()
                return redirect(url_for('doctor_patient_profile', patient_id=patient_id))
        except ValueError:
            flash("Invalid numerical input format. Please try again.", "danger")
            
    conn.close()
    return render_template('doctor_patient_profile_edit.html', patient=patient)

@app.route('/doctor/patient/<int:patient_id>/history')
@login_required
@doctor_only
def doctor_patient_history(patient_id):
    doc_id = session.get('user_id')
    conn = get_db_connection()
    
    # Verify patient belongs to logged in doctor
    patient = conn.execute('''
        SELECT u.id, u.name, u.email FROM users u
        JOIN patient_profiles p ON u.id = p.user_id
        WHERE u.id = ? AND p.doctor_id = ? AND u.role = 'patient'
    ''', (patient_id, doc_id)).fetchone()
    
    if not patient:
        conn.close()
        flash('Patient not found.', 'danger')
        return redirect(url_for('doctor_patients'))
        
    # Natively fetch the cycle rows strictly sorted ascending for History UX
    cycles = conn.execute('''
        SELECT c.* 
        FROM cycles c
        WHERE c.patient_id = ? AND c.doctor_id = ?
        ORDER BY c.created_at ASC
    ''', (patient_id, doc_id)).fetchall()
    
    conn.close()
    return render_template('doctor_patient_history.html', patient=patient, cycles=cycles)

@app.route('/patient/<int:patient_id>/cycle-data')
@login_required
@doctor_only
def get_cycle_data(patient_id):
    doc_id = session.get('user_id')
    conn = get_db_connection()
    
    patient_check = conn.execute('SELECT id FROM patient_profiles WHERE user_id = ? AND doctor_id = ?', (patient_id, doc_id)).fetchone()
    conn.close()
    
    if not patient_check:
        return jsonify({'success': False, 'error': 'Unauthorized'})
        
    data = get_patient_cycle_data_dict(patient_id)
    if not data:
        return jsonify({'success': True, 'data': {'dates': []}})
    
    return jsonify({'success': True, 'data': data})

@app.route('/predict', methods=['POST'])
@login_required
@doctor_only
def predict():
    data = request.json
    doc_id = session.get('user_id')
    patient_id = data.get('patient_id')
    
    # 1. Validation check
    if not patient_id:
        return jsonify({'success': False, 'error': 'Missing patient ID'})
        
    required_fields = ['age', 'bmi', 'amh', 'afc', 'protocol', 'gon', 'stim_days', 'f12', 'f18', 'f22', 'lead_follicle', 'e2', 'e2_prev', 'lh', 'growth']
    
    for f in required_fields:
        if f not in data or data[f] == '' or data[f] is None:
            return jsonify({'success': False, 'error': f'Missing required clinical input field: {f}. Inference strictly requires completeness.'})
            
    # 2. Authorization check
    conn = get_db_connection()
    patient_check = conn.execute('SELECT id FROM patient_profiles WHERE user_id = ? AND doctor_id = ?', (patient_id, doc_id)).fetchone()
    if not patient_check:
        conn.close()
        return jsonify({'success': False, 'error': 'Unauthorized workflow. Patient is not assigned to you.'})
        
    # 3. ML Inference execution
    try:
        prediction_result = run_prediction(data)
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': f'ML Engine runtime exception: {str(e)}'})

    # 4. Save to cycles natively
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cycles (
                doctor_id, patient_id, 
                age, bmi, amh, afc, protocol, gon, stim_days, 
                f12, f18, f22, lead_follicle, e2, e2_prev, lh, growth,
                predicted_trigger, confidence, ohss_risk, estimated_mii
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id, patient_id,
            float(data['age']), float(data['bmi']), float(data['amh']), float(data['afc']),
            str(data['protocol']), float(data['gon']), float(data['stim_days']),
            float(data['f12']), float(data['f18']), float(data['f22']), float(data['lead_follicle']),
            float(data['e2']), float(data['e2_prev']), float(data['lh']), float(data['growth']),
            prediction_result['trigger'], prediction_result['confidence'],
            prediction_result['ohss'], prediction_result['mii']
        ))
        
        # 5. Alert Trigger conditions
        if prediction_result['ohss'].lower() in ['high', 'yes'] or 'poor' in prediction_result['trigger'].lower():
            message = "High OHSS risk isolated natively via ML simulation engine." if prediction_result['ohss'].lower() in ['high', 'yes'] else "Poor response dynamically predicted. Review stimulation parameters."
            severity = "high"
            cursor.execute('''
                INSERT INTO alerts (doctor_id, patient_id, message, severity)
                VALUES (?, ?, ?, ?)
            ''', (doc_id, patient_id, message, severity))
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': f'Database logic exception: {str(e)}'})
    finally:
        conn.close()
        
    return jsonify({
        'success': True,
        'results': prediction_result
    })

@app.route('/simulate', methods=['POST'])
@login_required
@doctor_only
def simulate():
    data = request.json
    patient_id = data.get('patient_id')
    
    if not patient_id:
        return jsonify({'success': False, 'error': 'Missing patient ID'})
        
    conn = get_db_connection()
    # Find last baseline
    last_cycle = conn.execute('''
        SELECT age, bmi, amh, afc, protocol, gon, stim_days, f12, f18, f22, lead_follicle, e2, e2_prev, lh, growth, ohss_risk, predicted_trigger
        FROM cycles WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1
    ''', (patient_id,)).fetchone()
    conn.close()
    
    base_data = dict(last_cycle) if last_cycle else {}
    simulated_data = {**base_data}
    
    # Merge modified inputs
    for key, val in data.items():
        if val is not None and str(val).strip() != '':
            simulated_data[key] = val
            
    # Validation
    try:
        e2_val = float(simulated_data.get('e2', 0))
        f18_val = float(simulated_data.get('f18', 0))
        f12_val = float(simulated_data.get('f12', 0))
        if e2_val <= 0:
            return jsonify({'success': False, 'error': 'E2 must be greater than 0.'})
        if f18_val < 0 or f12_val < 0:
            return jsonify({'success': False, 'error': 'Follicle counts cannot be negative.'})
    except ValueError:
        return jsonify({'success': False, 'error': 'Simulation inputs must be valid numbers.'})

    required_fields = ['age', 'bmi', 'amh', 'afc', 'protocol', 'gon', 'stim_days', 'f12', 'f18', 'f22', 'lead_follicle', 'e2', 'e2_prev', 'lh', 'growth']
    for f in required_fields:
        if f not in simulated_data or str(simulated_data[f]).strip() == '':
             return jsonify({'success': False, 'error': f'Missing baseline data for {f}.'})
             
    try:
        sim_result = run_prediction(simulated_data)
        orig_result = None
        if base_data:
            # Re-predicting on base data establishes deterministic local compare baseline if required
            orig_result = run_prediction(base_data)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Simulation exception: {str(e)}'})
        
    return jsonify({
        'success': True,
        'simulated': sim_result,
        'original': orig_result
    })

@app.route('/patient/my-cycle')
@login_required
@patient_only
def patient_my_cycle():
    patient_id = session.get('user_id')
    
    data = get_patient_cycle_data_dict(patient_id)
    
    if not data:
        return render_template('patient_cycle.html', has_data=False, name=session.get('name'))
    
    latest_ohss = data['latest_ohss']
    safe_status = "On Track"
    status_color = "success"
    if latest_ohss.lower() == 'moderate':
        safe_status = "Needs Monitoring"
        status_color = "warning"
    elif latest_ohss.lower() in ['high', 'yes']:
         safe_status = "Extra Care Recommended"
         status_color = "danger"
         
    return render_template('patient_cycle.html', has_data=True, data=data, safe_status=safe_status, status_color=status_color, name=session.get('name'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)
