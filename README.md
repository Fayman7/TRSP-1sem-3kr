# FastAPI

## Установка и запуск

```powershell
cd fastapi-basic-login
pip install -r requirements.txt
```

Скопируйте переменные окружения:

```powershell
copy .env.example .env
```

Создайте таблицы в SQLite (один раз):

```powershell
python -c "from main import init_db; init_db()"
```

Или просто запустите сервер — таблицы создаются автоматически при старте.

Запуск сервера:

```powershell
python -m uvicorn main:app --reload
```

Приложение: http://127.0.0.1:8000

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `MODE` | `DEV` или `PROD` | `DEV` |
| `DOCS_USER` | Логин для `/docs` (только DEV) | — |
| `DOCS_PASSWORD` | Пароль для `/docs` (только DEV) | — |
| `JWT_SECRET` | Секрет для подписи JWT | `your-secret-key` |
| `JWT_ALGORITHM` | Алгоритм JWT | `HS256` |
| `JWT_EXPIRE_MINUTES` | Срок жизни токена (мин) | `30` |

- **DEV**: `/docs` и `/openapi.json` защищены Basic Auth; `/redoc` скрыт.
- **PROD**: `/docs`, `/openapi.json`, `/redoc` возвращают 404.

Файл `.env` не коммитится — см. `.gitignore`.

## Тестирование (curl)

> В **PowerShell** для JSON используйте `--%` перед `-d`, либо `-d $body` с переменной.

### Регистрация и SQLite

```powershell
curl.exe --% -X POST -H "Content-Type: application/json" -d "{\"username\":\"test_user\",\"password\":\"12345\"}" http://127.0.0.1:8000/register
```

### JWT-логин

```powershell
curl.exe --% -X POST -H "Content-Type: application/json" -d "{\"username\":\"admin1\",\"password\":\"pass123\"}" http://127.0.0.1:8000/login
```

Сохранить токен:

```powershell
$token = (curl.exe --% -s -X POST -H "Content-Type: application/json" -d "{\"username\":\"admin1\",\"password\":\"pass123\"}" http://127.0.0.1:8000/login | ConvertFrom-Json).access_token
```

### Защищённый ресурс (JWT + RBAC)

```powershell
curl.exe -H "Authorization: Bearer $token" http://127.0.0.1:8000/protected_resource
```

### Todo CRUD

```powershell
# Create
curl.exe --% -X POST -H "Content-Type: application/json" -d "{\"title\":\"Buy groceries\",\"description\":\"Milk, eggs, bread\"}" http://127.0.0.1:8000/todos

# Read (подставьте id из ответа POST)
curl.exe http://127.0.0.1:8000/todos/1

# Update
curl.exe -X PUT -H "Content-Type: application/json" --% -d "{\"title\":\"Buy groceries\",\"description\":\"Milk, eggs, bread\",\"completed\":true}" http://127.0.0.1:8000/todos/1

# Delete
curl.exe -X DELETE http://127.0.0.1:8000/todos/1
```

### Документация API (DEV)

```powershell
curl.exe -u valid_user:valid_password http://127.0.0.1:8000/docs
```

## Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/register` | Регистрация пользователя (SQLite) |
| POST | `/login` | JWT-логин |
| GET | `/login` | Basic Auth логin |
| GET | `/protected_resource` | JWT, роли admin/user |
| POST/GET/PUT/DELETE | `/todos`, `/todos/{id}` | CRUD Todo (SQLite) |
| GET | `/docs` | Swagger UI (DEV, Basic Auth) |
