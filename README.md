# YACAID — модульный домашний ассистент

Семейный ассистент по дому. Изначально — система видеонаблюдения с AI-детекцией
объектов; сейчас развивается в платформу с несколькими модулями (**безопасность**,
а в перспективе — **финансы**, **здоровье/диета** и др.), объединёнными общим
веб-интерфейсом и единой учётной записью для всех членов семьи.

## Архитектура

Два независимых компонента, соединённых по сети (приватный туннель / интернет):

### `recorder` — «мозги» ассистента

Работает **локально**, на машине рядом с камерами, **без Docker** — обычный Python-
процесс / systemd-сервис. Отвечает за:

- захват RTSP-потоков, детекцию движения и объектов (YOLO/ultralytics), запись по тревоге;
- локальное хранение, объединение и ретеншн отснятого;
- синхронизацию материалов в архив на сервере (`archive_sync`);
- локальный токенизированный control-API (доступен только через приватный туннель —
  Tailscale/WireGuard) — управление камерами (тревога вкл/выкл, фото и запись по запросу);
- **оркестрацию остального умного дома через Home Assistant** — recorder не реализует
  драйверы под каждое устройство, а проксирует команды/состояния в HA по его REST API.

### `archive_server` — UI + БД (витрина для семьи)

Запускается в **Docker** вместе с Postgres. Единая точка входа для всех членов семьи:
логин под персональной учётной записью, общей для всех модулей.

```
archive_server/
  core/      — общая платформа: аутентификация, БД, общий User, шаблоны, нав-меню
  modules/
    security/  — лента тревог, архив записей, проксирование управления камерами
    (finance/, health/ и т.п. — добавляются по тому же шаблону)
  main.py    — собирает приложение из списка модулей (MODULES)
```

Каждый модуль — самодостаточный пакет, который экспортирует свои `routers`
(маршруты FastAPI) и `nav_items` (пункты нижнего меню); общий UI просто
агрегирует их, ничего не зная о конкретных модулях заранее.

**Принцип разделения данных** (важно для многопользовательского режима):
- данные модуля `security` — общие для всей семьи: каждый залогиненный видит одни
  и те же камеры и тревоги (модель `Media` без `user_id`);
- личные данные будущих модулей (финансы, дневник питания и т.п.) должны
  скоупиться по `user_id` — видны только их владельцу. Все члены семьи живут в
  одной базе (`User`), но изоляция обеспечивается на уровне запросов модуля.

## Развёртывание

### A. archive_server + БД (Docker)

Требуется Docker и Docker Compose v2.

```bash
git clone <repo-url>
cd YACAID
cp .env.__EXAMPLE__ .env
```

Заполнить `.env` реальными значениями (сгенерировать секреты можно так:
`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`):

| Переменная | Назначение |
|---|---|
| `POSTGRES_PASSWORD` | пароль БД (пользователь и БД создаются автоматически: `yacaid`/`yacaid_archive`) |
| `ARCHIVE_API_KEY` | секрет, которым `recorder` аутентифицируется при заливке медиа в `/api/media` |
| `SESSION_SECRET` | подпись сессионных cookie — должен быть стабильным между рестартами |
| `CONTROL_BASE_URL` | адрес локального control-API `recorder`'а, доступный только через приватный туннель (например, `http://100.x.x.x:8090`) |
| `CONTROL_API_TOKEN` | токен control-API — тот же, что задан в `cfg.yml`/`cfg.local.yml` recorder'а |
| `COOKIE_SECURE` | `true` в проде (HTTPS); `false` — только для локального HTTP-теста |
| `ARCHIVE_SERVER_PORT` | порт публикации UI на хосте (по умолчанию `8000`) |

Запуск:

```bash
docker compose up -d --build
```

Поднимутся два контейнера:
- `db` — Postgres с данными в volume `db_data`;
- `archive_server` — UI на `http://localhost:${ARCHIVE_SERVER_PORT}` (по умолчанию 8000),
  архив фото/видео — в volume `media_data`.

Оба volume переживают пересоздание контейнеров (`docker compose down` без `-v`).

Логи контейнера: `docker compose logs -f archive_server`.

### B. recorder (без Docker, локально рядом с камерами)

```bash
cd YACAID
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-recorder.txt

cp cfg/cfg.yml.__EXAMPLE__ cfg/cfg.yml
cp cfg/cfg.local.yml.__EXAMPLE__ cfg/cfg.local.yml   # сюда — реальные секреты, файл в .gitignore
```

Что заполнить в `cfg.yml` / `cfg.local.yml` (последний полностью перекрывает первый
и не должен попадать в git — храните в нём пароли и токены):

- **`stream_cfg`** — RTSP-адреса камер (детектор/основной поток), пороги движения
  и минимальная площадь срабатывания AI;
- **`archive_sync`** — `base_url` архив-сервера и `api_key` (= `ARCHIVE_API_KEY` из `.env` сервера);
- **`control`** — `host`/`port` локального control-API и `token` (= `CONTROL_API_TOKEN`
  из `.env` сервера); пустой токен отключает control-API;
- **`home_assistant`** *(опционально)* — адрес HA-инстанса и долгоживущий токен, см. ниже.

Все секреты можно также передавать через переменные окружения
(`ARCHIVE_BASE_URL`, `ARCHIVE_API_KEY`, `CONTROL_API_TOKEN`,
`HOME_ASSISTANT_URL`, `HOME_ASSISTANT_TOKEN`) — они имеют приоритет над `cfg.*.yml`.

Запуск (в форграунде, для проверки):

```bash
python3 run_recorder.py
```

Для постоянной работы — оформить как systemd-сервис, например:

```ini
# /etc/systemd/system/yacaid-recorder.service
[Unit]
Description=YACAID recorder
After=network-online.target

[Service]
WorkingDirectory=/opt/YACAID
ExecStart=/opt/YACAID/.venv/bin/python run_recorder.py
Restart=always
User=yacaid

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now yacaid-recorder
```

> Control-API слушает по умолчанию на `127.0.0.1` — доступ к нему с архив-сервера
> организуется через приватный туннель (Tailscale/WireGuard), а не публично в интернет.

## Управление пользователями

Учётная запись общая для всей семьи и для всех модулей сразу: одни и те же
логин/пароль открывают доступ ко всему UI (а уже какие данные показывать —
общие или личные — решает каждый модуль).

Создать нового пользователя или сменить пароль существующему — выполнить внутри
контейнера `archive_server`:

```bash
docker compose exec archive_server python -m archive_server.core.create_user <username> <password>
```

Команда идемпотентна: если пользователь с таким именем уже есть — обновит ему
пароль; если нет — создаст. Логины успешных/неуспешных входов и выходов пишутся
в `logs/auth.log` (см. «Логирование»).

Удаление пользователей через CLI пока не реализовано; при необходимости можно
сделать это напрямую в БД:

```bash
docker compose exec db psql -U yacaid -d yacaid_archive -c "DELETE FROM users WHERE username = '<username>';"
```

## Home Assistant — оркестрация умного дома

`recorder` может управлять остальными устройствами дома (свет, розетки, датчики
и т.д.), не реализуя собственных драйверов — он проксирует команды и чтение
состояний в Home Assistant через его REST API:

1. Поднять Home Assistant в локальной сети (отдельным сервисом — recorder его не
   запускает и не зависит от его рантайма; HA можно держать хоть в Docker, хоть нативно).
2. В профиле HA создать **Long-Lived Access Token**.
3. Заполнить в `cfg.local.yml`:
   ```yaml
   home_assistant:
     base_url: "http://homeassistant.local:8123"
     token: "REPLACE_WITH_REAL_LONG_LIVED_ACCESS_TOKEN"
   ```
4. После перезапуска `recorder` локальный control-API (за тем же `CONTROL_API_TOKEN`,
   что и команды камер) начнёт отвечать на:
   - `POST /ha/service/{domain}/{service}` — вызов произвольного сервиса HA
     (например, `light/turn_on` с телом `{"entity_id": "light.hallway", "brightness_pct": 80}`);
   - `GET /ha/state/{entity_id}` — состояние конкретного устройства;
   - `GET /ha/states` — состояния всех устройств.

Если `base_url` не задан — интеграция выключена, и `/ha/...` отвечает `503 Home
Assistant не сконфигурирован`.

> На стороне UI пока нет модуля «Умный дом» и проксирующих маршрутов к `/ha/...`
> (по аналогии с существующим `/control/{camera}/{action}` для камер) — это
> следующий шаг, когда понадобится управлять устройствами прямо из семейного UI.

## Логирование

Каждый процесс (по камере, `file_handler`, `control-API`, `archive_server`,
`auth`, `ingest`, `retention` и т.д.) пишет в свой файл `logs/<имя>.log` с
ежедневной ротацией; записи старше **10 дней** удаляются автоматически
(`logger_setup.get_logger`, общий для `recorder` и `archive_server`).

Используемые уровни:
- **DEBUG/INFO** — штатная работа (запуск процессов, обнаружения, синхронизация,
  успешные входы/выходы из UI и т.п.);
- **WARNING** — нештатные, но не критичные ситуации (неудачная попытка входа,
  отключённый control-API, обрыв кадра);
- **ERROR/CRITICAL/EXCEPTION** — сбои, требующие внимания (недоступность
  Home Assistant/архив-сервера, падение процесса камеры и т.п.).

## Добавление нового модуля (например, «Финансы»)

1. Создать пакет `archive_server/modules/finance/`.
2. Описать модели в `models.py`, наследуя `Base` из `archive_server.core.db`.
   Для **личных** данных обязательно добавить колонку `user_id` (FK на `User`)
   и фильтровать по ней во всех запросах — в отличие от `security`, где данные общие.
3. Описать маршруты (`routes_ui.py` и т.д.), используя общий `templates` из
   `archive_server.core.templating`; шаблоны класть в `archive_server/templates/finance/...`
   (наследуя общий `base.html`).
4. В `__init__.py` модуля экспортировать `routers` (список `APIRouter`) и
   `nav_items` (список `NavItem` из `archive_server.core.nav`).
5. Добавить модуль в список `MODULES` в `archive_server/main.py` — он автоматически
   подключит маршруты и пункт меню.
