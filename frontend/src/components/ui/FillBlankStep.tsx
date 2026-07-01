'use client';
import { useState, useEffect, useRef } from 'react';
import { LessonStep } from '@/lib/api';

interface Props {
  step: LessonStep;
  onNext: () => void;
  onXP: () => void;
}

const BLANK_REGEX = /_{1,}(\s+_{1,})*|\.\.\.|(\[.*?\])/g;

function splitByBlank(text: string): string[] {
  const parts: string[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  BLANK_REGEX.lastIndex = 0;
  while ((match = BLANK_REGEX.exec(text)) !== null) {
    parts.push(text.slice(last, match.index));
    last = match.index + match[0].length;
  }
  parts.push(text.slice(last));
  return parts;
}

export function FillBlankStep({ step, onNext, onXP }: Props) {
  const sentence = step.task || step.content || '';
  const parts = splitByBlank(sentence);
  const blankCount = Math.max(parts.length - 1, 0);
  const fieldCount = Math.max(blankCount, 1);

  const [answers, setAnswers] = useState<string[]>(Array(fieldCount).fill(''));
  const [attempts, setAttempts] = useState(0);
  const [feedback, setFeedback] = useState<'correct' | 'wrong' | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setAnswers(Array(fieldCount).fill(''));
    setAttempts(0);
    setFeedback(null);
    setShowHint(false);
    setRevealed(false);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, [step.id, fieldCount]);

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const rawAnswers = step.step_data?.correct_answers ?? [];
  const questionText = step.step_data?.question ?? null;

  function setAnswer(index: number, value: string) {
    setAnswers(prev => { const next = [...prev]; next[index] = value; return next; });
  }

  function isAnswerCorrect(index: number): boolean {
    const userVal = (answers[index] ?? '').trim().toLowerCase();
    let accepted: string[];
    if (blankCount > 1) {
      const ca = rawAnswers[index];
      accepted = Array.isArray(ca) ? (ca as string[]) : [String(ca ?? '')];
    } else {
      accepted = rawAnswers as string[];
    }
    return accepted.some((a: string) => a.trim().toLowerCase() === userVal);
  }

  function handleSubmit() {
    if (answers.some(a => !a.trim()) || feedback === 'correct' || revealed) return;
    const allCorrect = Array.from({ length: fieldCount }, (_, i) => isAnswerCorrect(i)).every(Boolean);

    if (allCorrect) {
      setFeedback('correct');
      onXP();
      timerRef.current = setTimeout(onNext, 2000);
    } else {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);
      setFeedback('wrong');
      if (newAttempts < 2) {
        setShowHint(true);
        timerRef.current = setTimeout(() => {
          setFeedback(null);
          setAnswers(Array(fieldCount).fill(''));
        }, 1500);
      } else {
        setRevealed(true);
        timerRef.current = setTimeout(onNext, 2500);
      }
    }
  }

  const allFilled = answers.slice(0, fieldCount).every(a => a.trim().length > 0);

  const revealedText = blankCount > 1
    ? (rawAnswers as Array<string | string[]>).map(a => Array.isArray(a) ? a[0] : a).join(', ')
    : ((rawAnswers as string[])[0] || '—');

  return (
    <div className="space-y-4">
      {questionText && (
        <p className="fill-blank-question">{questionText}</p>
      )}

      <div className="text-lg text-gray-700 leading-relaxed">
        {blankCount > 0 ? (
          <span>
            {parts.map((part, i) => (
              <span key={i}>
                {part}
                {i < parts.length - 1 && (
                  <input
                    type="text"
                    value={answers[i] ?? ''}
                    onChange={e => setAnswer(i, e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); }}
                    disabled={feedback === 'correct' || revealed}
                    placeholder="..."
                    autoFocus={i === 0}
                    className={`fill-blank-input${feedback ? (isAnswerCorrect(i) ? ' correct' : ' incorrect') : ''}`}
                  />
                )}
              </span>
            ))}
          </span>
        ) : (
          <span>{sentence}</span>
        )}
      </div>

      {blankCount === 0 && (
        <input
          type="text"
          value={answers[0] ?? ''}
          onChange={e => setAnswer(0, e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); }}
          disabled={feedback === 'correct' || revealed}
          placeholder="Введи ответ..."
          autoFocus
          className={`w-full border-b-2 border-purple-400 focus:border-purple-600 outline-none px-3 py-2 text-center font-semibold text-purple-800 bg-transparent text-lg${feedback ? (isAnswerCorrect(0) ? ' correct' : ' incorrect') : ''}`}
        />
      )}

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
          💡 {step.feedback_wrong || 'Попробуй ещё раз!'}
        </div>
      )}

      {revealed && (
        <div className="answer-reveal">
          Правильный ответ: <strong>{revealedText}</strong>
        </div>
      )}

      {!feedback && !revealed && (
        <button
          onClick={handleSubmit}
          disabled={!allFilled}
          className="w-full py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-2xl font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Проверить
        </button>
      )}
    </div>
  );
}
