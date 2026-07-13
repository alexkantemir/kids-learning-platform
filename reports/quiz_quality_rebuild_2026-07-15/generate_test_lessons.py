"""
generate_test_lessons.py — генерация тестовых уроков ОБОИМИ пайплайнами
(старый монолитный и новый generator->verifier) на одних и тех же 10 темах,
для парного перезамера (TASK_STAGE1_v4.md, пункт 5 сессии 4).

Оригинальная папка reports/quiz_quality_baseline_2026-07-04/ (базовая
метрика 27%/50%) утеряна безвозвратно — не найдена ни на одной машине, ни
на сервере (см. CLAUDE.md). Эта папка не пытается её точно воспроизвести,
а строит НОВУЮ пару данных для честного парного сравнения старый vs новый
пайплайн в один день, на одном движке (GigaChat), на тех же 10 темах,
взятых из таблицы "Результат по каждому уроку" в CLAUDE.md.

Запуск ВНУТРИ backend-контейнера (креды GigaChat уже в окружении контейнера
через docker-compose + корневой .env — читать .env руками, как в версии
2026-07-04, не нужно):
    docker compose exec backend python \
        reports_scratch/generate_test_lessons.py
(скрипт кладут в контейнер через docker cp — Dockerfile копирует только
app/ и tests/, см. .claude/skills/kids-server/SKILL.md)
"""
import asyncio
import json
from pathlib import Path

from app.models.child import Child
from app.models.subject import Subject
from app.models.topic import Topic
from app.services.gigachat import generate_lesson_raw
from app.services.lesson_generator import _build_prompt
from app.services.lesson_pipeline import (
    assemble_lesson_dict,
    generate_lesson_content,
    generate_questions,
    verify_and_repair_questions,
)

OUT_DIR = Path(__file__).parent
OLD_DIR = OUT_DIR / "lessons_out_old"
NEW_DIR = OUT_DIR / "lessons_out_new"

# Те же 10 тем/возрастов, что в базовой метрике 2026-07-04 — см. CLAUDE.md,
# раздел "БАЗОВАЯ МЕТРИКА КАЧЕСТВА КВИЗОВ" -> "Результат по каждому уроку".
# (#, тема, возраст, сложность 1-3 — сложность в оригинале не была явно
# зафиксирована по номеру, взята пропорционально возрасту как разумное
# приближение методологии "по одной теме на класс/сложность").
TOPICS = [
    (1, "Счёт до 10", 6, 1),
    (2, "Секреты сложения", 7, 1),
    (3, "Вычитание в пределах 20", 7, 1),
    (4, "Умножение на 2 и 3", 8, 2),
    (5, "Деление без остатка", 9, 2),
    (6, "Порядок действий", 9, 2),
    (7, "Половина и четверть", 10, 2),
    (8, "Сложение дробей (общий знаменатель)", 10, 3),
    (9, "Периметр/площадь прямоугольника", 11, 3),
    (10, "Проценты, базовые понятия", 12, 3),
]

SUBJECT = Subject(name="Математика", slug="math")


def _grade_for_age(age: int) -> int:
    return max(1, age - 6)


async def generate_old(title: str, age: int, difficulty: int) -> dict:
    child = Child(name="Тест", age=age, grade=_grade_for_age(age))
    topic = Topic(title=title, difficulty=difficulty)
    prompt = _build_prompt(child, topic, SUBJECT, difficulty)
    return await generate_lesson_raw(prompt)


async def generate_new(title: str, age: int, difficulty: int) -> dict:
    child = Child(name="Тест", age=age, grade=_grade_for_age(age))
    topic = Topic(title=title, difficulty=difficulty)
    content = await generate_lesson_content(child, topic, SUBJECT, difficulty)
    drafts = await generate_questions(content)
    verified, passthrough = await verify_and_repair_questions(content, drafts)
    return assemble_lesson_dict(content, verified, passthrough)


async def main() -> None:
    OLD_DIR.mkdir(exist_ok=True)
    NEW_DIR.mkdir(exist_ok=True)

    for num, title, age, difficulty in TOPICS:
        print(f"[{num}/10] {title} (возраст {age}) — старый пайплайн...")
        try:
            old_lesson = await generate_old(title, age, difficulty)
            (OLD_DIR / f"lesson_{num:02d}.json").write_text(
                json.dumps(old_lesson, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            print(f"  ОШИБКА (старый): {e}")

        print(f"[{num}/10] {title} (возраст {age}) — новый пайплайн...")
        try:
            new_lesson = await generate_new(title, age, difficulty)
            (NEW_DIR / f"lesson_{num:02d}.json").write_text(
                json.dumps(new_lesson, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            print(f"  ОШИБКА (новый): {e}")

    print("Готово. См. lessons_out_old/ и lessons_out_new/, дальше — check_lessons.py")


if __name__ == "__main__":
    asyncio.run(main())
