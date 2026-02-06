import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

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
    # On garde le champ password_hash pour la compatibilité, mais il devient optionnel
    password_hash = db.Column(db.String(200), nullable=True)
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
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    senior = db.relationship('User', foreign_keys=[senior_id])


# --- INITIALISATION DE LA BASE ---
with app.app_context():
    try:
        db.create_all()
        if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI']:
            try:
                db.session.execute(text('ALTER TABLE booking ADD COLUMN IF NOT EXISTS description TEXT'))
                # Migration pour rendre le mot de passe optionnel si nécessaire
                db.session.execute(text('ALTER TABLE user ALTER COLUMN password_hash DROP NOT NULL'))
                db.session.commit()
            except Exception:
                db.session.rollback()
        print("🚀 Base de données synchronisée.")
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
    booking_desc = data.get('description', '')

    slot = Availability.query.get_or_404(slot_id)
    if slot.is_booked:
        if request.is_json: return jsonify({"error": "Déjà réservé"}), 400
        flash("Ce créneau est déjà réservé.", "danger")
        return redirect(url_for('dashboard'))

    booking = Booking(availability_id=slot.id, senior_id=current_user.id, description=booking_desc)
    slot.is_booked = True
    db.session.add(booking)
    db.session.commit()

    if request.is_json:
        return jsonify({"status": "success", "message": "Réservation confirmée"})

    flash("Réservation confirmée !", "success")
    return redirect(url_for('dashboard'))


@app.route('/api/availabilities', methods=['GET'])
def get_availabilities():
    slots = Availability.query.filter_by(is_booked=False).all()
    return jsonify([{
        "id": s.id,
        "youth": User.query.get(s.youth_id).name,
        "start_time": s.start_time.strftime("%Y-%m-%d %H:%M")
    } for s in slots])


@app.route('/api/profile/<int:user_id>', methods=['GET'])
@login_required
def get_profile_api(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "bio": user.bio
    })


# --- ROUTES PAGES ---

@app.route('/')
def index(): return render_template('index.html')


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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Le mot de passe n'est plus requis, on met une valeur par défaut ou vide
        new_user = User(
            name=request.form['name'],
            email=request.form['email'],
            password_hash=None,  # Plus besoin de hash
            role=request.form['role'],
            bio=request.form['bio']
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    AUTHENTIFICATION SIMPLIFIÉE :
    L'utilisateur se connecte uniquement avec son adresse email.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            login_user(user)
            return redirect(url_for('dashboard'))

        flash("Aucun compte trouvé avec cet email", "danger")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    user = User.query.get_or_404(user_id)

    if (request.headers.get('Accept') == 'application/json' or
            request.args.get('format') == 'json' or
            request.is_json):
        return jsonify({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "bio": user.bio
        })

    return render_template('profile.html', user=user)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.bio = request.form['bio']
        db.session.commit()
        flash("Profil mis à jour", "success")
        return redirect(url_for('dashboard'))
    return render_template('edit_profile.html')


@app.route('/add_availability', methods=['POST'])
@login_required
def add_availability():
    if current_user.role == 'jeune':
        dt = datetime.strptime(request.form['datetime'], '%Y-%m-%dT%H:%M')
        new_slot = Availability(youth_id=current_user.id, start_time=dt)
        db.session.add(new_slot)
        db.session.commit()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)