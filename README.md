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
├── backend/                                      # FastAPI backend
│   ├── Dockerfile                               # Docker-образ backend-сервиса
│   ├── README.md                                # Черновое описание структуры backend
│   ├── requirements.txt                         # Python-зависимости backend
│   └── app/                                     # Основной код backend-приложения
│       ├── main.py                              # Точка входа FastAPI, подключение роутеров
│       ├── api/                                 # API-слой приложения
│       │   ├── dependencies.py                  # Общие зависимости API, авторизация и проверка ролей
│       │   └── v1/                              # Версия API v1
│       │       ├── admin.py                     # Эндпоинты администратора: пользователи, шаблоны, протоколы, метрики
│       │       ├── llm.py                       # Создание отчета через LLM-пайплайн
│       │       ├── reports.py                   # Получение, генерация, скачивание и оценка отчетов
│       │       └── users.py                     # Авторизация пользователей
│       ├── core/                                # Базовая инфраструктура backend
│       │   ├── config.py                        # Настройки из .env
│       │   ├── database.py                      # Async SQLAlchemy engine и сессии
│       │   ├── role.py                          # Роли пользователей
│       │   ├── security.py                      # JWT и пароли
│       │   ├── celery_app.py                    # Конфигурация Celery для фоновых задач
│       │   └── rag/                             # RAG-модуль для работы с медицинской базой знаний
│       │       ├── chunker.py                   # Функции чанкования текста
│       │       ├── embedder.py                  # Эмбеддинг-кодирование текстов
│       │       ├── vector_store.py              # Организация векторного хранилища
│       │       ├── bm25_index.py                # Индекс BM25 для полнотекстового поиска
│       │       ├── graph_builder.py             # Построение графа знаний
│       │       ├── retriever.py                 # Гибридный поиск и графовый RAG
│       │       └── kb_manager.py                # Управление базой знаний
│       ├── models/                              # SQLAlchemy-модели БД
│       │   ├── report.py                        # SQLAlchemy-модель отчета
│       │   ├── user.py                          # SQLAlchemy-модели пользователя и организации
│       │   ├── clinical_protocols.py            # SQLAlchemy-модель клинического протокола
│       │   ├── llm_calls.py                     # SQLAlchemy-модель вызовов LLM
│       │   └── report_templates.py              # SQLAlchemy-модель шаблонов отчетов
│       ├── schemas/                             # Pydantic-схемы запросов и ответов
│       │   ├── admin.py                         # Pydantic-схемы администратора
│       │   ├── report.py                        # Pydantic-схемы отчетов
│       │   ├── llm.py                           # Схемы для получения ответа и отправления запроса к LLM
│       │   ├── user.py                          # Pydantic-схемы авторизации
│       │   ├── clinical_protocol.py             # Pydantic-схемы клинических протоколов
│       │   ├── llm_call.py                      # Pydantic-схемы LLM-вызовов
│       │   └── report_template.py               # Pydantic-схемы шаблонов отчетов
│       ├── services/                            # Сервисный слой с бизнес-логикой
│       │   ├── admin_service.py                 # Бизнес-логика администратора
│       │   ├── bootstrap_service.py             # Первичная инициализация данных
│       │   ├── llm_service.py                   # Обработка запроса к LLM
│       │   ├── ml_engine.py                     # Отправление запроса к LLM и подтягивание контекста
│       │   ├── storage_service.py               # Работа с файловым хранилищем MinIO
│       │   ├── report_service.py                # Бизнес-логика отчетов
│       │   └── user_service.py                  # Бизнес-логика пользователей
│       ├── tasks/                               # Фоновые задачи Celery
│       │   ├── report_tasks.py                  # Фоновая генерация отчетов
│       │   └── __init__.py                      # Инициализация пакета tasks
│       └── utils/                               # Вспомогательные утилиты backend
│           ├── file_handler.py                  # Обработка ZIP, CSV и JSON
│           ├── html_report_generator.py         # Генерация HTML-версии отчета
│           └── pdf_generator.py                 # Генерация PDF из HTML
├── clinical_protocols/                          # Клинические протоколы
│   ├── 158-157-1-PB.pdf                         # PDF-файл клинического протокола
│   ├── ...                                      # Остальные PDF-файлы протоколов
│   └── Рекомендации_торакоабдоминальная_аорта.pdf # Рекомендации по торакоабдоминальной аорте
├── docs/                                        # Артефакты формирования клиентского пути
│   ├── endpoints_draft_txt/                     # Черновики API-эндпоинтов
│   │   └── endpoints_api_for_user.txt           # Описание API для пользовательских сценариев
│   └── user_actions_draft/                      # Черновики пользовательских сценариев
│       └── 1.pdf                                # PDF-схема или описание пользовательского пути
└── frontend/                                    # React + Vite frontend
    ├── .gitignore                               # Исключения Git для frontend
    ├── Dockerfile                               # Docker-образ frontend-сервиса
    ├── eslint.config.js                         # Конфигурация ESLint
    ├── index.html                               # HTML-точка входа Vite
    ├── package-lock.json                        # Зафиксированные версии npm-зависимостей
    ├── package.json                             # Скрипты и зависимости frontend
    ├── README.md                                # Описание frontend-проекта
    ├── tsconfig.app.json                        # TypeScript-настройки приложения
    ├── tsconfig.json                            # Общая TypeScript-конфигурация
    ├── tsconfig.node.json                       # TypeScript-настройки для Node/Vite
    ├── vite.config.ts                           # Конфигурация Vite
    └── src/                                     # Исходный код React-приложения
        ├── App.tsx                              # Корневой компонент приложения
        ├── index.css                            # Глобальные CSS-стили
        ├── main.tsx                             # Точка входа React-приложения
        ├── app/                                 # Инициализация приложения, роутинг, layout и стили
        │   ├── layouts/                         # Layout-компоненты приложения
        │   │   └── AdminLayout/                 # Общий layout административного раздела
        │   │       ├── AdminLayout.module.scss  # Стили административного layout
        │   │       └── AdminLayout.tsx          # Обертка admin-страниц с header/sidebar
        │   ├── router/                          # Роутинг приложения
        │   │   ├── AppRouter.tsx                # Основные маршруты frontend
        │   │   └── ProtectedRoute.tsx           # Защита маршрутов по авторизации и ролям
        │   └── styles/                          # Общие стили приложения
        │       └── index.scss                   # SCSS-точка подключения общих стилей
        ├── entities/                            # Доменные сущности frontend
        │   ├── report/                          # Сущность отчета
        │   │   └── model/                       # Модель и типы отчета
        │   │       └── types.ts                 # TypeScript-типы отчета
        │   └── user/                            # Сущность пользователя
        │       └── model/                       # Модель и типы пользователя
        │           └── types.ts                 # TypeScript-типы пользователя
        ├── features/                            # Пользовательские функции и модальные окна
        │   ├── change-password/                 # Фича смены пароля
        │   │   ├── ChangePasswordModal.module.scss # Стили модального окна смены пароля
        │   │   └── ChangePasswordModal.tsx      # Модальное окно смены пароля
        │   ├── report-review/                   # Фича оценки отчета
        │   │   ├── ReportReview.module.scss     # Стили блока оценки отчета
        │   │   └── ReportReview.tsx             # Компонент оценки и комментария к отчету
        │   ├── restore-password/                # Фича восстановления пароля
        │   │   ├── RestorePasswordModal.module.scss # Стили модального окна восстановления пароля
        │   │   └── RestorePasswordModal.tsx     # Модальное окно восстановления пароля
        │   ├── user-form-modal/                 # Фича создания и редактирования пользователя
        │   │   ├── UserFormModal.module.scss    # Стили формы пользователя
        │   │   └── UserFormModal.tsx            # Модальное окно формы пользователя
        │   └── view-user-modal/                 # Фича просмотра информации о пользователе
        │       ├── UserInfoModal.module.scss    # Стили модального окна пользователя
        │       └── UserInfoModal.tsx            # Модальное окно с данными пользователя
        ├── pages/                               # Страницы приложения
        │   ├── AdminDashboardPage/              # Главная страница администратора
        │   │   ├── AdminDashboardPage.module.scss # Стили страницы статистики администратора
        │   │   └── AdminDashboardPage.tsx       # Дашборд с метриками качества и ошибок
        │   ├── AdminProtocolsPage/              # Страница управления клиническими протоколами
        │   │   ├── AdminProtocolsPage.module.scss # Стили страницы протоколов
        │   │   └── AdminProtocolsPage.tsx       # Загрузка, поиск и список клинических протоколов
        │   ├── AdminTemplatesPage/              # Страница управления шаблонами отчетов
        │   │   ├── AdminTemplatesPage.module.scss # Стили страницы шаблонов
        │   │   └── AdminTemplatesPage.tsx       # Загрузка и просмотр версий шаблонов отчетов
        │   ├── AdminUsersPage/                  # Страница управления пользователями
        │   │   ├── AdminUsersPage.module.scss   # Стили страницы пользователей
        │   │   └── AdminUsersPage.tsx           # Список, создание и редактирование пользователей
        │   ├── LoginPage/                       # Страница входа
        │   │   ├── LoginPage.module.scss        # Стили страницы входа
        │   │   └── LoginPage.tsx                # Форма авторизации пользователя
        │   └── MainPage/                        # Главная пользовательская страница
        │       ├── MainPage.module.scss         # Стили главной страницы
        │       └── MainPage.tsx                 # Пользовательский экран с отчетами и формой создания
        ├── shared/                              # Переиспользуемый общий код
        │   ├── api/                             # API-клиенты frontend
        │   │   ├── adminApi.ts                  # Запросы к admin API
        │   │   ├── apiClient.ts                 # Общий HTTP-клиент и базовая настройка запросов
        │   │   ├── authApi.ts                   # Запросы авторизации
        │   │   ├── reportApi.ts                 # Запросы для работы с отчетами
        │   │   └── userApi.ts                   # Запросы для работы с пользователем
        │   ├── assets/                          # Статические ресурсы frontend
        │   │   ├── fonts/                       # Подключаемые шрифты
        │   │   │   ├── DaysOne/                 # Шрифт DaysOne
        │   │   │   │   └── DaysOne-Regular.ttf  # Regular-начертание DaysOne
        │   │   │   ├── OpenSans/                # Шрифт OpenSans
        │   │   │   │   ├── OpenSans-Bold.ttf    # Bold-начертание OpenSans
        │   │   │   │   ├── OpenSans-Light.ttf   # Light-начертание OpenSans
        │   │   │   │   ├── OpenSans-Medium.ttf  # Medium-начертание OpenSans
        │   │   │   │   ├── OpenSans-Regular.ttf # Regular-начертание OpenSans
        │   │   │   │   └── OpenSans-SemiBold.ttf # SemiBold-начертание OpenSans
        │   │   │   └── ViaodaLibre/             # Шрифт ViaodaLibre
        │   │   │       └── ViaodaLibre-Regular.ttf # Regular-начертание ViaodaLibre
        │   │   ├── icons/                       # SVG-иконки интерфейса
        │   │   │   ├── accountIcon.svg          # Иконка аккаунта
        │   │   │   ├── addIcon.svg              # Иконка добавления
        │   │   │   ├── crossIcon.svg            # Иконка закрытия
        │   │   │   ├── CTReport.svg             # Иконка КТ-отчета
        │   │   │   ├── deleteIcon.svg           # Иконка удаления
        │   │   │   ├── doorIcon.svg             # Иконка двери/выхода
        │   │   │   ├── downloadIcon.svg         # Иконка скачивания
        │   │   │   ├── editIcon.svg             # Иконка редактирования
        │   │   │   ├── exitIcon.svg             # Иконка выхода
        │   │   │   ├── eyeCloseIcon.svg         # Иконка скрытого пароля
        │   │   │   ├── eyeIcon.svg              # Иконка показа пароля
        │   │   │   ├── fileBlueIcon.svg         # Синяя иконка файла
        │   │   │   ├── fileIcon.svg             # Иконка файла
        │   │   │   ├── heartLogoIcon.svg        # Иконка логотипа с сердцем
        │   │   │   ├── homeIcon.svg             # Иконка главной страницы
        │   │   │   ├── infoIcon.svg             # Иконка информации
        │   │   │   ├── lockIcon.svg             # Иконка замка/пароля
        │   │   │   ├── logoIcon.svg             # Основной логотип
        │   │   │   ├── logOuIcont.svg           # Иконка выхода из аккаунта
        │   │   │   ├── openUserIcon.svg         # Иконка открытия карточки пользователя
        │   │   │   ├── searchIcon.svg           # Иконка поиска
        │   │   │   ├── starEmptyIcon.svg        # Пустая звезда для оценки
        │   │   │   ├── starFullIcon.svg         # Заполненная звезда для оценки
        │   │   │   ├── tsconfig.app.json        # Лишний/ошибочно попавший файл конфигурации среди иконок
        │   │   │   ├── userIcon.svg             # Иконка пользователя
        │   │   │   └── userLogoW.svg            # Белая версия пользовательского логотипа
        │   │   └── images/                      # Изображения интерфейса
        │   │       └── bgHomePage.png           # Фоновое изображение главной страницы
        │   ├── lib/                             # Общие frontend-утилиты
        │   │   ├── jwt.ts                       # Работа с JWT на клиенте
        │   │   └── tokenStorage.ts              # Хранение и получение токена авторизации
        │   └── ui/                              # Переиспользуемые UI-компоненты
        │       ├── Button/                      # Компонент кнопки
        │       │   ├── Button.module.scss       # Стили кнопки
        │       │   └── Button.tsx               # UI-компонент Button
        │       ├── Dropdown/                    # Компонент выпадающего списка
        │       │   ├── Dropdown.module.scss     # Стили Dropdown
        │       │   └── Dropdown.tsx             # UI-компонент Dropdown
        │       ├── FileInput/                   # Компонент загрузки файлов
        │       │   ├── FileInput.module.scss    # Стили FileInput
        │       │   └── FileInput.tsx            # UI-компонент выбора файлов
        │       ├── Input/                       # Компонент текстового поля
        │       │   ├── Input.module.scss        # Стили Input
        │       │   └── Input.tsx                # UI-компонент Input
        │       ├── Modal/                       # Компонент модального окна
        │       │   ├── Modal.module.scss        # Стили Modal
        │       │   └── Modal.tsx                # UI-компонент Modal
        │       ├── Radio/                       # Компонент radio-переключателя
        │       │   ├── Radio.module.scss        # Стили Radio
        │       │   └── Radio.tsx                # UI-компонент Radio
        │       └── SearchBar/                   # Компонент поиска
        │           ├── SearchBar.module.scss    # Стили SearchBar
        │           └── SearchBar.tsx            # UI-компонент строки поиска
        └── widgets/                             # Крупные UI-блоки страниц
            ├── AdminHeader/                     # Верхняя панель admin-раздела
            │   ├── AdminHeader.module.scss      # Стили AdminHeader
            │   └── AdminHeader.tsx              # Компонент верхней панели администратора
            ├── AdminSidebar/                    # Боковое меню admin-раздела
            │   ├── AdminSidebar.module.scss     # Стили AdminSidebar
            │   └── AdminSidebar.tsx             # Компонент боковой навигации администратора
            ├── AdminStats/                      # Виджет статистики администратора
            │   ├── AdminStats.module.scss       # Стили AdminStats
            │   └── AdminStats.tsx               # Компонент карточек статистики
            ├── AdminUsersToolbar/               # Панель действий на странице пользователей
            │   ├── AdminUsersToolbar.module.scss # Стили панели пользователей
            │   └── AdminUsersToolbar.tsx        # Поиск и действия над пользователями
            ├── Header/                          # Основной header пользовательской части
            │   ├── Header.module.scss           # Стили Header
            │   └── Header.tsx                   # Компонент верхней панели пользователя
            ├── HomeSection/                     # Главный информационный блок пользовательской страницы
            │   ├── HomeSection.module.scss      # Стили HomeSection
            │   └── HomeSection.tsx              # Компонент домашнего/приветственного блока
            ├── ListOfReports/                   # Список отчетов пользователя
            │   ├── ListOfReports.module.scss    # Стили списка отчетов
            │   └── ListOfReports.tsx            # Компонент отображения отчетов
            ├── NewReportForm/                   # Форма создания нового отчета
            │   ├── NewReportForm.module.scss    # Стили формы нового отчета
            │   └── NewReportForm.tsx            # Компонент ввода данных для генерации отчета
            ├── ProfileDropdown/                 # Выпадающее меню профиля
            │   ├── ProfileDropdown.module.scss  # Стили меню профиля
            │   └── ProfileDropdown.tsx          # Компонент действий профиля пользователя
            └── UsersTable/                      # Таблица пользователей в admin-разделе
                ├── UsersTable.module.scss       # Стили таблицы пользователей
                └── UsersTable.tsx               # Компонент таблицы пользователей
├── .env.example                                 # Пример переменных окружения
├── docker-compose.yml                           # Docker Compose для запуска сервисов проекта
├── nginx.conf                                   # Конфигурация nginx для frontend/backend
├── openapi.json                                 # OpenAPI-спецификация backend API
└── Проект Клиники Пирогова.txt                  # Текстовое описание проекта

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
