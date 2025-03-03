from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os
from enum import Enum
from datetime import datetime
import pytz
from PIL import Image
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy import Boolean

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for sessions and flash messages

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configuration
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

class UserType(Enum):
    STUDENT = 'student'
    DESIGNATED = 'designated'
    ADMIN = 'admin'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.Enum(UserType), nullable=False)
    iit = db.Column(db.String(50), nullable=False)
    branch = db.Column(db.String(50))
    year = db.Column(db.String(20))
    designation = db.Column(db.String(100))
    verification_mobile = db.Column(db.String(15))
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile_picture = db.Column(db.String(255), default='default_profile.png')

    def __repr__(self):
        return f'<User {self.email}>'

class ApprovalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('approval_request', uselist=False))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ApprovalRequest {self.user.email}>'

class Bulletin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('bulletins', lazy=True))
    upvotes = db.relationship('Upvote', backref='bulletin', lazy='dynamic', cascade='all, delete-orphan')
    visibility = db.Column(JSON, default=lambda: {"all": True, "specific_iits": []})

    def __repr__(self):
        return f'<Bulletin {self.title}>'

    @property
    def created_at_ist(self):
        utc_time = self.created_at.replace(tzinfo=pytz.UTC)
        ist_time = utc_time.astimezone(pytz.timezone('Asia/Kolkata'))
        return ist_time

class Upvote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bulletin_id = db.Column(db.Integer, db.ForeignKey('bulletin.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Upvote {self.user_id} - {self.bulletin_id}>'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('signin'))
        user = User.query.get(session['user_id'])
        if user.user_type != UserType.ADMIN:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def crop_and_resize_image(file_path, size=(150, 150)):
    with Image.open(file_path) as img:
        # Calculate dimensions to crop image to a square
        width, height = img.size
        new_size = min(width, height)
        left = (width - new_size) / 2
        top = (height - new_size) / 2
        right = (width + new_size) / 2
        bottom = (height + new_size) / 2

        # Crop and resize
        img = img.crop((left, top, right, bottom))
        img = img.resize(size, Image.LANCZOS)

        # Save the processed image
        img.save(file_path)

@app.route('/')
def landing():
    return render_template('index.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if user.user_type == UserType.DESIGNATED:
                approval_request = ApprovalRequest.query.filter_by(user_id=user.id).first()
                if approval_request:
                    if approval_request.status == 'rejected':
                        flash('Your account approval has been rejected. Please contact the administrator for more information.', 'error')
                        return redirect(url_for('signin'))
                    elif approval_request.status == 'pending':
                        flash('Your account is pending approval. Please wait for admin confirmation.', 'warning')
                        return redirect(url_for('signin'))
                elif not user.is_approved:
                    flash('Your account is pending approval. Please wait for admin confirmation.', 'warning')
                    return redirect(url_for('signin'))
            session['user_id'] = user.id
            flash('Signed in successfully!', 'success')
            if user.user_type == UserType.ADMIN:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('signin.html')

@app.route('/signout')
def signout():
    session.pop('user_id', None)
    flash('Signed out successfully!', 'success')
    return redirect(url_for('landing'))

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        user_type = request.form.get('user_type')
        iit = request.form.get('iit')

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('signup.html')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered!', 'error')
            return render_template('signup.html')

        new_user = User(
            email=email,
            name=name,
            password=generate_password_hash(password),
            user_type=UserType(user_type),
            iit=iit,
            is_approved=user_type == UserType.STUDENT.value
        )

        if user_type == UserType.STUDENT.value:
            new_user.branch = request.form.get('branch')
            new_user.year = request.form.get('year')
        elif user_type == UserType.DESIGNATED.value:
            new_user.designation = request.form.get('designation')
            new_user.verification_mobile = request.form.get('verification_mobile')

        db.session.add(new_user)
        db.session.commit()

        if user_type == UserType.DESIGNATED.value:
            approval_request = ApprovalRequest(user_id=new_user.id)
            db.session.add(approval_request)
            db.session.commit()
            flash('Your account has been created and is pending approval. You will be notified once approved.', 'pending_approval')
        else:
            flash('Account created successfully! Please sign in.', 'success')

        return redirect(url_for('signin'))

    return render_template('signup.html')

@app.route('/admin/dashboard')
@app.route('/admin/dashboard/<section>')
@admin_required
def admin_dashboard(section='pending'):
    pending_requests = ApprovalRequest.query.filter_by(status='pending').all()
    approved_requests = ApprovalRequest.query.filter_by(status='approved').all()
    declined_requests = ApprovalRequest.query.filter_by(status='rejected').all()

    ist = pytz.timezone('Asia/Kolkata')
    
    for request in approved_requests + declined_requests:
        request.ist_updated_at = request.updated_at.replace(tzinfo=pytz.UTC).astimezone(ist)

    return render_template('admin_dashboard.html', 
                           section=section,
                           pending_requests=pending_requests,
                           approved_requests=approved_requests,
                           declined_requests=declined_requests)

@app.route('/admin/approve/<int:request_id>')
@admin_required
def approve_request(request_id):
    approval_request = ApprovalRequest.query.get_or_404(request_id)
    approval_request.status = 'approved'
    approval_request.user.is_approved = True
    approval_request.updated_at = datetime.utcnow()
    db.session.commit()
    flash('User approved successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:request_id>')
@admin_required
def reject_request(request_id):
    approval_request = ApprovalRequest.query.get_or_404(request_id)
    approval_request.status = 'rejected'
    approval_request.updated_at = datetime.utcnow()
    db.session.commit()
    flash('User rejected successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/bulletins', methods=['GET', 'POST'])
@login_required
def bulletins():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST' and user.user_type in [UserType.DESIGNATED, UserType.ADMIN]:
        title = request.form.get('title')
        content = request.form.get('content')
        image = request.files.get('image')
        visibility = request.form.get('visibility')

        if title and content:
            new_bulletin = Bulletin(title=title, content=content, user_id=user.id)
            
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(file_path)
                new_bulletin.image = filename

            if visibility == 'all':
                new_bulletin.visibility = {"all": True}
            elif visibility == 'my_iit':
                new_bulletin.visibility = {"my_iit": user.iit}

            db.session.add(new_bulletin)
            db.session.commit()
            flash('Bulletin posted successfully!', 'success')
            return redirect(url_for('bulletins'))
        else:
            flash('Title and content are required!', 'error')
            return redirect(url_for('bulletins'))

    filter_option = request.args.get('filter', 'all')

    if filter_option == 'all':
        bulletins = Bulletin.query.filter(
            db.or_(
                Bulletin.visibility.contains({"all": True}),
                Bulletin.visibility.contains({"my_iit": user.iit})
            )
        ).order_by(Bulletin.created_at.desc()).all()
    elif filter_option == 'my_iit':
        bulletins = Bulletin.query.filter(
            Bulletin.visibility.contains({"my_iit": user.iit})
        ).order_by(Bulletin.created_at.desc()).all()
    else:
        bulletins = []

    # Process visibility information for each bulletin
    for bulletin in bulletins:
        if bulletin.visibility.get('all', False):
            bulletin.visibility_info = 'all'
        elif bulletin.visibility.get('my_iit'):
            bulletin.visibility_info = bulletin.visibility['my_iit']

    return render_template('bulletins.html', bulletins=bulletins, user=user, filter_option=filter_option)

@app.route('/bulletin/upvote/<int:bulletin_id>', methods=['POST'])
@login_required
def upvote_bulletin(bulletin_id):
    user_id = session['user_id']
    existing_upvote = Upvote.query.filter_by(user_id=user_id, bulletin_id=bulletin_id).first()

    if existing_upvote:
        db.session.delete(existing_upvote)
        db.session.commit()
        return jsonify({'status': 'removed', 'count': Upvote.query.filter_by(bulletin_id=bulletin_id).count()})
    else:
        new_upvote = Upvote(user_id=user_id, bulletin_id=bulletin_id)
        db.session.add(new_upvote)
        db.session.commit()
        return jsonify({'status': 'added', 'count': Upvote.query.filter_by(bulletin_id=bulletin_id).count()})

@app.route('/bulletin/delete/<int:bulletin_id>', methods=['POST'])
@login_required
def delete_bulletin(bulletin_id):
    bulletin = Bulletin.query.get_or_404(bulletin_id)
    user = User.query.get(session['user_id'])

    if bulletin.user_id == user.id or user.user_type == UserType.ADMIN:
        db.session.delete(bulletin)
        db.session.commit()
        flash('Bulletin deleted successfully!', 'success')
    else:
        flash('You do not have permission to delete this bulletin.', 'error')

    return redirect(url_for('bulletins'))

@app.route('/tweets')
@login_required
def tweets():
    return render_template('tweets.html')

@app.route('/connect')
@login_required
def connect():
    return render_template('connect.html')

@app.route('/projects')
@login_required
def projects():
    return render_template('projects.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.name = request.form.get('name')
        if user.user_type == UserType.STUDENT:
            user.year = request.form.get('year')
            user.branch = request.form.get('branch')
        
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                crop_and_resize_image(file_path)
                user.profile_picture = filename

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

@app.route('/user/<int:user_id>/profile')
@login_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    profile_picture_url = url_for('static', filename='uploads/' + user.profile_picture) if user.profile_picture else None
    
    profile_data = {
        'name': user.name,
        'email': user.email,
        'iit': user.iit,
        'user_type': user.user_type.value,
        'profile_picture': profile_picture_url,
    }
    
    if user.user_type == UserType.STUDENT:
        profile_data.update({
            'branch': user.branch,
            'year': user.year,
        })
    elif user.user_type == UserType.DESIGNATED:
        profile_data['designation'] = user.designation

    return jsonify(profile_data)

def init_db():
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        admin_user = User.query.filter_by(email='iitconnectvk@gmail.com').first()
        if not admin_user:
            admin_user = User(
                email='iitconnectvk@gmail.com',
                name='Website Admin',
                password=generate_password_hash('Connect@14'),
                user_type=UserType.ADMIN,
                iit='Admin',
                is_approved=True
            )
            db.session.add(admin_user)
            db.session.commit()
        print("Database initialized.")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

