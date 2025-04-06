from app import app, db, User

with app.app_context():
    # Удаляем все таблицы
    db.drop_all()
    # Создаем таблицы заново
    db.create_all()
    
    # Создаем тестового пользователя
    test_user = User(username='test', email='test@example.com')
    test_user.set_password('test')
    db.session.add(test_user)
    
    # Создаем администратора
    admin_user = User(username='admin', email='admin@example.com', is_admin=True)
    admin_user.set_password('admin')
    db.session.add(admin_user)
    
    # Сохраняем изменения
    db.session.commit()
    print("База данных успешно инициализирована!") 