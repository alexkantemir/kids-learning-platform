# Kids Learning Platform

Образовательная платформа для детей с AI-генерацией уроков через GigaChat. Уроки создаются под конкретного ребёнка (возраст, класс, тема), проходят автоматическую валидацию и сохраняются в базу данных.

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy async, Pydantic v2 |
| База данных | PostgreSQL 16, Redis 7 |
| AI | GigaChat API (Sber) |
| Инфраструктура | Docker Compose, Nginx, Let's Encrypt |

## Возможности

- **Генерация уроков** — GigaChat создаёт персонализированный урок по теме и возрасту ребёнка, с повторными попытками при ошибках
- **Валидатор уроков** — автоматически проверяет математику, исправляет неверные индексы ответов, валидирует структуру шагов
- **Интерактивные шаги** — `multiple_choice`, `fill_blank` (поддержка нескольких пропусков), `match_pairs`, `sort_items`, `explain`
- **Геймификация** — XP, стрики, бейджи, прогресс по предметам
- **Кабинет родителя** — добавление детей, просмотр прогресса, управление профилями
- **Ежедневный разогрев** — 3 вопроса из уроков, пройденных 2–7 дней назад

## Структура проекта

```
kids-learning-platform/
├── backend/
│   ├── app/
│   │   ├── api/endpoints/      # FastAPI роуты
│   │   ├── models/             # SQLAlchemy модели
│   │   ├── schemas/            # Pydantic схемы
│   │   └── services/
│   │       ├── lesson_generator.py   # Генерация уроков через GigaChat
│   │       ├── lesson_validator.py   # Валидация и авто-исправление
│   │       └── gigachat.py           # GigaChat API клиент
│   └── tests/
│       └── test_lesson_validator.py  # 15 unit-тестов валидатора
├── frontend/
│   └── src/
│       ├── app/                # Next.js App Router страницы
│       └── components/ui/      # Компоненты шагов урока
├── nginx/conf.d/               # Nginx конфиг с SSL
└── docker-compose.yml
```

## Быстрый старт

### Требования

- Docker + Docker Compose
- GigaChat API credentials ([sberdevices.ru](https://developers.sber.ru/gigachat))

### Установка

```bash
git clone https://github.com/alexkantemir/kids-learning-platform.git
cd kids-learning-platform

# Скопировать и заполнить переменные окружения
cp .env.example .env
nano .env

# Запустить
docker compose up -d
```

### Переменные окружения

```env
# GigaChat API (получить в личном кабинете SberDevices)
GIGACHAT_CLIENT_ID=your-client-id
GIGACHAT_CLIENT_SECRET=your-base64-encoded-auth-key
GIGACHAT_SCOPE=GIGACHAT_API_PERS

# PostgreSQL
POSTGRES_DB=kids_platform
POSTGRES_USER=kids_user
POSTGRES_PASSWORD=generate-strong-password-here

# Application
SECRET_KEY=generate-64-char-hex-here
DATABASE_URL=postgresql+asyncpg://kids_user:password@postgres/kids_platform
REDIS_URL=redis://:password@redis:6379

# Environment
ENVIRONMENT=production
```

### Заполнить базу данных начальными данными

```bash
docker exec kids-platform-backend-1 python seed.py
```

## Запуск тестов

```bash
docker exec kids-platform-backend-1 python -m pytest tests/ -v
```

15 тестов покрывают:
- Авто-исправление неверного `correct_index` в математических вопросах
- Авто-исправление неверного ответа в `fill_blank`
- Валидацию структуры всех типов шагов
- Генерацию подсказок для повторной попытки GigaChat

## Архитектура генерации уроков

```
Запрос урока
    │
    ▼
GigaChat API ──► JSON урок
    │
    ▼
lesson_validator.py
    ├── Структурная валидация (обязательные поля, типы)
    ├── Математическая проверка (вычисляет выражение, сравнивает с ответом)
    │   └── Авто-исправление если верный ответ есть среди вариантов
    └── Проверка качества (подсказки, соответствие пропусков и ответов)
         │
         ├── Всё ОК ──► Сохранить урок со статусом ready
         ├── Есть исправления ──► Применить AutoFix, сохранить
         └── Критические ошибки ──► Повторить с retry_hint (до 3 раз)
                                        └── Если не исправлено ──► needs_review
```

## API

После запуска документация доступна на `http://localhost:8000/api/docs` (только в dev-режиме).

Основные эндпоинты:

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/auth/login` | Вход (родитель или ребёнок) |
| POST | `/api/auth/register-parent` | Регистрация родителя |
| GET | `/api/children/{id}` | Профиль ребёнка |
| GET | `/api/children/{id}/warmup` | Ежедневный разогрев |
| POST | `/api/lessons/generate` | Генерация урока |
| GET | `/api/lessons/{id}` | Получить урок с шагами |
| POST | `/api/quizzes/{lesson_id}/submit` | Сдать финальный квиз |

## Деплой на VDS

```bash
# На сервере
git clone https://github.com/alexkantemir/kids-learning-platform.git /opt/kids-platform
cd /opt/kids-platform
cp .env.example .env
# заполнить .env

docker compose up -d --build
docker exec kids-platform-backend-1 python seed.py
```

SSL через Let's Encrypt настраивается в `nginx/conf.d/kids-platform.conf`.
