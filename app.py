import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'generation_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///generation.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- MODÈLES ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'senior' or 'jeune'
    bio = db.Column(db.Text, nullable=True)
    availabilities = db.relationship('Availability', backref='youth', lazy=True)


class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    youth_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    is_booked = db.Column(db.Boolean, default=False)
    booking = db.relationship('Booking', backref='slot', uselist=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    availability_id = db.Column(db.Integer, db.ForeignKey('availability.id'), nullable=False)
    senior_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- OUTILS ---

def notify_user(user_email, message):
    """Simulation d'envoi d'email via console"""
    print(f"\n[NOTIFICATION EMAIL envoyé à {user_email}]")
    print(f"Message: {message}")
    print("-" * 30)


# --- ROUTES API (JSON) ---

@app.route('/api/availabilities', methods=['GET'])
def get_availabilities():
    slots = Availability.query.filter_by(is_booked=False).all()
    return jsonify([{
        "id": s.id,
        "youth": User.query.get(s.youth_id).name,
        "start_time": s.start_time.strftime("%Y-%m-%d %H:%M")
    } for s in slots])


@app.route('/api/bookings', methods=['POST'])
@login_required
def create_booking_api():
    data = request.get_json() or request.form
    slot_id = data.get('availability_id')
    slot = Availability.query.get_or_404(slot_id)

    if slot.is_booked:
        return jsonify({"error": "Déjà réservé"}), 400

    booking = Booking(availability_id=slot.id, senior_id=current_user.id)
    slot.is_booked = True
    db.session.add(booking)
    db.session.commit()

    # Notification simulée
    youth = User.query.get(slot.youth_id)
    notify_user(youth.email,
                f"Bonjour {youth.name}, le senior {current_user.name} a réservé votre créneau du {slot.start_time}.")

    return jsonify({"message": "Réservation confirmée"}), 201


# --- ROUTES FRONTEND ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(
            name=request.form['name'],
            email=request.form['email'],
            password_hash=hashed_pw,
            role=request.form['role'],
            bio=request.form['bio']
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Compte créé avec succès !", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Email ou mot de passe incorrect", "danger")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'jeune':
        my_slots = Availability.query.filter_by(youth_id=current_user.id).all()
        return render_template('dashboard_jeune.html', slots=my_slots)
    else:
        available_slots = Availability.query.filter_by(is_booked=False).all()
        my_bookings = Booking.query.filter_by(senior_id=current_user.id).all()
        return render_template('dashboard_senior.html', available_slots=available_slots, my_bookings=my_bookings)


@app.route('/add_availability', methods=['POST'])
@login_required
def add_availability():
    if current_user.role == 'jeune':
        dt = datetime.strptime(request.form['datetime'], '%Y-%m-%dT%H:%M')
        new_slot = Availability(youth_id=current_user.id, start_time=dt)
        db.session.add(new_slot)
        db.session.commit()
        flash("Disponibilité ajoutée !", "success")
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)