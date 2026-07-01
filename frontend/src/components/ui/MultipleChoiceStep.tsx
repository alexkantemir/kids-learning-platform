'use client';
import { useState, useEffect } from 'react';
import { LessonStep } from '@/lib/api';

interface Props {
  step: LessonStep;
  onNext: () => void;
  onXP: () => void;
}

export function MultipleChoiceStep({ step, onNext, onXP }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [showHint, setShowHint] = useState(false);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    setSelected(null);
    setAttempts(0);
    setShowHint(false);
    setRevealed(false);
  }, [step.id]);

  const question = step.task || '';
  const options = step.options || [];
  const correctIdx = step.correct_index ?? 0;

  function handleSelect(idx: number) {
    if (selected !== null || revealed) return;
    setSelected(idx);

    if (idx === correctIdx) {
      onXP();
      setTimeout(onNext, 2000);
    } else {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);
      if (newAttempts < 2) {
        setShowHint(true);
      } else {
        setRevealed(true);
        setTimeout(onNext, 2500);
      }
    }
  }

  function handleRetry() {
    setSelected(null);
  }

  const isAnswered = selected !== null;
  const isCorrect = selected === correctIdx;

  return (
    <div className="space-y-4">
      {question && <p className="text-lg font-semibold text-gray-700">{question}</p>}

      <div className="space-y-3">
        {options.map((option, i) => {
          let cls = 'bg-purple-50 hover:bg-purple-100 border-purple-200 hover:border-purple-400 text-gray-700';
          if (isAnswered || revealed) {
            if (i === correctIdx) cls = 'bg-green-100 border-green-500 text-green-800 font-bold';
            else if (selected === i) cls = 'bg-red-100 border-red-400 text-red-700';
            else cls = 'bg-gray-50 border-gray-200 text-gray-400';
          }
          return (
            <button
              key={i}
              onClick={() => handleSelect(i)}
              disabled={isAnswered || revealed}
              className={`w-full text-left px-6 py-4 border-2 rounded-2xl font-medium transition-all ${isAnswered ? '' : 'active:scale-95'} ${cls}`}
            >
              {isAnswered && i === correctIdx && <span className="mr-2">✓</span>}
              {isAnswered && selected === i && i !== correctIdx && <span className="mr-2">✗</span>}
              {option}
            </button>
          );
        })}
      </div>

      {isAnswered && isCorrect && (
        <div className="rounded-2xl p-4 bg-green-50 text-green-700 border border-green-200 text-sm font-medium">
          🎉 {step.feedback_correct || step.explanation || 'Отлично!'}
        </div>
      )}

      {isAnswered && !isCorrect && !revealed && (
        <>
          <div className="rounded-2xl p-4 bg-orange-50 text-orange-700 border border-orange-200 text-sm font-medium">
            💡 {step.feedback_wrong || step.explanation || 'Подумай ещё!'}
          </div>
          {showHint && step.hint && (
            <div className="hint-box">🔑 {step.hint}</div>
          )}
          {attempts < 2 && (
            <button
              onClick={handleRetry}
              className="w-full py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-2xl font-bold transition-all"
            >
              Попробовать ещё раз
            </button>
          )}
        </>
      )}

      {revealed && (
        <div className="answer-reveal">
          Правильный ответ: <strong>{options[correctIdx]}</strong>
        </div>
      )}
    </div>
  );
}
