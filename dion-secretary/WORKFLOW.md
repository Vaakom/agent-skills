# Dion Secretary — схема работы

```mermaid
flowchart TB
    A(["Команда пользователя · чат Codex"]) --> B{"Действие · Codex"}
    B -->|Запись| C["Проверка состояния и устройств<br/>secretary.py · status / devices"]
    C --> D{"Запись уже идёт?<br/>secretary.py"}
    D -->|Да| E["Сообщить состояние<br/>Codex + secretary.py status"]
    D -->|Нет| F["Записать микрофон + системный звук<br/>secretary.py start · PyAudioWPatch / WASAPI"]
    F --> G["Проверить обе дорожки и журнал Dion<br/>secretary.py status"]
    G --> H["Остановить и сохранить WAV<br/>secretary.py stop / meeting_autostop.py"]
    B -->|Остановка| H
    H --> I{"Запрошена обработка?<br/>Codex"}
    I -->|Нет| Z(["Аудио сохранено"])
    I -->|Да| J["Распознать речь выбранным движком<br/>secretary.py process · настроенный ASR<br/>gigaam_adapter.py / gigaam_worker.py"]
    B -->|Готовая запись| J
    J --> K["Привязать имена из журнала Dion<br/>dion-speaker-helper · auto_journals.py / speaker_names.py"]
    K --> L["Экспортировать стенограмму и временные метки<br/>secretary.py process"]
    L --> M{"Подготовка протокола<br/>Codex"}
    M -->|По умолчанию| N["Прочитать полную стенограмму → черновик<br/>Codex"]
    N --> O["Проверить источник и сохранить протокол<br/>secretary.py finalize-minutes · minutes_handoff.py"]
    M -->|Явный запрос локальной модели| P["Выделить и проверить факты → локальный черновик<br/>local_minutes.py / fact_context.py<br/>Ollama · qwen3.5:9b по умолчанию"]
    O --> Q(["Ссылки на результаты · чат Codex"])
    P --> Q

    classDef action fill:#eef4ff,stroke:#7597ce,color:#172e50,rx:10,ry:10;
    classDef choice fill:#fff5db,stroke:#d6ad49,color:#584317;
    classDef terminal fill:#e8f5ed,stroke:#68a47d,color:#204d30;
    class C,E,F,G,H,J,K,L,N,O,P action;
    class B,D,I,M choice;
    class A,Z,Q terminal;
```

- Автоостановка: закрытие привязанного окна встречи или всего Chrome. Закрытие вкладки и признаки окончания встречи дают только предупреждение.
- После старта проверяются работа аудиопроцесса, поступление данных в обе дорожки и свежесть журнала Dion. Недоступный журнал не блокирует запись; имена остаются неподтверждёнными.
- Запись сохраняется независимо от обработки. Напоминания: через 60 минут, затем каждые 30 минут — `recording_reminders.py`.
- При ошибке Codex сообщает этап и известную причину; частичные записи и готовая стенограмма сохраняются. Движок распознавания и способ подготовки протокола автоматически не подменяются.
- Whisper и разделение по голосам включаются только по явному запросу. Основная схема показывает режим имён из журнала браузера.

Источник: [SKILL.md](SKILL.md). Схема сверена с инструкцией 2026-10-27.
- Выходные каталоги задаются параметрами sessions и notes. Настройки компьютера находятся в исключённых из Git config.json и references/local.md.
- GigaAM-v3 использует gigaam_worker.py, Whisper — faster-whisper. Движок задаётся настройками; автоматического переключения нет.
