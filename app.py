import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user, login_manager
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURATION DE PRODUCTION / LOCALE ---

# 1. Gestion de la Clé Secrète
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-a-changer-en-local')

# 2. Gestion de la Base de Données (Postgres sur Render, SQLite en local)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///generation.db')

# Petit fix indispensable pour SQLAlchemy et Render
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()
    print("Base de données initialisée (Tables créées) !")

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

    # AJOUT : Relation pour accéder directement à l'objet User du senior
    senior = db.relationship('User', foreign_keys=[senior_id])


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

@app.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('profile.html', user=user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.bio = request.form['bio']
        db.session.commit()
        flash("Profil mis à jour avec succès !", "success")
        return redirect(url_for('dashboard'))
    return render_template('edit_profile.html')

@app.route('/api/bookings', methods=['POST'])
@login_required
def create_booking_api():
    # Le paramètre silent=True empêche l'erreur 415 si ce n'est pas du JSON
    data = request.get_json(silent=True) or request.form

    slot_id = data.get('availability_id')
    if not slot_id:
        return jsonify({"error": "ID de créneau manquant"}), 400

    slot = Availability.query.get_or_404(slot_id)

    if slot.is_booked:
        if request.is_json:
            return jsonify({"error": "Déjà réservé"}), 400
        flash("Ce créneau est déjà réservé.", "danger")
        return redirect(url_for('dashboard'))

    # Création de la réservation
    booking = Booking(availability_id=slot.id, senior_id=current_user.id)
    slot.is_booked = True
    db.session.add(booking)
    db.session.commit()

    # Notification simulée
    youth = User.query.get(slot.youth_id)
    notify_user(youth.email, f"Bonjour {youth.name}, le senior {current_user.name} a réservé votre créneau.")

    # Gestion de la réponse selon la source (API vs Formulaire)
    if request.is_json:
        return jsonify({"message": "Réservation confirmée"}), 201

    flash("Réservation confirmée avec succès !", "success")
    return redirect(url_for('dashboard'))


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