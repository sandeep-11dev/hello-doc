from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_socketio import SocketIO, join_room, leave_room, emit
import random, os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///doctor_appointment.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SMTP configuration (update with your credentials)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'subrahmanyag79@gmail.com'
app.config['MAIL_PASSWORD'] = 'utwltqbrqsjibwqx'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

db = SQLAlchemy(app)
mail = Mail(app)
socketio = SocketIO(app)

# --------------------
# Database Models
# --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    verified = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6))

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    specialty = db.Column(db.String(150))
    portfolio = db.Column(db.Text)
    rating = db.Column(db.Float, default=0)
    num_ratings = db.Column(db.Integer, default=0)
    otp = db.Column(db.String(6))
    verified = db.Column(db.Boolean, default=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'))
    appointment_type = db.Column(db.String(50))  # 'online' or 'offline'
    scheduled_time = db.Column(db.DateTime)
    paid = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default="pending")  # "pending", "accepted", "rejected"
    video_call_status = db.Column(db.String(50), default="none")  # "none", "requested", "accepted"

# New model for direct video call requests (without appointment)
class DirectCall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer)  # patient or doctor ID who initiates the call
    receiver_id = db.Column(db.Integer)   # target user ID
    requester_type = db.Column(db.String(20))  # 'patient' or 'doctor'
    status = db.Column(db.String(20), default="pending")  # "pending", "accepted", "rejected"
    room = db.Column(db.String(100))  # video call room name
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class CommunityPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)  # can be patient or doctor
    user_type = db.Column(db.String(20))  # 'patient' or 'doctor'
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'))
    rating = db.Column(db.Integer)  # 1 to 5
    comment = db.Column(db.Text)

# --------------------
# Routes
# --------------------

@app.route('/')
def home():
    return render_template('home.html')

# Patient Registration with OTP
@app.route('/register_patient', methods=['GET', 'POST'])
def register_patient():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different email or login.', 'danger')
            return redirect(url_for('register_patient'))
        otp = str(random.randint(100000, 999999))
        user = User(name=name, email=email, password=password, otp=otp)
        db.session.add(user)
        db.session.commit()
        msg = Message('Your OTP Verification Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f"Your OTP is: {otp}"
        mail.send(msg)
        flash('OTP sent to your email. Please verify your account.', 'info')
        session['user_email'] = email
        return redirect(url_for('verify_otp'))
    return render_template('register_patient.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('register_patient'))
    user = User.query.filter_by(email=email).first()
    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == user.otp:
            user.verified = True
            db.session.commit()
            flash('Your account has been verified!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
    return render_template('verify_otp.html', email=email)

# Doctor Registration with OTP
@app.route('/register_doctor', methods=['GET', 'POST'])
def register_doctor():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        specialty = request.form['specialty']
        portfolio = request.form['portfolio']
        if Doctor.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different email or login.', 'danger')
            return redirect(url_for('register_doctor'))
        otp = str(random.randint(100000, 999999))
        doctor = Doctor(name=name, email=email, password=password,
                        specialty=specialty, portfolio=portfolio, otp=otp)
        db.session.add(doctor)
        db.session.commit()
        msg = Message('Your Doctor OTP Verification Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f"Your OTP is: {otp}"
        mail.send(msg)
        flash('OTP sent to your email. Please verify your account.', 'info')
        session['doctor_email'] = email
        return redirect(url_for('verify_doctor_otp'))
    return render_template('register_doctor.html')

@app.route('/verify_doctor_otp', methods=['GET', 'POST'])
def verify_doctor_otp():
    email = session.get('doctor_email')
    if not email:
        return redirect(url_for('register_doctor'))
    doctor = Doctor.query.filter_by(email=email).first()
    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == doctor.otp:
            doctor.verified = True
            db.session.commit()
            flash('Your doctor account has been verified!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
    return render_template('verify_doctor_otp.html', email=email)

# Login and Logout
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        doctor = Doctor.query.filter_by(email=email, password=password).first()
        if user and user.verified:
            session['user_id'] = user.id
            session['user_type'] = 'patient'
            flash('Logged in as patient.', 'success')
            return redirect(url_for('dashboard'))
        elif doctor and doctor.verified:
            session['user_id'] = doctor.id
            session['user_type'] = 'doctor'
            flash('Logged in as doctor.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials or account not verified.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))

# Dashboard – shows different data based on user type
@app.route('/dashboard')
def dashboard():
    user_type = session.get('user_type')
    if user_type == 'patient':
        doctors = Doctor.query.all()
        appointments = Appointment.query.filter_by(user_id=session.get('user_id')).all()
        return render_template('dashboard.html', doctors=doctors, appointments=appointments)
    elif user_type == 'doctor':
        doctor = Doctor.query.get(session.get('user_id'))
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
        return render_template('doctor_dashboard.html', doctor=doctor, appointments=appointments)
    else:
        return redirect(url_for('login'))

# My Video Calls page – lists appointment-based video calls
@app.route('/my_video_calls')
def my_video_calls():
    if 'user_id' not in session:
        flash('Please login to access video calls.', 'danger')
        return redirect(url_for('login'))
    user_type = session.get('user_type')
    if user_type == 'patient':
        calls = Appointment.query.filter_by(user_id=session.get('user_id'),
                                            appointment_type='online',
                                            status='accepted',
                                            video_call_status='accepted').all()
    elif user_type == 'doctor':
        calls = Appointment.query.filter_by(doctor_id=session.get('user_id'),
                                            appointment_type='online',
                                            status='accepted',
                                            video_call_status='accepted').all()
    else:
        calls = []
    return render_template('my_video_calls.html', calls=calls)

# Community route
@app.route('/community', methods=['GET', 'POST'])
def community():
    if 'user_id' not in session:
        flash('Please login to access the community.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form['content']
        user_type = session.get('user_type')
        post = CommunityPost(user_id=session.get('user_id'), user_type=user_type, content=content)
        db.session.add(post)
        db.session.commit()
        flash('Post added successfully!', 'success')
    posts = CommunityPost.query.order_by(CommunityPost.timestamp.desc()).all()
    return render_template('community.html', posts=posts)

# Search route
@app.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    query = ""
    if request.method == 'POST':
        query = request.form['query'].lower()
        doctors = Doctor.query.all()
        for doc in doctors:
            if query in doc.specialty.lower() or query in doc.portfolio.lower() or query in doc.name.lower():
                results.append(doc)
    return render_template('search.html', results=results, query=query)

# Doctor profile route
@app.route('/doctor/<int:doctor_id>')
def doctor_profile(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    ratings = Rating.query.filter_by(doctor_id=doctor_id).all()
    return render_template('doctor_profile.html', doctor=doctor, ratings=ratings)

# Appointment booking by patient
@app.route('/appointment/<int:doctor_id>', methods=['GET', 'POST'])
def appointment(doctor_id):
    if 'user_id' not in session or session.get('user_type') != 'patient':
        flash('Please login as a patient to book an appointment.', 'danger')
        return redirect(url_for('login'))
    doctor = Doctor.query.get(doctor_id)
    if request.method == 'POST':
        appointment_type = request.form['appointment_type']
        scheduled_time = request.form['scheduled_time']
        paid = False
        if appointment_type == 'online':
            paid = request.form.get('paid') == 'true'
            if not paid:
                flash('Please complete prepayment for online consultation.', 'danger')
                return redirect(url_for('payment', doctor_id=doctor_id))
        appointment = Appointment(
            user_id=session.get('user_id'),
            doctor_id=doctor_id,
            appointment_type=appointment_type,
            scheduled_time=datetime.strptime(scheduled_time, '%Y-%m-%dT%H:%M'),
            paid=paid,
            status="pending",
            video_call_status="none"
        )
        db.session.add(appointment)
        db.session.commit()
        flash('Appointment booked successfully! Waiting for doctor confirmation.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('appointment.html', doctor=doctor)

# Payment simulation route
@app.route('/payment/<int:doctor_id>', methods=['GET', 'POST'])
def payment(doctor_id):
    if request.method == 'POST':
        flash('Payment successful. You can now book your online consultation.', 'success')
        return redirect(url_for('appointment', doctor_id=doctor_id))
    return render_template('payment.html', doctor_id=doctor_id)

# Doctor accepts appointment request
@app.route('/accept_appointment/<int:appointment_id>', methods=['POST'])
def accept_appointment(appointment_id):
    if 'user_id' not in session or session.get('user_type') != 'doctor':
        flash('Please login as a doctor to perform this action.', 'danger')
        return redirect(url_for('login'))
    appointment = Appointment.query.get(appointment_id)
    if appointment.doctor_id != session.get('user_id'):
        flash('Not authorized.', 'danger')
        return redirect(url_for('dashboard'))
    appointment.status = "accepted"
    db.session.commit()
    flash('Appointment accepted.', 'success')
    return redirect(url_for('dashboard'))

# Doctor rejects appointment request
@app.route('/reject_appointment/<int:appointment_id>', methods=['POST'])
def reject_appointment(appointment_id):
    if 'user_id' not in session or session.get('user_type') != 'doctor':
        flash('Please login as a doctor to perform this action.', 'danger')
        return redirect(url_for('login'))
    appointment = Appointment.query.get(appointment_id)
    if appointment.doctor_id != session.get('user_id'):
        flash('Not authorized.', 'danger')
        return redirect(url_for('dashboard'))
    appointment.status = "rejected"
    db.session.commit()
    flash('Appointment rejected.', 'success')
    return redirect(url_for('dashboard'))

# Doctor requests video call for an accepted appointment
@app.route('/request_videocall/<int:appointment_id>', methods=['POST'])
def request_videocall(appointment_id):
    if 'user_id' not in session or session.get('user_type') != 'doctor':
        flash('Please login as a doctor to perform this action.', 'danger')
        return redirect(url_for('login'))
    appointment = Appointment.query.get(appointment_id)
    if appointment.doctor_id != session.get('user_id'):
        flash('Not authorized.', 'danger')
        return redirect(url_for('dashboard'))
    if appointment.status != "accepted":
        flash('Appointment must be accepted first.', 'danger')
        return redirect(url_for('dashboard'))
    appointment.video_call_status = "requested"
    db.session.commit()
    flash('Video call request sent to patient.', 'success')
    return redirect(url_for('dashboard'))

# Patient accepts video call request (for appointment-based calls)
@app.route('/accept_videocall/<int:appointment_id>', methods=['POST'])
def accept_videocall(appointment_id):
    if 'user_id' not in session or session.get('user_type') != 'patient':
        flash('Please login as a patient to perform this action.', 'danger')
        return redirect(url_for('login'))
    appointment = Appointment.query.get(appointment_id)
    if appointment.user_id != session.get('user_id'):
        flash('Not authorized.', 'danger')
        return redirect(url_for('dashboard'))
    if appointment.video_call_status != "requested":
        flash('No video call request pending.', 'danger')
        return redirect(url_for('dashboard'))
    appointment.video_call_status = "accepted"
    db.session.commit()
    flash('Video call accepted. You can now join the call.', 'success')
    return redirect(url_for('dashboard'))

# Video call page for appointment-based calls (uses same template as direct calls)
@app.route('/video_call/<int:appointment_id>')
def video_call(appointment_id):
    appointment = Appointment.query.get(appointment_id)
    if appointment.appointment_type != 'online' or appointment.status != "accepted" or appointment.video_call_status != "accepted":
        flash('Video call cannot be started. Please ensure appointment is accepted and video call request is accepted.', 'danger')
        return redirect(url_for('dashboard'))
    # Use appointment id to generate a room name (or store room name in appointment if needed)
    room = f"appointment_{appointment.id}"
    return render_template('video_call.html', appointment=appointment, room=room)

# ----------------------------
# Direct Video Call Routes
# ----------------------------

# Patient requests a direct video call to a doctor (without appointment)
@app.route('/direct_call/request_to_doctor', methods=['GET', 'POST'])
def direct_call_request_to_doctor():
    if 'user_id' not in session or session.get('user_type') != 'patient':
        flash('Please login as a patient to request a direct video call.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        # Generate a random room name for the call
        room = f"direct_{random.randint(100000, 999999)}"
        direct_call = DirectCall(
            requester_id=session.get('user_id'),
            receiver_id=doctor_id,
            requester_type='patient',
            status='pending',
            room=room
        )
        db.session.add(direct_call)
        db.session.commit()
        flash('Direct video call request sent to doctor.', 'success')
        return redirect(url_for('direct_calls'))
    # GET: show list of available doctors
    doctors = Doctor.query.all()
    return render_template('direct_call_request_to_doctor.html', doctors=doctors)

# Doctor requests a direct video call to a patient (without appointment)
@app.route('/direct_call/request_to_patient', methods=['GET', 'POST'])
def direct_call_request_to_patient():
    if 'user_id' not in session or session.get('user_type') != 'doctor':
        flash('Please login as a doctor to request a direct video call.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        patient_id = request.form['patient_id']
        room = f"direct_{random.randint(100000, 999999)}"
        direct_call = DirectCall(
            requester_id=session.get('user_id'),
            receiver_id=patient_id,
            requester_type='doctor',
            status='pending',
            room=room
        )
        db.session.add(direct_call)
        db.session.commit()
        flash('Direct video call request sent to patient.', 'success')
        return redirect(url_for('direct_calls'))
    # GET: show list of available patients (all users)
    patients = User.query.all()
    return render_template('direct_call_request_to_patient.html', patients=patients)

# List all direct call requests (incoming and outgoing) for the logged-in user
@app.route('/direct_calls')
def direct_calls():
    if 'user_id' not in session:
        flash('Please login to view direct calls.', 'danger')
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    # For incoming requests, where receiver_id equals current user id.
    incoming = DirectCall.query.filter_by(receiver_id=user_id).all()
    # For outgoing requests, where requester_id equals current user id.
    outgoing = DirectCall.query.filter_by(requester_id=user_id).all()
    return render_template('direct_calls.html', incoming=incoming, outgoing=outgoing)

# Receiver accepts a direct call request
@app.route('/direct_call/accept/<int:call_id>', methods=['POST'])
def direct_call_accept(call_id):
    if 'user_id' not in session:
        flash('Please login to perform this action.', 'danger')
        return redirect(url_for('login'))
    direct_call = DirectCall.query.get(call_id)
    if direct_call.receiver_id != session.get('user_id'):
        flash('Not authorized to accept this call.', 'danger')
        return redirect(url_for('direct_calls'))
    direct_call.status = "accepted"
    db.session.commit()
    flash('Direct video call request accepted.', 'success')
    return redirect(url_for('direct_calls'))

# Direct video call page (for direct call requests)
@app.route('/direct_call/<int:call_id>')
def direct_call(call_id):
    direct_call = DirectCall.query.get(call_id)
    if direct_call.status != "accepted":
        flash('Direct call not accepted yet.', 'danger')
        return redirect(url_for('direct_calls'))
    return render_template('video_call.html', appointment=direct_call, room=direct_call.room)

# ----------------------------
# Socket.IO Events (for video signaling)
# ----------------------------
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    emit('message', {'msg': f"{data.get('username', 'User')} has entered the room."}, room=room)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    emit('message', {'msg': f"{data.get('username', 'User')} has left the room."}, room=room)

@socketio.on('message')
def handle_message(data):
    room = data.get('room')
    emit('message', data, room=room)

# ----------------------------
# Main
# ----------------------------
if __name__ == '__main__':
    if not os.path.exists('doctor_appointment.db'):
        with app.app_context():
            db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

