import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf','doc','docx','png','jpg','jpeg','ppt','pptx','xls','xlsx','txt'}

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'hub.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'dev-secret-key'  # replace in production

db = SQLAlchemy(app)

# Models
class StudyMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    created_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    options = db.relationship('SurveyOption', backref='survey', cascade="all, delete-orphan")

class SurveyOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    text = db.Column(db.String(200), nullable=False)
    votes = db.Column(db.Integer, default=0)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    asked_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answers = db.relationship('Answer', backref='question', cascade="all, delete-orphan")

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    replied_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TechNews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(500), nullable=False)
    posted_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    posted_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    latest_materials = StudyMaterial.query.order_by(StudyMaterial.created_at.desc()).limit(5).all()
    latest_surveys = Survey.query.order_by(Survey.created_at.desc()).limit(5).all()
    latest_questions = Question.query.order_by(Question.created_at.desc()).limit(5).all()
    latest_news = TechNews.query.order_by(TechNews.created_at.desc()).limit(5).all()
    latest_announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all()
    return render_template('index.html',
                           materials=latest_materials,
                           surveys=latest_surveys,
                           questions=latest_questions,
                           news=latest_news,
                           announcements=latest_announcements)

# Study Materials
@app.route('/materials', methods=['GET', 'POST'])
def materials():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        description = request.form.get('description','').strip()
        uploaded_by = request.form.get('uploaded_by','').strip()
        file = request.files.get('file')
        if not title or not file or file.filename == '':
            flash('Title and file are required.')
            return redirect(url_for('materials'))
        if not allowed_file(file.filename):
            flash('File type not allowed.')
            return redirect(url_for('materials'))
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        # Avoid overwrite: if exists, add suffix
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(save_path):
            filename = f"{base}_{counter}{ext}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            counter += 1
        file.save(save_path)
        item = StudyMaterial(title=title, description=description, filename=filename, uploaded_by=uploaded_by)
        db.session.add(item)
        db.session.commit()
        flash('Material uploaded successfully.')
        return redirect(url_for('materials'))
    items = StudyMaterial.query.order_by(StudyMaterial.created_at.desc()).all()
    return render_template('materials.html', items=items)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)

# Surveys
@app.route('/surveys', methods=['GET', 'POST'])
def surveys():
    if request.method == 'POST':
        question = request.form.get('question','').strip()
        created_by = request.form.get('created_by','').strip()
        raw_options = [o.strip() for o in request.form.getlist('options') if o.strip()]
        if not question or len(raw_options) < 2:
            flash('Question and at least two options are required.')
            return redirect(url_for('surveys'))
        s = Survey(question=question, created_by=created_by)
        db.session.add(s)
        db.session.flush()
        for opt in raw_options:
            db.session.add(SurveyOption(survey_id=s.id, text=opt, votes=0))
        db.session.commit()
        flash('Survey created.')
        return redirect(url_for('surveys'))
    all_surveys = Survey.query.order_by(Survey.created_at.desc()).all()
    return render_template('surveys.html', surveys=all_surveys)

@app.route('/surveys/<int:survey_id>/vote', methods=['POST'])
def vote_survey(survey_id):
    option_id = request.form.get('option_id', type=int)
    option = SurveyOption.query.filter_by(id=option_id, survey_id=survey_id).first()
    if option:
        option.votes += 1
        db.session.commit()
        flash('Vote counted!')
    else:
        flash('Invalid vote.')
    return redirect(url_for('surveys'))

# Q/A
@app.route('/qa', methods=['GET', 'POST'])
def qa():
    if request.method == 'POST':
        text = request.form.get('text','').strip()
        asked_by = request.form.get('asked_by','').strip()
        if not text:
            flash('Question text is required.')
            return redirect(url_for('qa'))
        q = Question(text=text, asked_by=asked_by)
        db.session.add(q)
        db.session.commit()
        flash('Question posted.')
        return redirect(url_for('qa'))
    questions = Question.query.order_by(Question.created_at.desc()).all()
    return render_template('qa.html', questions=questions)

@app.route('/qa/<int:question_id>/answer', methods=['POST'])
def answer(question_id):
    text = request.form.get('text','').strip()
    replied_by = request.form.get('replied_by','').strip()
    if not text:
        flash('Reply text is required.')
        return redirect(url_for('qa'))
    a = Answer(question_id=question_id, text=text, replied_by=replied_by)
    db.session.add(a)
    db.session.commit()
    flash('Reply added.')
    return redirect(url_for('qa'))

# Tech News
@app.route('/tech', methods=['GET', 'POST'])
def tech():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        link = request.form.get('link','').strip()
        posted_by = request.form.get('posted_by','').strip()
        if not title or not link:
            flash('Title and link are required.')
            return redirect(url_for('tech'))
        item = TechNews(title=title, link=link, posted_by=posted_by)
        db.session.add(item)
        db.session.commit()
        flash('Tech news posted.')
        return redirect(url_for('tech'))
    items = TechNews.query.order_by(TechNews.created_at.desc()).all()
    return render_template('tech.html', items=items)

# Announcements
@app.route('/announcements', methods=['GET', 'POST'])
def announcements():
    if request.method == 'POST':
        text = request.form.get('text','').strip()
        posted_by = request.form.get('posted_by','').strip()
        if not text:
            flash('Announcement text is required.')
            return redirect(url_for('announcements'))
        a = Announcement(text=text, posted_by=posted_by)
        db.session.add(a)
        db.session.commit()
        flash('Announcement posted.')
        return redirect(url_for('announcements'))
    items = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('announcements.html', items=items)

# Init
@app.cli.command('init-db')
def init_db_cmd():
    db.create_all()
    print('Database initialized.')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)