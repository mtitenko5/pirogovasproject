# CT Report Service

Веб-сервис для интеллектуальной генерации заключения врача-кардиохирурга по данным КТ аорты.

## О проекте

**CT Report Service** — это backend-сервис на FastAPI, который принимает от пользователя архив с изображениями КТ, файл измерений и метаданные пациента, после чего сохраняет данные отчета в PostgreSQL и готовит основу для генерации медицинского заключения. Генерация текста отчета вынесена в LLM-сервис, а формирование HTML/PDF предусмотрено отдельными утилитами.

Проект сейчас находится на стадии backend-прототипа: реализованы API-слой, модели БД, схемы, сервисы пользователей/администратора/отчетов и Docker Compose для запуска приложения с PostgreSQL.

## Ключевые возможности

### Для пользователя
- **Загрузка кейса** — ZIP-архив с КТ-изображениями, файл измерений CSV/JSON и метаданные пациента.
- **Создание отчета** — сохранение измерений, путей к изображениям, метаданных пациента, ответа LLM и trace-данных.
- **Просмотр отчетов** — получение списка отчетов по логину пользователя.
- **Экспорт отчета** — предусмотрена генерация HTML/PDF через утилиты `html_report_generator.py` и `pdf_generator.py`.
- **Оценка качества** — добавление оценки и текстового комментария к отчету.

### Для администратора
- **Управление пользователями** — создание пользователей и обновление их данных.
- **Ролевая модель** — проверка административного доступа через JWT и зависимости FastAPI.
- **Первичная инициализация** — bootstrap-сервис создает первую организацию и администратора из переменных окружения.

## Пользовательский сценарий

1. **Авторизация** Пользователь получает JWT-токен через `/api/v1/users/login`.
2. **Загрузка** Пользователь отправляет ZIP с КТ-изображениями, файл измерений и метаданные пациента в `/api/v1/llm/create_report`.
3. **Обработка файлов** Сервис разбирает измерения и сохраняет изображения на диск.
4. **Генерация** LLM-сервис формирует текстовую основу заключения и trace-данные.
5. **Сохранение** Отчет сохраняется в PostgreSQL.
6. **Экспорт** По идентификатору отчета можно запустить генерацию HTML/PDF.
7. **Оценка** Пользователь добавляет оценку качества и комментарий.

## Технологии

Python 3.11, FastAPI, PostgreSQL, SQLAlchemy async, Pydantic / pydantic-settings, Uvicorn, Docker Compose, JWT через `python-jose`, хеширование паролей через `passlib` / `bcrypt`, загрузка файлов через `python-multipart`.

## Требования

- Python 3.11+
- `pip`
- Docker и Docker Compose

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/citec-spbu/pirogovasproject
cd pirogovasproject
```

### 2. Настройка окружения

Создайте `.env` на основе примера:

```bash
cp .env.example .env
```

Для Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Основные переменные:

```text
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=ct_photos_database
FIRST_ADMIN_LOGIN=admin
FIRST_ADMIN_PASSWORD=admin123
SECRET_KEY=some-super-secret-long-random-string
```

### 3. Запуск через Docker Compose

```bash
docker compose up --build
```

После запуска API будет доступно по адресу:

```text
http://localhost:8000
```

Swagger-документация:

```text
http://localhost:8000/docs
```

### 4. Локальный запуск backend без Docker

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Для Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

При локальном запуске должен быть доступен PostgreSQL, а `DATABASE_URL` должен использовать async-драйвер, например:

```text
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ct_photos_database
```

## Структура проекта

```text
pirogovasproject/
├── backend/                         # FastAPI backend
│   ├── Dockerfile                    # Docker-образ backend-сервиса
│   ├── README.md                     # Черновое описание структуры backend
│   ├── requirements.txt              # Python-зависимости backend
│   └── app/
│       ├── main.py                   # Точка входа FastAPI, подключение роутеров
│       ├── api/
│       │   ├── dependencies.py       # Общие зависимости API, авторизация и проверка ролей
│       │   └── v1/
│       │       ├── admin.py          # Эндпоинты администратора: пользователи, шаблоны, протоколы, метрики
│       │       ├── llm.py            # Создание отчета через LLM-пайплайн
│       │       ├── reports.py        # Получение, генерация, скачивание и оценка отчетов
│       │       └── users.py          # Авторизация, регистрация и операции пользователя
│       ├── core/
│       │   ├── config.py             # Настройки приложения из .env
│       │   ├── database.py           # Async SQLAlchemy engine, Base и сессии БД
│       │   ├── role.py               # Роли пользователей
│       │   ├── security.py           # JWT, хеширование и проверка паролей
│       │   ├── celery_app.py         # Конфигурация Celery для фоновых задач генерации отчетов
│       │   └── rag/
│       │       ├── chunker.py        # Функции разбиения медицинских текстов на чанки
│       │       ├── embedder.py       # Эмбеддинг-кодирование текстовых фрагментов
│       │       ├── vector_store.py   # Организация и поиск по векторному хранилищу
│       │       ├── bm25_index.py     # BM25-индекс для полнотекстового поиска
│       │       ├── graph_builder.py  # Построение графа знаний по клиническим протоколам
│       │       ├── retriever.py      # Гибридный поиск и graph RAG для подбора контекста
│       │       └── kb_manager.py     # Управление базой знаний и индексацией протоколов
│       ├── models/
│       │   ├── report.py             # SQLAlchemy-модель отчета
│       │   ├── user.py               # SQLAlchemy-модели пользователя и организации
│       │   ├── clinical_protocols.py # SQLAlchemy-модель клинического протокола
│       │   ├── llm_calls.py          # SQLAlchemy-модель вызовов LLM и их статусов
│       │   └── report_templates.py   # SQLAlchemy-модель шаблонов отчетов
│       ├── schemas/
│       │   ├── admin.py              # Pydantic-схемы администратора
│       │   ├── report.py             # Pydantic-схемы отчетов
│       │   ├── llm.py                # Схемы запроса и ответа для LLM
│       │   ├── user.py               # Pydantic-схемы авторизации и пользователей
│       │   ├── clinical_protocol.py  # Pydantic-схемы клинических протоколов
│       │   ├── llm_call.py           # Pydantic-схемы логирования LLM-вызовов
│       │   └── report_template.py    # Pydantic-схемы шаблонов отчетов
│       ├── services/
│       │   ├── admin_service.py      # Бизнес-логика администратора
│       │   ├── bootstrap_service.py  # Первичная инициализация данных
│       │   ├── llm_service.py        # Обработка запроса к LLM
│       │   ├── ml_engine.py          # Подготовка LLM-запроса и подтягивание контекста
│       │   ├── storage_service.py    # Работа с файловым хранилищем MinIO
│       │   ├── report_service.py     # Бизнес-логика отчетов
│       │   └── user_service.py       # Бизнес-логика пользователей
│       ├── tasks/
│       │   ├── report_tasks.py       # Celery-задачи фоновой генерации отчетов
│       │   └── __init__.py           # Инициализация пакета фоновых задач
│       └── utils/
│           ├── file_handler.py       # Обработка ZIP, CSV и JSON
│           ├── html_report_generator.py # Генерация HTML-версии медицинского отчета
│           └── pdf_generator.py      # Генерация PDF из HTML-отчета
├── clinical_protocols/               # Клинические протоколы и рекомендации в PDF
│   ├── 158-157-1-PB.pdf              # Исходный PDF-документ клинического протокола
│   └── Рекомендации_торакоабдоминальная_аорта.pdf # Рекомендации по торакоабдоминальной аорте
├── docs/                             # Артефакты формирования клиентского пути
│   ├── endpoints_draft_txt/          # Черновики API-эндпоинтов
│   │   └── endpoints_api_for_user.txt # Описание API для пользовательских сценариев
│   └── user_actions_draft/           # Черновики пользовательских сценариев
│       └── 1.pdf                     # PDF-схема или описание пользовательского пути
└── frontend/                         # React + Vite frontend
    ├── .gitignore                    # Исключения Git для frontend
    ├── Dockerfile                    # Docker-образ frontend-сервиса
    ├── eslint.config.js              # Конфигурация ESLint
    ├── index.html                    # HTML-точка входа Vite
    ├── package-lock.json             # Зафиксированные версии npm-зависимостей
    ├── package.json                  # Скрипты и зависимости frontend
    ├── README.md                     # Описание frontend-проекта
    ├── tsconfig.app.json             # TypeScript-настройки приложения
    ├── tsconfig.json                 # Общая TypeScript-конфигурация
    ├── tsconfig.node.json            # TypeScript-настройки для Node/Vite
    ├── vite.config.ts                # Конфигурация Vite
    └── src/
        ├── App.tsx                   # Корневой компонент приложения
        ├── index.css                 # Глобальные CSS-стили
        ├── main.tsx                  # Точка входа React-приложения
        ├── app/                      # Инициализация приложения, роутинг, layout и стили
        ├── entities/                 # Доменные типы сущностей: пользователь, отчет
        ├── features/                 # Самостоятельные пользовательские функции и модальные окна
        ├── pages/                    # Страницы приложения: вход, главная, admin-разделы
        ├── shared/                   # Переиспользуемые API-клиенты, UI-компоненты, assets и утилиты
        └── widgets/                  # Крупные UI-блоки: header, sidebar, таблицы, формы и списки
├── .env.example                      # Пример переменных окружения
├── docker-compose.yml                # Запуск PostgreSQL, backend и связанных сервисов
├── nginx.conf                        # Конфигурация nginx для проксирования frontend/backend
├── openapi.json                      # OpenAPI-спецификация backend API
└── Проект Клиники Пирогова.txt       # Текстовое описание проекта

```

## Тестирование

Автоматические тесты в текущей структуре пока не добавлены. Для первичной проверки после запуска можно открыть:

```text
http://localhost:8000/docs
```

Также можно проверить корневой эндпоинт:

```bash
curl http://localhost:8000/
```

Ожидаемый ответ:

```json
{"message":"Welcome to the CT AI Analysis API!"}
```

## Для чего подходит этот проект

Проект разрабатывается как исследовательский прототип для автоматизации формирования кардиохирургических заключений на основе данных КТ-снимков. Сервис предназначен для вспомогательных целей и требует обязательной верификации результатов квалифицированным врачом.

## Вклад в проект

Проект разработан при поддержке Клиники Пирогова СПбГУ и Центра ИИ СПбГУ. Предложения по улучшению архитектуры и функционала приветствуются.

## Контакты

Обновятся позднее.

## Дисклеймер

Данный сервис предназначен исключительно для вспомогательных и исследовательских целей. Сгенерированные отчеты не являются официальными медицинскими документами и подлежат обязательной верификации врачом-кардиохирургом. Разработчики не несут ответственности за клинические решения, принятые на основе автоматизированных выводов.
