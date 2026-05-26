# CT Report

Веб-сервис для интеллектуальной генерации заключения врача-кардиохирурга по данным КТ аорты.

## О проекте

**CT Report** — это backend-сервис на FastAPI, который принимает от пользователя архив с изображениями КТ, файл измерений и метаданные пациента, после чего сохраняет данные отчета в PostgreSQL и готовит основу для генерации медицинского заключения. Генерация текста отчета вынесена в LLM-сервис, а формирование HTML/PDF предусмотрено отдельными утилитами.

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
│       │   ├── dependencies.py       # Общие зависимости API, проверка ролей
│       │   └── v1/
│       │       ├── admin.py          # Эндпоинты администратора
│       │       ├── llm.py            # Создание отчета через LLM-пайплайн
│       │       ├── reports.py        # Получение, генерация и оценка отчетов
│       │       └── users.py          # Авторизация пользователей
│       ├── core/
│       │   ├── config.py             # Настройки из .env
│       │   ├── database.py           # Async SQLAlchemy engine и сессии
│       │   ├── role.py               # Роли пользователей
│       │   |── security.py           # JWT и пароли
│       │   |── celery_app.py
│       │   └── rag/                  
│       │       ├── chunker.py        # функции чанкования текста
│       │       ├── embedder.py       # эмбеддинг-кодирование
│       │       ├── vector_store.py   # организация векторного хранилища
│       │       ├── bm25_index.py     # индекс bm25 (опционален для подключения)
│       │       ├── graph_builder.py  # построение графа знаний
│       │       ├── retriever.py      # гибридный поиск и графовый rag
│       │       └── kb_manager.py     # управление базой знаний
│       ├── models/
│       │   ├── report.py             # SQLAlchemy-модель отчета
│       │   ├── user.py               # SQLAlchemy-модели пользователя и организации
│       │   ├── clinical_protocols.py
│       │   ├── llm_calls.py
│       │   ├── report.py
│       │   └── report_templates.py
│       ├── schemas/
│       │   ├── admin.py              # Pydantic-схемы администратора
│       │   ├── report.py             # Pydantic-схемы отчетов
│       │   ├── llm.py                       # схема для получения ответа и отправления запроса
│       │   ├── user.py               # Pydantic-схемы авторизации
│       │   ├── clinical_protocol.py
│       │   ├── llm_call.py
│       │   └── report_template.py
│       │ 
│       ├── services/
│       │   ├── admin_service.py      # Бизнес-логика администратора
│       │   ├── bootstrap_service.py  # Первичная инициализация данных
│       │   ├── llm_service.py        # обработка запроса к LLM
│       │   ├── ml_engine.py          # отправление запроса к LLM и подтаскивание контекста
│       │   ├── storage_service.py    
│       │   ├── report_service.py     # Бизнес-логика отчетов
│       │   └── user_service.py       # Бизнес-логика пользователей
│       ├───tasks/
│       │       report_tasks.py       # 
│       │       __init__.py
│       └── utils/
│           ├── file_handler.py       # Обработка ZIP, CSV и JSON
│           ├── html_report_generator.py
│           └── pdf_generator.py
├───clinical_protocols #клинические протоколы
│       158-157-1-PB.pdf
        ...
│       Рекомендации_торакоабдоминальная_аорта.pdf
├───docs # артефакты формирования клиентского пути
│   ├───endpoints_draft_txt
│   │       endpoints_api_for_user.txt
│   │
│   └───user_actions_draft
│           1.pdf
│
└───frontend
    │   .gitignore
    │   Dockerfile
    │   eslint.config.js
    │   index.html
    │   package-lock.json
    │   package.json
    │   README.md
    │   tsconfig.app.json
    │   tsconfig.json
    │   tsconfig.node.json
    │   vite.config.ts
    │
    └───src
        │   App.tsx
        │   index.css
        │   main.tsx
        │
        ├───app
        │   ├───layouts
        │   │   └───AdminLayout
        │   │           AdminLayout.module.scss
        │   │           AdminLayout.tsx
        │   │
        │   ├───router
        │   │       AppRouter.tsx
        │   │       ProtectedRoute.tsx
        │   │
        │   └───styles
        │           index.scss
        │
        ├───entities
        │   ├───report
        │   │   └───model
        │   │           types.ts
        │   │
        │   └───user
        │       └───model
        │               types.ts
        │
        ├───features
        │   ├───change-password
        │   │       ChangePasswordModal.module.scss
        │   │       ChangePasswordModal.tsx
        │   │
        │   ├───report-review
        │   │       ReportReview.module.scss
        │   │       ReportReview.tsx
        │   │
        │   ├───restore-password
        │   │       RestorePasswordModal.module.scss
        │   │       RestorePasswordModal.tsx
        │   │
        │   ├───user-form-modal
        │   │       UserFormModal.module.scss
        │   │       UserFormModal.tsx
        │   │
        │   └───view-user-modal
        │           UserInfoModal.module.scss
        │           UserInfoModal.tsx
        │
        ├───pages
        │   ├───AdminDashboardPage
        │   │       AdminDashboardPage.module.scss
        │   │       AdminDashboardPage.tsx
        │   │
        │   ├───AdminProtocolsPage
        │   │       AdminProtocolsPage.module.scss
        │   │       AdminProtocolsPage.tsx
        │   │
        │   ├───AdminTemplatesPage
        │   │       AdminTemplatesPage.module.scss
        │   │       AdminTemplatesPage.tsx
        │   │
        │   ├───AdminUsersPage
        │   │       AdminUsersPage.module.scss
        │   │       AdminUsersPage.tsx
        │   │
        │   ├───LoginPage
        │   │       LoginPage.module.scss
        │   │       LoginPage.tsx
        │   │
        │   └───MainPage
        │           MainPage.module.scss
        │           MainPage.tsx
        │
        ├───shared
        │   ├───api
        │   │       adminApi.ts
        │   │       apiClient.ts
        │   │       authApi.ts
        │   │       reportApi.ts
        │   │       userApi.ts
        │   │
        │   ├───assets
        │   │   ├───fonts
        │   │   │   ├───DaysOne
        │   │   │   │       DaysOne-Regular.ttf
        │   │   │   │
        │   │   │   ├───OpenSans
        │   │   │   │       OpenSans-Bold.ttf
        │   │   │   │       OpenSans-Light.ttf
        │   │   │   │       OpenSans-Medium.ttf
        │   │   │   │       OpenSans-Regular.ttf
        │   │   │   │       OpenSans-SemiBold.ttf
        │   │   │   │
        │   │   │   └───ViaodaLibre
        │   │   │           ViaodaLibre-Regular.ttf
        │   │   │
        │   │   ├───icons
        │   │   │       accountIcon.svg
        │   │   │       addIcon.svg
        │   │   │       crossIcon.svg
        │   │   │       CTReport.svg
        │   │   │       deleteIcon.svg
        │   │   │       doorIcon.svg
        │   │   │       downloadIcon.svg
        │   │   │       editIcon.svg
        │   │   │       exitIcon.svg
        │   │   │       eyeCloseIcon.svg
        │   │   │       eyeIcon.svg
        │   │   │       fileBlueIcon.svg
        │   │   │       fileIcon.svg
        │   │   │       heartLogoIcon.svg
        │   │   │       homeIcon.svg
        │   │   │       infoIcon.svg
        │   │   │       lockIcon.svg
        │   │   │       logoIcon.svg
        │   │   │       logOuIcont.svg
        │   │   │       openUserIcon.svg
        │   │   │       searchIcon.svg
        │   │   │       starEmptyIcon.svg
        │   │   │       starFullIcon.svg
        │   │   │       tsconfig.app.json
        │   │   │       userIcon.svg
        │   │   │       userLogoW.svg
        │   │   │
        │   │   └───images
        │   │           bgHomePage.png
        │   │
        │   ├───lib
        │   │       jwt.ts
        │   │       tokenStorage.ts
        │   │
        │   └───ui
        │       ├───Button
        │       │       Button.module.scss
        │       │       Button.tsx
        │       │
        │       ├───Dropdown
        │       │       Dropdown.module.scss
        │       │       Dropdown.tsx
        │       │
        │       ├───FileInput
        │       │       FileInput.module.scss
        │       │       FileInput.tsx
        │       │
        │       ├───Input
        │       │       Input.module.scss
        │       │       Input.tsx
        │       │
        │       ├───Modal
        │       │       Modal.module.scss
        │       │       Modal.tsx
        │       │
        │       ├───Radio
        │       │       Radio.module.scss
        │       │       Radio.tsx
        │       │
        │       └───SearchBar
        │               SearchBar.module.scss
        │               SearchBar.tsx
        │
        └───widgets
            ├───AdminHeader
            │       AdminHeader.module.scss
            │       AdminHeader.tsx
            │
            ├───AdminSidebar
            │       AdminSidebar.module.scss
            │       AdminSidebar.tsx
            │
            ├───AdminStats
            │       AdminStats.module.scss
            │       AdminStats.tsx
            │
            ├───AdminUsersToolbar
            │       AdminUsersToolbar.module.scss
            │       AdminUsersToolbar.tsx
            │
            ├───Header
            │       Header.module.scss
            │       Header.tsx
            │
            ├───HomeSection
            │       HomeSection.module.scss
            │       HomeSection.tsx
            │
            ├───ListOfReports
            │       ListOfReports.module.scss
            │       ListOfReports.tsx
            │
            ├───NewReportForm
            │       NewReportForm.module.scss
            │       NewReportForm.tsx
            │
            ├───ProfileDropdown
            │       ProfileDropdown.module.scss
            │       ProfileDropdown.tsx
            │
            └───UsersTable
                    UsersTable.module.scss
                    UsersTable.tsx
│
├── docs/
│   ├── endpoints_draft_txt/          # Черновики API-эндпоинтов
│   └── user_actions_draft/           # Черновики пользовательских сценариев
├── .env.example                      # Пример переменных окружения
├── docker-compose.yml                # PostgreSQL + backend
├── openapi.json                      # OpenAPI-спецификация
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
