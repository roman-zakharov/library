from app import app, db

with app.app_context():
    # Удаляем все таблицы
    db.drop_all()
    # Создаем таблицы заново
    db.create_all()
    print("База данных успешно очищена!") 