# Business Skill Issue

Скилл для разбора бизнес-запроса: собирает вопросы и ответы, фиксирует версии требований, ведёт ход работы по событиям и помогает понять, какой шаг нужен дальше. Подходит для работы с требованиями от первичного запроса до приёмки. Содержимое проекта хранится в ваших локальных файлах; скилл сам по себе ничего не публикует.

## Установка

**Через skill-installer.** Попросите Codex: «Установи скилл из `https://github.com/aedixxe/Business-Skill-Issue/tree/main/skills/business-skill-issue` через skill-installer». Для CLI можно запустить:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo aedixxe/Business-Skill-Issue \
  --path skills/business-skill-issue
```

Скилл станет доступен в следующем сообщении Codex после установки.

**Из ZIP-релиза.** Скачайте `Business-Skill-Issue-v0.1.0.zip` со страницы [Releases](https://github.com/aedixxe/Business-Skill-Issue/releases), распакуйте папку `business-skill-issue` в `~/.codex/skills/` (или `$CODEX_HOME/skills/`). Внутри неё должен лежать `SKILL.md`. Если папка уже существует, сначала сохраните свои изменения и обновите её вручную.

## Быстрый старт

Напишите Codex: «Используй Business Skill Issue. Вот описание задачи: … Разбери запрос и составь вопросы к заказчику». Можно начать с вопроса «Business Skill Issue, что ты умеешь?» без файлов и выбрать нужный режим работы.

По ходу работы агент обновляет `pipeline.json` — состояние этапов, события, версии документов и согласования — и пересобирает локальную страницу. Обычно вручную редактировать JSON не требуется.

Чтобы посмотреть демо из корня клонированного репозитория, запустите:

```bash
python3 skills/business-skill-issue/scripts/render_pipeline.py \
  --input skills/business-skill-issue/examples/demo-pipeline.json \
  --output skills/business-skill-issue/examples/demo-pipeline.html
```

Откройте [готовое демо](skills/business-skill-issue/examples/demo-pipeline.html) прямо из файловой системы: сервер, CDN и сторонние Python-библиотеки не нужны. В демо версия 1 согласована, а новая рабочая версия 2 ещё ждёт ответа и отдельного решения. Документы `.md` и `.txt` до 256 КиБ можно читать внутри страницы. Для своего проекта храните `pipeline.json` и его документы в одной папке или её подпапках: локальные пути в JSON разрешаются относительно файла JSON.

После установки скилла команда для демо короче:

```bash
cd ~/.codex/skills/business-skill-issue
python3 scripts/render_pipeline.py --input examples/demo-pipeline.json --output examples/demo-pipeline.html
```

Формат JSON и правила времени/согласований описаны в [справочнике](skills/business-skill-issue/references/pipeline.md). Демо полностью вымышленное.

## Разработка

Требуется Python 3.9+ из стандартной библиотеки. Проверка renderer:

```bash
python3 -m unittest discover -s tests -v
```

Релизный ZIP собирается из фиксированного списка публичных файлов; `dist/`, `.qa/`, тесты и любые локальные документы проекта в него не входят:

```bash
python3 build_release.py --version v0.1.0
```

Лицензия: [MIT](LICENSE).
