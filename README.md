# Library Web Application

This is a Flask-based web application for managing a library of books. It allows users to add, edit, and search for books, as well as import and export book data.

## Features

- Add, edit, and delete books
- Search for books by title or author
- Import and export books in CSV and Excel formats
- User authentication and authorization

## Requirements

- Docker
- Docker Compose

## Setup and Deployment

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Build and run the application using Docker Compose:**

   ```bash
   docker-compose up --build
   ```

3. **Access the application:**

   Open your web browser and go to `http://localhost:5000`.

4. **Stop the application:**

   To stop the application, press `Ctrl+C` in the terminal where Docker Compose is running.

5. **Remove containers:**

   To remove the containers, run:

   ```bash
   docker-compose down
   ```

## Environment Variables

- `FLASK_APP`: The entry point of the application (default: `app.py`)
- `FLASK_ENV`: The environment in which the application is running (default: `development`)

## Database

The application uses PostgreSQL as the database. The database configuration is defined in the `docker-compose.yml` file.

## License

This project is licensed under the MIT License.

## Функциональность

- Регистрация и авторизация пользователей
- Добавление новых книг
- Поиск книг по названию и автору
- Добавление комментариев и рейтингов к книгам
- Импорт книг из CSV и Excel файлов
- Экспорт книг в CSV и Excel форматы

## Установка

1. Клонируйте репозиторий:
```bash
git clone <url-репозитория>
cd library
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
venv\Scripts\activate  # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Запустите приложение:
```bash
python app.py
```

5. Откройте браузер и перейдите по адресу: http://localhost:5000

## Использование

### Регистрация и авторизация
1. Нажмите "Регистрация" для создания нового аккаунта
2. Заполните форму регистрации
3. После регистрации войдите в систему

### Работа с книгами
1. Нажмите "Добавить книгу" для добавления новой книги
2. Заполните форму с информацией о книге
3. Используйте поиск для фильтрации книг
4. Нажмите на книгу для просмотра деталей и добавления комментариев

### Импорт/Экспорт
1. Для импорта книг нажмите "Импорт" и выберите CSV или Excel файл
2. Для экспорта нажмите "Экспорт" и выберите желаемый формат

## Формат файлов для импорта

### CSV
```csv
Название,Автор,Описание
Война и мир,Лев Толстой,Роман-эпопея
Преступление и наказание,Федор Достоевский,Роман
```

### Excel
Файл должен содержать те же колонки: Название, Автор, Описание 