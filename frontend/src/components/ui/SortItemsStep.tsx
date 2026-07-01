'use client';
import { useState, useEffect } from 'react';
import { LessonStep } from '@/lib/api';

interface Props {
  step: LessonStep;
  onNext: () => void;
  onXP: () => void;
}

export function SortItemsStep({ step, onNext, onXP }: Props) {
  const items: string[] = step.step_data?.items || [];
  const correctOrder: string[] = step.step_data?.correct_order || [];
  const instruction = step.step_data?.instruction || step.task || '';

  const [clickOrder, setClickOrder] = useState<number[]>([]);
  const [feedback, setFeedback] = useState<'correct' | 'wrong' | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [showHint, setShowHint] = useState(false);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    setClickOrder([]);
    setFeedback(null);
    setAttempts(0);
    setShowHint(false);
    setRevealed(false);
  }, [step.id]);

  function handleClick(idx: number) {
    if (feedback || revealed) return;
    if (clickOrder.includes(idx)) {
      setClickOrder(clickOrder.filter(i => i !== idx));
    } else {
      setClickOrder([...clickOrder, idx]);
    }
  }

  function handleCheck() {
    if (clickOrder.length !== items.length || feedback || revealed) return;
    const userOrder = clickOrder.map(i => items[i]);
    const isCorrect = userOrder.every((item, i) => item === correctOrder[i]);

    if (isCorrect) {
      setFeedback('correct');
      onXP();
      setTimeout(onNext, 2000);
    } else {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);
      setFeedback('wrong');
      if (newAttempts < 2) {
        setShowHint(true);
        setTimeout(() => { setFeedback(null); setClickOrder([]); }, 1500);
      } else {
        setRevealed(true);
        setTimeout(onNext, 2500);
      }
    }
  }

  return (
    <div className="space-y-4">
      {instruction && <p className="text-gray-700 font-medium">{instruction}</p>}
      <p className="text-sm text-gray-500">
        Нажимай элементы в правильном порядке (1 → {items.length})
      </p>

      <div className="flex flex-wrap gap-2">
        {items.map((item, idx) => {
          const pos = clickOrder.indexOf(idx);
          const isSelected = pos !== -1;
          return (
            <button
              key={idx}
              onClick={() => handleClick(idx)}
              disabled={!!feedback || revealed}
              className={`relative px-4 py-2 rounded-2xl border-2 font-medium text-sm transition-all active:scale-95 ${
                isSelected
                  ? 'bg-purple-500 border-purple-600 text-white'
                  : 'bg-white border-gray-200 hover:border-purple-300 text-gray-700'
              }`}
            >
              {isSelected && (
                <span className="absolute -top-2 -right-2 bg-purple-700 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
                  {pos + 1}
                </span>
              )}
              {item}
            </button>
          );
        })}
      </div>

      {showHint && !revealed && step.hint && (
        <div className="hint-box">🔑 {step.hint}</div>
      )}

      {feedback === 'correct' && (
        <div className="rounded-2xl p-4 bg-green-50 text-green-700 border border-green-200 text-sm font-medium">
          🎉 {step.feedback_correct || 'Верно!'}
        </div>
      )}

      {feedback === 'wrong' && !revealed && (
        <div className="rounded-2xl p-4 bg-orange-50 text-orange-700 border border-orange-200 text-sm font-medium">
          💡 {step.feedback_wrong || 'Порядок неправильный, попробуй ещё!'}
        </div>
      )}

      {revealed && (
        <div className="answer-reveal">
          Правильный порядок: <strong>{correctOrder.join(' → ')}</strong>
        </div>
      )}

      {!feedback && !revealed && clickOrder.length === items.length && (
        <button
          onClick={handleCheck}
          className="w-full py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-2xl font-bold transition-all"
        >
          Проверить
        </button>
      )}
    </div>
  );
}
