'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { api, LessonFull, QuizResult } from '@/lib/api';
import { getAuth } from '@/lib/auth';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { XPToast } from '@/components/ui/XPToast';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { MultipleChoiceStep } from '@/components/ui/MultipleChoiceStep';
import { FillBlankStep } from '@/components/ui/FillBlankStep';
import { MatchPairsStep } from '@/components/ui/MatchPairsStep';
import { SortItemsStep } from '@/components/ui/SortItemsStep';

type Phase = 'loading' | 'intro' | 'steps' | 'quiz' | 'result';

const ACHIEVEMENT_NAMES: Record<string, string> = {
  'first-lesson': '🎉 Первый урок!',
  'five-lessons': '📚 Пять уроков!',
  'ten-lessons': '🎓 Десять уроков!',
  'perfect-quiz': '💯 Отличник!',
  'streak-3': '🔥 3 дня подряд!',
  'streak-7': '🔥 Неделя подряд!',
  'math-explorer': '🔢 Исследователь математики!',
  'first-100-xp': '⭐ 100 XP набрано!',
  'first-500-xp': '🏆 500 XP набрано!',
};

export default function LessonPage() {
  const router = useRouter();
  const params = useParams();
  const lessonId = Number(params.lessonId);

  const [lesson, setLesson] = useState<LessonFull | null>(null);
  const [phase, setPhase] = useState<Phase>('loading');
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [quizError, setQuizError] = useState('');
  const [showXPToast, setShowXPToast] = useState(false);

  useEffect(() => {
    const auth = getAuth();
    if (!auth) { router.push('/login'); return; }
    api.getLesson(lessonId, auth.token)
      .then(l => {
        setLesson(l);
        setPhase('intro');
        if (l.quiz) {
          setAnswers(new Array(l.quiz.questions.length).fill(null));
        }
      })
      .catch(() => router.push('/child/dashboard'));
  }, [lessonId, router]);

  async function submitQuiz() {
    const auth = getAuth();
    if (!auth || !lesson?.quiz) return;
    setSubmitting(true);
    try {
      const finalAnswers = answers.map(a => a ?? 0);
      const result = await api.submitQuiz(lesson.quiz.id, finalAnswers, null, auth.token);
      setQuizResult(result);
      setPhase('result');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setQuizError(message);
    } finally {
      setSubmitting(false);
    }
  }

  if (phase === 'loading' || !lesson) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-100 to-blue-100">
        <div className="text-center">
          <div className="text-6xl animate-bounce mb-4">📖</div>
          <div className="text-xl font-bold text-purple-700">Загружаем урок...</div>
        </div>
      </div>
    );
  }

  // INTRO PHASE
  if (phase === 'intro') {
    return (
      <main className="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-50 p-4">
        <div className="max-w-2xl mx-auto pt-4 space-y-6">
          <button onClick={() => router.back()} aria-label="Назад" className="text-2xl text-gray-400 hover:text-gray-600">←</button>
          <div className="text-center">
            <div className="text-6xl mb-4">🌟</div>
            <h1 className="text-3xl font-bold text-gray-800">{lesson.title}</h1>
            {lesson.goal && <p className="text-gray-500 mt-2">Цель: {lesson.goal}</p>}
          </div>
          {lesson.story_intro && (
            <Card className="bg-gradient-to-br from-orange-100 to-yellow-100 border-2 border-orange-200">
              <div className="text-4xl mb-3">🎭</div>
              <p className="text-lg text-gray-700 leading-relaxed">{lesson.story_intro}</p>
            </Card>
          )}
          <Button onClick={() => { setPhase('steps'); setCurrentStep(0); }} fullWidth size="xl">
            🚀 Начать урок!
          </Button>
        </div>
      </main>
    );
  }

  // STEPS PHASE
  if (phase === 'steps') {
    const step = lesson.steps[currentStep];
    const isLast = currentStep === lesson.steps.length - 1;
    const stepType = step.type;

    const goNext = () => {
      if (isLast) {
        if (lesson?.quiz) setPhase('quiz');
        else setPhase('result');
      } else {
        setCurrentStep(s => s + 1);
      }
    };

    const handleBack = () => {
      setCurrentStep(s => s - 1);
    };

    const handleXP = () => {
      setShowXPToast(true);
    };

    const stepIcon =
      stepType === 'explain' ? '💡' :
      stepType === 'fill_blank' ? '✏️' :
      stepType === 'match_pairs' ? '🔗' :
      stepType === 'sort_items' ? '📋' : '🎮';

    return (
      <main className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 p-4">
        {showXPToast && (
          <XPToast points={10} onComplete={() => setShowXPToast(false)} />
        )}
        <div className="max-w-2xl mx-auto pt-4 space-y-4">
          <ProgressBar current={currentStep + 1} total={lesson.steps.length} />

          <Card>
            <div className="flex items-center gap-3 mb-4">
              <span className="text-3xl">{stepIcon}</span>
              <h2 className="text-xl font-bold text-gray-800">{step.title}</h2>
            </div>

            {stepType === 'explain' && step.content && (
              <p className="text-lg text-gray-700 leading-relaxed">{step.content}</p>
            )}

            {(stepType === 'game' || stepType === 'multiple_choice') && (
              <MultipleChoiceStep step={step} onNext={goNext} onXP={handleXP} />
            )}

            {stepType === 'fill_blank' && (
              <FillBlankStep step={step} onNext={goNext} onXP={handleXP} />
            )}

            {stepType === 'match_pairs' && (
              <MatchPairsStep step={step} onNext={goNext} onXP={handleXP} />
            )}

            {stepType === 'sort_items' && (
              <SortItemsStep step={step} onNext={goNext} onXP={handleXP} />
            )}
          </Card>

          <div className="lesson-nav">
            {currentStep > 0 && (
              <button className="btn-back" onClick={handleBack}>← Назад</button>
            )}
            {stepType === 'explain' && (
              <Button
                onClick={goNext}
                size="lg"
                className={currentStep === 0 ? 'w-full' : 'flex-1'}
              >
                {isLast ? '📝 К тесту!' : '➡️ Дальше'}
              </Button>
            )}
          </div>
        </div>
      </main>
    );
  }

  // QUIZ PHASE
  if (phase === 'quiz' && lesson.quiz) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-green-50 to-teal-50 p-4">
        <div className="max-w-2xl mx-auto pt-4 space-y-6">
          <div className="text-center">
            <div className="text-5xl mb-2">📝</div>
            <h2 className="text-2xl font-bold text-gray-800">Тест</h2>
            <p className="text-gray-500">Ответь на вопросы!</p>
          </div>

          <div className="space-y-6">
            {lesson.quiz.questions.map((q, qi) => (
              <Card key={q.id}>
                <p className="font-bold text-gray-800 mb-4 text-lg">
                  {qi + 1}. {q.question}
                </p>
                <div className="space-y-2">
                  {q.options.map((option, oi) => (
                    <button
                      key={oi}
                      onClick={() => {
                        const next = [...answers];
                        next[qi] = oi;
                        setAnswers(next);
                      }}
                      className={`w-full text-left px-5 py-3 rounded-2xl border-2 transition-all font-medium ${
                        answers[qi] === oi
                          ? 'bg-purple-500 border-purple-500 text-white'
                          : 'bg-white border-gray-200 hover:border-purple-300 text-gray-700'
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </Card>
            ))}
          </div>

          {quizError && (
            <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl p-3 text-sm text-center">
              ❌ {quizError}
            </div>
          )}
          <Button
            onClick={submitQuiz}
            disabled={answers.some(a => a === null) || submitting}
            fullWidth size="xl"
          >
            {submitting ? '⏳ Проверяем...' : '✅ Сдать тест!'}
          </Button>
        </div>
      </main>
    );
  }

  // RESULT PHASE
  if (phase === 'result') {
    const scorePercent = quizResult ? Math.round(quizResult.score * 100) : 100;
    const emoji = scorePercent === 100 ? '🏆' : scorePercent >= 60 ? '⭐' : '💪';

    return (
      <main className="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-50 p-4">
        <div className="max-w-2xl mx-auto pt-8 space-y-6 text-center">
          <div className="text-8xl mb-4">{emoji}</div>
          <h2 className="text-4xl font-bold text-gray-800">
            {scorePercent === 100 ? 'Отлично!' : scorePercent >= 60 ? 'Хорошо!' : 'Не сдавайся!'}
          </h2>

          {quizResult && (
            <Card className="text-center">
              <div className="text-5xl font-bold text-purple-700 mb-2">{scorePercent}%</div>
              <div className="text-gray-500 mb-4">
                Правильно: {quizResult.correct} из {quizResult.total}
              </div>
              <div className="bg-yellow-100 rounded-2xl p-4">
                <div className="text-2xl font-bold text-yellow-700">+{quizResult.xp_earned} XP</div>
                <div className="text-yellow-600">заработано!</div>
              </div>
            </Card>
          )}

          {quizResult?.new_achievements && quizResult.new_achievements.length > 0 && (
            <Card className="bg-gradient-to-r from-yellow-100 to-orange-100 border-2 border-yellow-300">
              <div className="text-3xl mb-2">🏅 Новые достижения!</div>
              {quizResult.new_achievements.map(slug => (
                <div key={slug} className="font-bold text-yellow-800">{ACHIEVEMENT_NAMES[slug] ?? slug}</div>
              ))}
            </Card>
          )}

          <div className="space-y-3">
            <Button onClick={() => router.push('/child/catalog')} fullWidth size="lg">
              📚 Ещё урок!
            </Button>
            <Button onClick={() => router.push('/child/dashboard')} variant="ghost" fullWidth size="lg">
              🏠 На главную
            </Button>
          </div>
        </div>
      </main>
    );
  }

  return null;
}
