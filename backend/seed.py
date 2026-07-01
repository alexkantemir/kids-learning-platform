"""
Seed script: populates subjects, topics, and initial achievements.
Run inside the backend container: docker compose exec backend python seed.py
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from app.core.config import settings
from app.models.subject import Subject
from app.models.topic import Topic
from app.services.gamification import ensure_achievements_exist

SUBJECTS = [
    {"name": "Математика", "slug": "math", "emoji": "🔢", "color": "blue", "sort_order": 1},
    {"name": "Русский язык", "slug": "russian", "emoji": "📝", "color": "red", "sort_order": 2},
    {"name": "Чтение и литература", "slug": "reading", "emoji": "📖", "color": "purple", "sort_order": 3},
    {"name": "Окружающий мир", "slug": "world", "emoji": "🌍", "color": "green", "sort_order": 4},
    {"name": "Логика", "slug": "logic", "emoji": "🧩", "color": "orange", "sort_order": 5},
    {"name": "Английский язык", "slug": "english", "emoji": "🇬🇧", "color": "indigo", "sort_order": 6},
]

TOPICS = {
    "math": [
        {"title": "Сложение и вычитание до 100", "difficulty": 1},
        {"title": "Умножение и деление", "difficulty": 2},
        {"title": "Дроби: половина и четверть", "difficulty": 2},
        {"title": "Геометрические фигуры", "difficulty": 1},
        {"title": "Задачи на время", "difficulty": 2},
        {"title": "Порядок действий в примерах", "difficulty": 3},
    ],
    "russian": [
        {"title": "Гласные и согласные буквы", "difficulty": 1},
        {"title": "Правило ЖИ-ШИ, ЧА-ЩА", "difficulty": 1},
        {"title": "Состав слова: корень, суффикс, приставка", "difficulty": 2},
        {"title": "Имя существительное", "difficulty": 2},
        {"title": "Глагол и его формы", "difficulty": 2},
        {"title": "Знаки препинания в предложении", "difficulty": 3},
    ],
    "reading": [
        {"title": "Пересказ прочитанного текста", "difficulty": 1},
        {"title": "Главный герой и его характер", "difficulty": 2},
        {"title": "Басни Крылова", "difficulty": 2},
        {"title": "Сказки народов мира", "difficulty": 1},
        {"title": "Стихи Пушкина", "difficulty": 2},
    ],
    "world": [
        {"title": "Времена года", "difficulty": 1},
        {"title": "Животные и их среда обитания", "difficulty": 1},
        {"title": "Части света и океаны", "difficulty": 2},
        {"title": "Растения: строение и виды", "difficulty": 2},
        {"title": "Солнечная система", "difficulty": 2},
        {"title": "Человек и его здоровье", "difficulty": 1},
    ],
    "logic": [
        {"title": "Загадки и ребусы", "difficulty": 1},
        {"title": "Сравнение и классификация", "difficulty": 1},
        {"title": "Причина и следствие", "difficulty": 2},
        {"title": "Числовые паттерны", "difficulty": 2},
        {"title": "Логические цепочки", "difficulty": 3},
    ],
    "english": [
        {"title": "Алфавит и звуки английского", "difficulty": 1},
        {"title": "Цвета и числа", "difficulty": 1},
        {"title": "Моя семья (My Family)", "difficulty": 1},
        {"title": "Животные (Animals)", "difficulty": 1},
        {"title": "Глагол to be", "difficulty": 2},
        {"title": "Present Simple", "difficulty": 2},
    ],
}


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        # Seed subjects
        for subj_data in SUBJECTS:
            existing = await db.execute(select(Subject).where(Subject.slug == subj_data["slug"]))
            if not existing.scalar_one_or_none():
                subject = Subject(**subj_data)
                db.add(subject)
                print(f"Added subject: {subj_data['name']}")

        await db.flush()

        # Seed topics
        for slug, topics in TOPICS.items():
            subj_result = await db.execute(select(Subject).where(Subject.slug == slug))
            subject = subj_result.scalar_one_or_none()
            if not subject:
                continue

            for topic_data in topics:
                existing = await db.execute(
                    select(Topic).where(
                        Topic.title == topic_data["title"],
                        Topic.subject_id == subject.id,
                    )
                )
                if not existing.scalar_one_or_none():
                    topic = Topic(
                        title=topic_data["title"],
                        difficulty=topic_data["difficulty"],
                        subject_id=subject.id,
                        is_catalog=True,
                        is_approved=True,
                    )
                    db.add(topic)
                    print(f"Added topic: {topic_data['title']}")

        # Seed achievements
        await ensure_achievements_exist(db)
        print("Achievements seeded")

        await db.commit()
        print("Seed complete!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
