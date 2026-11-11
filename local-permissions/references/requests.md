# Задания локального запускателя

Схема соответствует существующей инсталляции `products/local-permissions/run.py`. При расхождении сверяйся с текущим кодом и README продукта; не добавляй неизвестные поля. Все примеры — данные для stdin submit.py, не команды shell. Пути с `SESSION`/`NOTE` замени существующими путями выбранной задачи.

## Dion

```json
{"operation":"dion","action":"status"}
{"operation":"dion","action":"devices"}
{"operation":"dion","action":"start","title":"Название встречи"}
{"operation":"dion","action":"stop"}
{"operation":"dion","action":"process","session":"C:/AI/Large files/Dion/SESSION"}
{"operation":"dion","action":"summarize","transcript":"C:/AI/AI Native/meetings/Dion/NOTE.md"}
{"operation":"dion","action":"finalize-minutes","handoff":"C:/AI/Large files/Dion/SESSION/minutes-handoff.json","draft":"C:/AI/Large files/Dion/SESSION/minutes-draft.md"}
```

У start необязательные `speaker` и `mic` — целочисленные индексы реальных устройств; `meeting_journal` — существующий каталог внутри `C:/AI/Tools/dion-speaker-helper/runtime/journals`. Несколько пересекающихся встреч требуют явного выбора. Process использует browser-имена и протокол с ассистентом; этот шлюз не переключает движок или режим диаризации. Handoff и Markdown-draft должны принадлежать одной сессии.

## Почта

```json
{"operation":"mail","action":"search","text":"тема поиска","all_folders":true,"limit":20}
{"operation":"mail","action":"read","folder":"INBOX","uid":"123"}
{"operation":"mail","action":"folders"}
{"operation":"mail","action":"check"}
{"operation":"mail","action":"export","sender":"sender@example.com","subjects":["Тема"],"destination":"C:/AI/AI Native/output/mail/selection"}
```

Search: необязательные `text`, `subject`, `sender`, `since`, `before`, `limit` (1–100), `folders` (массив идентификаторов) либо `all_folders` (boolean). Даты — YYYY-MM-DD, since включительно, before исключительно. Без выбора папок поиск идёт в INBOX. Для read используй идентификатор папки из folders и числовой UID строкой. Export: точный sender, от 1 до 30 строк subjects, destination — подпапка output вне private. Установка учётных данных и отправка писем не поддерживаются.

## Открытие и аудит

Отдельная команда для правил текущего пользователя:

```json
{"operation":"rules","action":"open","name":"local"}
{"operation":"rules","action":"open","name":"default"}
```

Открывает в Блокноте только `~/.codex/rules/local-operations.rules` или `default.rules`. Произвольные пути, изменение и публикация правил не поддерживаются; файл должен существовать без перенаправления ссылкой.

```json
{"operation":"open","target":"C:/AI/AI Native/meetings/Dion/NOTE.md","anchor":"^t-00-00-12"}
{"operation":"open","target":"https://example.com/"}
{"operation":"audit","check":"skills-static"}
```

Open принимает существующие документы разрешённых расширений внутри хранилища или `C:/AI/Large files/documents`, либо HTTP(S) URL без встроенных учётных данных. `anchor` — только Obsidian block ID для Markdown-заметки в хранилище. Private, скрытые пути, UNC, ADS и исполняемые файлы отвергаются.

Audit check: `vault`, `skills-static`, `skills-tests`, `skills-full`. Статический, выбранный и полный режимы проверяют разные вещи; читай README соответствующего аудитора перед выбором.

## Тесты и диагностика

```json
{"operation":"tests","suite":"permissions"}
{"operation":"diagnostic","component":"dion"}
{"operation":"diagnostic","component":"syncthing"}
{"operation":"diagnostic","component":"archive"}
{"operation":"github","action":"auth"}
{"operation":"github","action":"refs","repo":"skills"}
{"operation":"github","action":"ci","repo":"dion"}
{"operation":"link","url":"https://github.com/Vaakom/local-permissions"}
```

Tests suite: permissions, dion-helper (только Python), archive, skill-health. Github repo: skills, dion, permissions — три известных репозитория; action только auth/refs/ci, без записи. Diagnostic: только локальные конфиги/метаданные Dion, GET status/ignores фиксированной папки Syncthing, status.json архиватора. Не выдавай совпадение конфигов за проверенный фактический ID Chrome, свежий файл за сохранённые имена, старый статус архиватора за живой процесс.

Link проверяет публичный HTTP(S), включая каждый редирект; локальные IP, credentials в URL и нестандартные порты запрещены. Не передавай URL с секретами. Проверка не использует авторизацию браузера, поэтому при 403/антиботе попробуй другой разрешённый способ проверки страницы. Эти операции не ремонтируют конфигурацию, не запускают сервисы, не удаляют данные и не публикуют ничего.
