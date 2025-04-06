from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from datetime import datetime
import os
from sqlalchemy.exc import IntegrityError
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from functools import wraps
import random
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Модели данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    comments = db.relationship('Comment', backref='user', lazy=True)
    logs = db.relationship('Log', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    rating = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('books', lazy=True))
    comments = db.relationship('Comment', backref='book', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Маршруты
@app.route('/')
@login_required
def index():
    sort_by = request.args.get('sort_by', 'title')
    order = request.args.get('order', 'asc')
    filter_by = request.args.get('filter_by', None)
    
    # Фильтруем книги только для текущего пользователя
    query = Book.query.filter_by(user_id=current_user.id)
    
    if filter_by:
        query = query.filter((Book.title == filter_by) | (Book.author == filter_by))
    
    if sort_by == 'title':
        query = query.order_by(Book.title.asc() if order == 'asc' else Book.title.desc())
    elif sort_by == 'author':
        query = query.order_by(Book.author.asc() if order == 'asc' else Book.author.desc())
    elif sort_by == 'rating':
        query = query.order_by(Book.rating.asc() if order == 'asc' else Book.rating.desc())
    
    books = query.all()
    
    # Статистика
    total_books = len(books)
    
    # Подсчет книг по авторам
    author_stats = {}
    for book in books:
        if book.author in author_stats:
            author_stats[book.author] += 1
        else:
            author_stats[book.author] = 1
    
    # Сортировка авторов по количеству книг
    top_authors = sorted(author_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Форматирование статистики
    author_stats_formatted = []
    for author, count in top_authors:
        percentage = (count / total_books * 100) if total_books > 0 else 0
        author_stats_formatted.append({
            'author': author,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    return render_template('index.html', 
                         books=books, 
                         sort_by=sort_by, 
                         order=order, 
                         filter_by=filter_by,
                         total_books=total_books,
                         author_stats=author_stats_formatted)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            log_action(user.id, 'Вход в систему')
            return redirect(url_for('index'))
        
        log_action(None, 'Неудачная попытка входа', f'Пользователь: {username}')
        flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        print(f"Попытка регистрации пользователя: {username}, email: {email}")
        
        # Валидация имени пользователя
        if len(username) < 3 or len(username) > 20:
            flash('Имя пользователя должно быть от 3 до 20 символов!', 'error')
            return redirect(url_for('register'))
            
        # Проверяем, не содержит ли имя пользователя кириллицу
        if any(ord(c) >= 1040 for c in username):
            flash('Имя пользователя не должно содержать кириллицу!', 'error')
            return redirect(url_for('register'))
            
        # Валидация email
        if not '@' in email or not '.' in email:
            flash('Некорректный email адрес!', 'error')
            return redirect(url_for('register'))
        
        # Проверка существующего пользователя
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!', 'error')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует!', 'error')
            return redirect(url_for('register'))
        
        try:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            log_action(user.id, 'Регистрация')
            print(f"Пользователь {username} успешно зарегистрирован")
            flash('Регистрация успешна! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Ошибка при регистрации: {str(e)}")
            db.session.rollback()
            flash('Произошла ошибка при регистрации. Попробуйте еще раз.', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    log_action(current_user.id, 'Выход из системы')
    logout_user()
    return redirect(url_for('index'))

@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    if request.method == 'POST':
        title = request.form.get('title', "New title")
        author = request.form.get('author', 'new author')
        rating = int(request.form.get('rating', 0))
        
        book = Book(title=title, author=author, rating=rating, user_id=current_user.id)
        db.session.add(book)
        db.session.commit()
        log_action(current_user.id, 'Добавление книги', f'Название: {title}, Автор: {author}')
        flash('Книга успешно добавлена!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_book.html')

@app.route('/book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST' and current_user.is_authenticated:
        comment = Comment(
            content=request.form.get('content'),
            rating=float(request.form.get('rating')),
            user_id=current_user.id,
            book_id=book.id
        )
        db.session.add(comment)
        # Обновляем средний рейтинг книги
        book.rating = sum(c.rating for c in book.comments) / len(book.comments)
        db.session.commit()
        return redirect(url_for('book_detail', book_id=book.id))
    return render_template('book_detail.html', book=book)

@app.route('/book/<int:book_id>/update', methods=['POST'])
@login_required
def update_book(book_id):
    book = Book.query.get_or_404(book_id)
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    
    if field in ['title', 'author', 'rating']:
        if field == 'rating':
            value = float(value)
        setattr(book, field, value)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/search')
@login_required
def search():
    query = request.args.get('query', '').lower()
    
    if not query:
        books = Book.query.filter_by(user_id=current_user.id).all()
    else:
        all_books = Book.query.filter_by(user_id=current_user.id).all()
        books_with_scores = []
        
        for book in all_books:
            # Вычисляем степень схожести для названия и автора
            # Используем partial_ratio вместо ratio для лучшего поиска частичных совпадений
            title_ratio = fuzz.partial_ratio(query, book.title.lower())
            author_ratio = fuzz.partial_ratio(query, book.author.lower())
            
            # Берем максимальный показатель схожести
            max_ratio = max(title_ratio, author_ratio)
            
            # Если есть хотя бы частичное совпадение (порог 40%)
            if max_ratio >= 40:
                books_with_scores.append((book, max_ratio))
        
        # Сортируем по степени схожести (по убыванию)
        books_with_scores.sort(key=lambda x: x[1], reverse=True)
        books = [book for book, _ in books_with_scores]
    
    return render_template('index.html', books=books, query=query)

@app.route('/export')
@login_required
def export_books():
    books = Book.query.all()
    data = []
    for book in books:
        data.append({
            'Название': book.title,
            'Автор': book.author,
            'Описание': book.description,
            'Рейтинг': book.rating
        })
    df = pd.DataFrame(data)
    format = request.args.get('format', 'csv')
    if format == 'xlsx':
        df.to_excel('books.xlsx', index=False)
        return send_file('books.xlsx', as_attachment=True)
    else:
        df.to_csv('books.csv', index=False)
        return send_file('books.csv', as_attachment=True)

@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_books():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename.endswith('.csv'):
            try:
                # Читаем CSV файл
                df = pd.read_csv(file, encoding='utf-8')
                
                # Проверяем наличие необходимых колонок
                required_columns = ['Название', 'Автор', 'Комментарий']
                if not all(col in df.columns for col in required_columns):
                    flash('Ошибка: файл должен содержать колонки "Название", "Автор" и "Комментарий"')
                    return render_template('import.html')
                
                # Проверяем наличие данных в обязательных полях
                error_count = 0
                success_count = 0
                
                for index, row in df.iterrows():
                    # Проверяем обязательные поля на NaN и пустые значения
                    if pd.isna(row['Название']) or str(row['Название']).strip() == '':
                        error_count += 1
                        continue
                        
                    if pd.isna(row['Автор']) or str(row['Автор']).strip() == '':
                        error_count += 1
                        continue
                    
                    # Подготавливаем данные, заменяя NaN на пустую строку для необязательных полей
                    comment = '' if pd.isna(row['Комментарий']) else str(row['Комментарий'])
                    
                    # Создаем книгу
                    book = Book(
                        title=str(row['Название']).strip(),
                        author=str(row['Автор']).strip(),
                        description=comment.strip(),
                        user_id=current_user.id  # Добавляем user_id текущего пользователя
                    )
                    db.session.add(book)
                    success_count += 1
                
                if success_count > 0:
                    db.session.commit()
                    if error_count > 0:
                        flash(f'Импортировано {success_count} книг. {error_count} книг пропущено из-за отсутствия обязательных данных.')
                    else:
                        flash(f'Успешно импортировано {success_count} книг!')
                else:
                    flash('Ошибка: не удалось импортировать ни одной книги. Проверьте данные в файле.')
                
                return redirect(url_for('index'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при импорте: {str(e)}')
                return render_template('import.html')
                
        elif file.filename.endswith('.xlsx'):
            try:
                df = pd.read_excel(file)
                required_columns = ['Название', 'Автор', 'Комментарий']
                if not all(col in df.columns for col in required_columns):
                    flash('Ошибка: файл должен содержать колонки "Название", "Автор" и "Комментарий"')
                    return render_template('import.html')
                
                # Проверяем наличие данных в обязательных полях
                error_count = 0
                success_count = 0
                
                for index, row in df.iterrows():
                    # Проверяем обязательные поля на NaN и пустые значения
                    if pd.isna(row['Название']) or str(row['Название']).strip() == '':
                        error_count += 1
                        continue
                        
                    if pd.isna(row['Автор']) or str(row['Автор']).strip() == '':
                        error_count += 1
                        continue
                    
                    # Подготавливаем данные, заменяя NaN на пустую строку для необязательных полей
                    comment = '' if pd.isna(row['Комментарий']) else str(row['Комментарий'])
                    
                    # Создаем книгу
                    book = Book(
                        title=str(row['Название']).strip(),
                        author=str(row['Автор']).strip(),
                        description=comment.strip(),
                        user_id=current_user.id  # Добавляем user_id текущего пользователя
                    )
                    db.session.add(book)
                    success_count += 1
                
                if success_count > 0:
                    db.session.commit()
                    if error_count > 0:
                        flash(f'Импортировано {success_count} книг. {error_count} книг пропущено из-за отсутствия обязательных данных.')
                    else:
                        flash(f'Успешно импортировано {success_count} книг!')
                else:
                    flash('Ошибка: не удалось импортировать ни одной книги. Проверьте данные в файле.')
                
                return redirect(url_for('index'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при импорте: {str(e)}')
                return render_template('import.html')
        else:
            flash('Поддерживаются только файлы CSV и Excel')
            return render_template('import.html')
            
    return render_template('import.html')

@app.route('/comment/<int:comment_id>/update', methods=['POST'])
@login_required
def update_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    
    if field in ['content', 'rating']:
        if field == 'rating':
            value = float(value)
        setattr(comment, field, value)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 400


@app.route('/delete_books', methods=['POST'])
@login_required
def delete_books():
    book_ids = request.form.getlist('book_ids[]')
    
    # Отладочный вывод
    print(f"Получены ID книг для удаления: {book_ids}")
    
    if not book_ids:
        flash('Выберите книги для удаления', 'error')
        return redirect(url_for('index'))
    
    # Преобразуем строковые ID в целые числа
    try:
        book_ids = [int(book_id) for book_id in book_ids]
    except ValueError:
        flash('Неверный формат ID книг', 'error')
        return redirect(url_for('index'))
    
    try:
        # Сначала удаляем связанные комментарии
        Comment.query.filter(Comment.book_id.in_(book_ids)).delete(synchronize_session=False)
        
        # Затем удаляем сами книги, убедившись, что они принадлежат текущему пользователю
        deleted_count = Book.query.filter(
            Book.id.in_(book_ids), 
            Book.user_id == current_user.id
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        if deleted_count > 0:
            flash(f'Успешно удалено {deleted_count} книг', 'success')
            log_action(current_user.id, 'Удаление книг', f'Удалено {deleted_count} книг')
        else:
            flash('Нет прав на удаление выбранных книг или книги не найдены', 'warning')
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при удалении книг: {str(e)}")
        flash(f'Произошла ошибка при удалении книг: {str(e)}', 'error')
    
    return redirect(url_for('index'))

""" @app.route('/delete_books', methods=['POST'])
@login_required
def delete_books():
    book_ids = request.form.getlist('book_ids[]')
    if not book_ids:
        flash('Выберите книги для удаления')
        return redirect(url_for('index'))
    
    # Проверяем, что все книги принадлежат текущему пользователю
    books = Book.query.filter(Book.id.in_(book_ids), Book.user_id == current_user.id).all()
    
    if not books:
        flash('Нет прав на удаление выбранных книг')
        return redirect(url_for('index'))
    
    try:
        for book in books:
            db.session.delete(book)
        db.session.commit()
        flash(f'Успешно удалено {len(books)} книг')
    except Exception as e:
        db.session.rollback()
        flash('Произошла ошибка при удалении книг')
    
    return redirect(url_for('index'))
 """
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('У вас нет прав для доступа к этой странице.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/update_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    
    if field in ['username', 'email']:
        try:
            setattr(user, field, value)
            db.session.commit()
            return jsonify({'success': True})
        except IntegrityError:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Значение уже используется'})
    
    return jsonify({'success': False, 'error': 'Недопустимое поле'})

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    user.set_password(new_password)
    db.session.commit()
    return jsonify({'success': True, 'new_password': new_password})

@app.route('/admin/user_logs/<int:user_id>')
@login_required
@admin_required
def user_logs(user_id):
    logs = Log.query.filter_by(user_id=user_id).order_by(Log.timestamp.desc()).all()
    return jsonify({
        'logs': [{
            'timestamp': log.timestamp.isoformat(),
            'action': log.action,
            'details': log.details
        } for log in logs]
    })

def log_action(user_id, action, details=None):
    try:
        log = Log(user_id=user_id, action=action, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка при логировании: {str(e)}")
        db.session.rollback()

if __name__ == '__main__':
    with app.app_context():
        # Создаем таблицы, если они не существуют
        db.create_all()
        
        # Создаем тестового пользователя и админа, если их нет
        test_user = User.query.filter_by(username='test').first()
        if not test_user:
            test_user = User(username='test', email='test@example.com')
            test_user.set_password('test')
            db.session.add(test_user)
            db.session.commit()
            
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', email='admin@example.com', is_admin=True)
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            
    app.run(host='0.0.0.0', port=5000, debug=True) 