import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-a-changer-en-local')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///generation.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# --- MODÈLES ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)
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
    description = db.Column(db.Text, nullable=True)  # AJOUT : Note facultative
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    senior = db.relationship('User', foreign_keys=[senior_id])


# --- INITIALISATION DE LA BASE ---
with app.app_context():
    try:
        db.create_all()
        print("🚀 Base de données synchronisée avec succès.")
    except Exception as e:
        print(f"❌ Erreur initialisation : {e}")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- ROUTES API ---

@app.route('/api/bookings', methods=['POST'])
@login_required
def create_booking_api():
    data = request.get_json(silent=True) or request.form
    slot_id = data.get('availability_id')
    booking_desc = data.get('description', '')  # Récupération de la description

    slot = Availability.query.get_or_404(slot_id)
    if slot.is_booked:
        if request.is_json: return jsonify({"error": "Déjà réservé"}), 400
        flash("Ce créneau est déjà pris.", "danger")
        return redirect(url_for('dashboard'))

    # Création avec la description
    booking = Booking(
        availability_id=slot.id,
        senior_id=current_user.id,
        description=booking_desc
    )
    slot.is_booked = True
    db.session.add(booking)
    db.session.commit()

    flash("Réservation confirmée !", "success")
    return redirect(url_for('dashboard'))


# --- ROUTES PAGES (STUB) ---
@app.route('/')
def index(): return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Identifiants incorrects", "danger")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(
            name=request.form['name'], email=request.form['email'],
            password_hash=hashed_pw, role=request.form['role'], bio=request.form['bio']
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


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
    return redirect(url_for('dashboard'))


@app.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('profile.html', user=user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)