'use client';
import { useState, useEffect, useMemo } from 'react';
import { LessonStep } from '@/lib/api';

interface Props {
  step: LessonStep;
  onNext: () => void;
  onXP: () => void;
}

export function MatchPairsStep({ step, onNext, onXP }: Props) {
  const pairs: { left: string; right: string }[] = step.step_data?.pairs || [];

  const shuffledRightOrder = useMemo(() => {
    const indices = pairs.map((_, i) => i);
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    return indices;
  }, [step.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const [selectedLeft, setSelectedLeft] = useState<number | null>(null);
  const [matched, setMatched] = useState<Record<number, number>>({}); // leftIdx → rightIdx
  const [wrongFlash, setWrongFlash] = useState<{ left: number; right: number } | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    setSelectedLeft(null);
    setMatched({});
    setWrongFlash(null);
    setDone(false);
  }, [step.id]);

  const matchedRightSet = new Set(Object.values(matched));

  function handleLeft(idx: number) {
    if (matched[idx] !== undefined || done) return;
    setSelectedLeft(prev => (prev === idx ? null : idx));
  }

  function handleRight(shuffledIdx: number) {
    const actualRightIdx = shuffledRightOrder[shuffledIdx];
    if (selectedLeft === null || done || matchedRightSet.has(actualRightIdx)) return;

    if (actualRightIdx === selectedLeft) {
      const newMatched = { ...matched, [selectedLeft]: actualRightIdx };
      setMatched(newMatched);
      setSelectedLeft(null);
      if (Object.keys(newMatched).length === pairs.length) {
        setDone(true);
        onXP();
        setTimeout(onNext, 2000);
      }
    } else {
      setWrongFlash({ left: selectedLeft, right: shuffledIdx });
      setTimeout(() => {
        setWrongFlash(null);
        setSelectedLeft(null);
      }, 700);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 text-center">
        {selectedLeft !== null ? 'Выбери правый вариант' : 'Выбери элемент слева'}
      </p>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          {pairs.map((pair, i) => {
            const isMatched = matched[i] !== undefined;
            const isSelected = selectedLeft === i;
            const isWrong = wrongFlash?.left === i;
            return (
              <button
                key={i}
                onClick={() => handleLeft(i)}
                disabled={isMatched || done}
                className={`w-full px-3 py-3 rounded-2xl border-2 font-medium text-sm transition-all ${
                  isMatched ? 'bg-green-100 border-green-400 text-green-800' :
                  isWrong ? 'bg-red-100 border-red-400 text-red-700' :
                  isSelected ? 'bg-purple-100 border-purple-500 text-purple-800' :
                  'bg-white border-gray-200 hover:border-purple-300 text-gray-700 active:scale-95'
                }`}
              >
                {isMatched && '✓ '}{pair.left}
              </button>
            );
          })}
        </div>

        <div className="space-y-2">
          {shuffledRightOrder.map((actualIdx, shuffledIdx) => {
            const isMatched = matchedRightSet.has(actualIdx);
            const isWrong = wrongFlash?.right === shuffledIdx;
            return (
              <button
                key={shuffledIdx}
                onClick={() => handleRight(shuffledIdx)}
                disabled={isMatched || done}
                className={`w-full px-3 py-3 rounded-2xl border-2 font-medium text-sm transition-all ${
                  isMatched ? 'bg-green-100 border-green-400 text-green-800' :
                  isWrong ? 'bg-red-100 border-red-400 text-red-700' :
                  'bg-white border-gray-200 hover:border-purple-300 text-gray-700 active:scale-95'
                }`}
              >
                {isMatched && '✓ '}{pairs[actualIdx].right}
              </button>
            );
          })}
        </div>
      </div>

      {done && step.feedback_correct && (
        <div className="rounded-2xl p-4 bg-green-50 text-green-700 border border-green-200 text-sm font-medium">
          🎉 {step.feedback_correct}
        </div>
      )}
    </div>
  );
}
