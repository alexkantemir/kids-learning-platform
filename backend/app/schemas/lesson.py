from typing import Any
from pydantic import BaseModel, field_validator, model_validator


class LessonStepSchema(BaseModel):
    type: str  # explain | multiple_choice | game | fill_blank | match_pairs | sort_items
    title: str = ""
    # explain
    content: str | None = None
    # multiple_choice / game
    task: str | None = None
    options: list[str] | None = None
    correct_index: int | None = None
    explanation: str | None = None
    # feedback for all interactive types
    feedback_correct: str | None = None
    feedback_wrong: str | None = None
    hint: str | None = None
    # fill_blank
    text: str | None = None
    question: str | None = None  # instruction shown above the blank text
    blank_index: int | None = None
    correct_answers: list[Any] | None = None  # str[] (single blank) or str[][] (multi-blank)
    # match_pairs
    pairs: list[dict[str, Any]] | None = None
    # sort_items
    instruction: str | None = None
    items: list[str] | None = None
    correct_order: list[str] | None = None

    @model_validator(mode="after")
    def check_and_normalize(self) -> "LessonStepSchema":
        valid_types = {"explain", "game", "multiple_choice", "fill_blank", "match_pairs", "sort_items"}
        if self.type not in valid_types:
            self.type = "explain"
            if not self.content:
                self.content = self.task or ""
            return self

        if self.type in ("game", "multiple_choice"):
            if not self.options or len(self.options) < 2:
                self.type = "explain"
                if not self.content:
                    self.content = self.task or ""
            else:
                n = len(self.options)
                idx = self.correct_index
                if idx is None:
                    self.correct_index = 0
                elif idx == n:
                    # GigaChat used 1-based index — convert to 0-based
                    self.correct_index = n - 1
                elif not (0 <= idx < n):
                    self.correct_index = 0

        if self.type == "fill_blank":
            if not self.text and not self.task:
                self.type = "explain"
                self.content = self.content or ""
            elif not self.correct_answers:
                if self.options:
                    self.correct_answers = [self.options[0]]
                else:
                    self.correct_answers = [""]

        if self.type == "match_pairs":
            if not self.pairs or len(self.pairs) < 2:
                self.type = "explain"
                self.content = self.content or self.task or ""

        if self.type == "sort_items":
            if not self.items or len(self.items) < 2:
                self.type = "explain"
                self.content = self.content or self.task or ""
            elif not self.correct_order:
                self.correct_order = list(self.items)

        if not self.title:
            self.title = "Шаг"

        return self


class QuizQuestionSchema(BaseModel):
    question: str
    options: list[str]
    correct: int
    explanation: str | None = None

    @field_validator("options")
    @classmethod
    def check_options(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("Quiz question must have at least 2 options")
        return v

    @model_validator(mode="after")
    def normalize_correct_index(self) -> "QuizQuestionSchema":
        n = len(self.options)
        idx = self.correct
        if idx < 0:
            self.correct = 0
        elif idx == n:
            # GigaChat used 1-based index — convert to 0-based
            self.correct = n - 1
        elif idx >= n:
            self.correct = 0
        return self


class RewardSchema(BaseModel):
    xp: int = 20
    badge_candidate: str | None = None


class AILessonResponse(BaseModel):
    """Pydantic schema for validating GigaChat lesson response."""
    title: str
    age_band: str
    goal: str | None = None
    story_intro: str | None = None
    steps: list[LessonStepSchema]
    quiz: list[QuizQuestionSchema]
    reward: RewardSchema = RewardSchema()

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v[:256]

    @field_validator("steps")
    @classmethod
    def check_steps(cls, v: list) -> list:
        if not v:
            raise ValueError("Lesson must have at least one step")
        if len(v) > 10:
            return v[:10]
        return v

    @field_validator("quiz")
    @classmethod
    def check_quiz(cls, v: list) -> list:
        if not v:
            raise ValueError("Lesson must have at least one quiz question")
        if len(v) > 10:
            return v[:10]
        return v


class LessonGenerateRequest(BaseModel):
    topic_id: int
    child_id: int
    difficulty: int = 1

    @field_validator("difficulty")
    @classmethod
    def check_difficulty(cls, v: int) -> int:
        if not (1 <= v <= 3):
            raise ValueError("Difficulty must be 1, 2 or 3")
        return v
