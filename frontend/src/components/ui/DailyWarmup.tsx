'use client';
import { useState } from 'react';
import { WarmupQuestion } from '@/lib/api';

interface Props {
  questions: WarmupQuestion[];
}

export function DailyWarmup({ questions }: Props) {
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>(new Array(questions.length).fill(null));
  const [done, setDone] = useState(false);

  if (questions.length === 0) return null;

  if (done) {
    const correct = questions.filter((q, i) => answers[i] === q.correct_index).length;
    return (
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-3xl p-5 border border-blue-100">
        <div className="text-center">
          <div className="text-3xl mb-2">🧠</div>
          <div className="font-bold text-blue-800 text-lg">Разминка завершена!</div>
          <div className="text-blue-600 mt-1">
            {correct} из {questions.length} верно
          </div>
        </div>
      </div>
    );
  }

  const q = questions[current];
  const answered = answers[current] !== null;

  function handleAnswer(idx: number) {
    if (answered) return;
    const next = [...answers];
    next[current] = idx;
    setAnswers(next);
    setTimeout(() => {
      if (current < questions.length - 1) {
        setCurrent(current + 1);
      } else {
        setDone(true);
      }
    }, 1200);
  }

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-3xl p-5 border border-blue-100">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">🧠</span>
        <h3 className="font-bold text-blue-800">Вспомни вчерашнее</h3>
        <span className="ml-auto text-sm text-blue-400 font-medium">{current + 1}/{questions.length}</span>
      </div>
      <p className="text-xs text-blue-400 mb-3 truncate">{q.lesson_title}</p>
      <p className="font-semibold text-gray-800 mb-3 text-sm leading-snug">{q.question}</p>
      <div className="space-y-2">
        {q.options.map((opt, i) => {
          const isSelected = answers[current] === i;
          const isCorrect = q.correct_index === i;
          let cls = 'bg-white border-gray-200 hover:border-blue-300 text-gray-700';
          if (answered) {
            if (isCorrect) cls = 'bg-green-100 border-green-400 text-green-800 font-bold';
            else if (isSelected) cls = 'bg-red-100 border-red-400 text-red-700';
            else cls = 'bg-gray-50 border-gray-200 text-gray-400';
          }
          return (
            <button
              key={i}
              onClick={() => handleAnswer(i)}
              disabled={answered}
              className={`w-full text-left px-4 py-2 rounded-xl border-2 text-sm transition-all ${cls}`}
            >
              {answered && isCorrect && '✓ '}
              {answered && isSelected && !isCorrect && '✗ '}
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}
