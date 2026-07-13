# Перезамер качества квизов — 2026-07-15

Восстановление утерянной папки `reports/quiz_quality_baseline_2026-07-04/`
(TASK_STAGE1_v4.md, пункт 5 сессии 4). Оригинал не найден ни на одной
машине, ни на сервере — считается утерянным безвозвратно. Эта папка не
воспроизводит точные исторические цифры 27%/50% (сырых данных под ними
больше нет), а строит новое, честное ПАРНОЕ сравнение: старый и новый
пайплайн, одни и те же 10 тем, один день, один движок (GigaChat).

## Файлы

- `generate_test_lessons.py` — генерирует уроки ОБОИМИ пайплайнами
  (старый монолитный `_build_prompt` из `lesson_generator.py`, новый
  `generate_lesson_content -> generate_questions -> verify_and_repair_questions`
  из `lesson_pipeline.py`) на 10 темах из таблицы «Результат по каждому
  уроку» в CLAUDE.md.
- `check_lessons.py` — автоскоринг: настоящий `validate_lesson()` +
  кодовая проверка арифметики quiz (`check_question_arithmetic` из
  `lesson_pipeline.py`, с учётом порядка операций и скобок).
- `lessons_out_old/`, `lessons_out_new/` — сырые сгенерированные уроки
  (10 + 10, JSON).
- `check_output_old.json`, `check_output_new.json` — результат автоскоринга.

## Результат автоскоринга (2026-07-15, GigaChat, temperature по умолчанию)

| Пайплайн | Уроков с браком | Вопросов quiz | Дефектных quiz (авто) |
|---|---|---|---|
| Старый (монолитный) | 6/10 (60%) | 26 | 1 (4%) |
| Новый (generator→verifier) | 0/10 (0%) | 17 | 0 (0%) |

**Это НЕ финальная цифра.** Автоскоринг ловит структурные ошибки
(`validate_lesson()`) и арифметику, вычислимую кодом. Он НЕ ловит
неарифметические дефекты quiz — например, вопрос с двумя одновременно
верными вариантами или без единственного верного (см. методологию ручной
сверки в CLAUDE.md, раздел «БАЗОВАЯ МЕТРИКА КАЧЕСТВА КВИЗОВ»). Именно
такие дефекты давали большую часть исторических 27%: 4% автоскоринга для
старого пайплайна — это нижняя граница, не полная цифра. Ручная вычитка
`lessons_out_old/`/`lessons_out_new/` — следующий шаг (что в оригинальном
плане было сессией 6, здесь — часть «Перезамера» в TASK_STAGE1_v4.md).

Дополнительно найдено и исправлено по ходу генерации (см. журнал сессии 4
в CLAUDE.md): промпт вызова 2 указывал `feedback_correct`/`feedback_wrong`/
`hint` как обязательные только в примере для `multiple_choice` — модель
следовала примеру, а не общему текстовому правилу, и пропускала эти поля
для `fill_blank`/`match_pairs`/`sort_items`. Пример JSON в промпте расширен
на все 4 типа шагов — после этого новый пайплайн ушёл с 100% до 0% брака
по `validate_lesson()`.

## Как запустить заново

Скрипты рассчитаны на запуск ВНУТРИ backend-контейнера (там уже есть
креды GigaChat через docker-compose/.env, не нужно читать .env руками,
как в версии 2026-07-04):

```bash
docker cp generate_test_lessons.py kids-platform-backend-1:/app/generate_test_lessons.py
docker cp check_lessons.py kids-platform-backend-1:/app/check_lessons.py
docker exec -u root -w /app kids-platform-backend-1 python generate_test_lessons.py
docker exec -u root -w /app kids-platform-backend-1 python check_lessons.py
docker cp kids-platform-backend-1:/app/lessons_out_old ./lessons_out_old
docker cp kids-platform-backend-1:/app/lessons_out_new ./lessons_out_new
docker cp kids-platform-backend-1:/app/check_output_old.json ./check_output_old.json
docker cp kids-platform-backend-1:/app/check_output_new.json ./check_output_new.json
```

`-u root` нужен, т.к. `/app` в контейнере принадлежит root, а контейнер по
умолчанию исполняет от `appuser` без прав записи туда.
