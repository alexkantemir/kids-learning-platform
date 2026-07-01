'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { getAuth } from '@/lib/auth';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

interface ChildDetail {
  child: { id: number; name: string; age: number; grade: number; xp: number; streak_days: number; avatar_color: string };
  stats: { total_lessons: number; total_xp: number; streak_days: number; achievements_earned: number };
  recent_lessons: { id: number; title: string; topic: string | null; xp_reward: number; created_at: string }[];
  recent_attempts: { id: number; score: number; xp_earned: number; created_at: string }[];
  progress: { subject: string; subject_emoji: string; lessons_completed: number; total_xp: number }[];
}

export default function ChildDetailPage() {
  const router = useRouter();
  const params = useParams();
  const childId = Number(params.childId);
  const [detail, setDetail] = useState<ChildDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmReset, setConfirmReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetDone, setResetDone] = useState(false);

  function loadDetail() {
    const auth = getAuth();
    if (!auth || auth.role !== 'parent') { router.push('/login'); return; }
    fetch(`/api/parent/child/${childId}/detail`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
      .then(r => r.json())
      .then(setDetail)
      .catch(() => router.push('/parent/dashboard'))
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadDetail(); }, [childId, router]);

  async function resetHistory() {
    const auth = getAuth();
    if (!auth) return;
    setResetting(true);
    try {
      await api.resetChildHistory(childId, auth.token);
      setResetDone(true);
      setConfirmReset(false);
      setLoading(true);
      loadDetail();
    } finally {
      setResetting(false);
    }
  }

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="text-4xl animate-bounce">⏳</div></div>;
  if (!detail) return null;

  const { child, stats, recent_lessons, recent_attempts, progress } = detail;

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 to-blue-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 pt-4 mb-6">
          <button onClick={() => router.back()} aria-label="Назад" className="text-2xl">←</button>
          <h1 className="text-3xl font-bold text-gray-800">{child.name}</h1>
        </div>

        {resetDone && (
          <div className="bg-green-50 border border-green-200 text-green-700 rounded-2xl p-3 mb-4 text-sm font-medium">
            ✅ История очищена. Прогресс, уроки и достижения сброшены.
          </div>
        )}

        {/* Stats overview */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          {[
            { emoji: '⭐', label: 'XP', value: stats.total_xp },
            { emoji: '📚', label: 'Уроков', value: stats.total_lessons },
            { emoji: '🔥', label: 'Серия дней', value: `${stats.streak_days}д` },
            { emoji: '🏆', label: 'Достижений', value: stats.achievements_earned },
          ].map(s => (
            <Card key={s.label} className="text-center py-4">
              <div className="text-3xl">{s.emoji}</div>
              <div className="text-2xl font-bold text-gray-800">{s.value}</div>
              <div className="text-sm text-gray-500">{s.label}</div>
            </Card>
          ))}
        </div>

        {/* Progress per subject */}
        {progress.length > 0 && (
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gray-700 mb-3">📊 Прогресс по предметам</h2>
            <div className="space-y-3">
              {progress.map(p => (
                <Card key={p.subject} className="py-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">{p.subject_emoji} {p.subject}</span>
                    <span className="text-sm text-purple-600 font-semibold">{p.total_xp} XP</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full">
                    <div className="h-full bg-purple-400 rounded-full" style={{ width: `${Math.min((p.total_xp / 200) * 100, 100)}%` }} />
                  </div>
                  <div className="text-xs text-gray-400 mt-1">{p.lessons_completed} уроков</div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Recent lessons */}
        {recent_lessons.length > 0 && (
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gray-700 mb-3">📖 Последние уроки</h2>
            <div className="space-y-2">
              {recent_lessons.map(l => (
                <Card key={l.id} className="py-3">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium text-gray-800 text-sm">{l.title}</div>
                      <div className="text-xs text-gray-400">{new Date(l.created_at).toLocaleDateString('ru-RU')}</div>
                    </div>
                    <div className="text-sm font-bold text-purple-600">+{l.xp_reward} XP</div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Recent quiz attempts */}
        {recent_attempts.length > 0 && (
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gray-700 mb-3">📝 Последние тесты</h2>
            <div className="space-y-2">
              {recent_attempts.map(a => (
                <Card key={a.id} className="py-3">
                  <div className="flex justify-between items-center">
                    <div className="text-sm text-gray-400">{new Date(a.created_at).toLocaleDateString('ru-RU')}</div>
                    <div className="flex items-center gap-3">
                      <span className={`font-bold ${a.score >= 80 ? 'text-green-600' : a.score >= 60 ? 'text-yellow-600' : 'text-red-500'}`}>
                        {a.score}%
                      </span>
                      <span className="text-sm text-purple-600">+{a.xp_earned} XP</span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Danger zone */}
        <div className="border-2 border-red-100 rounded-3xl p-5 mt-4">
          <h2 className="text-base font-bold text-red-500 mb-1">⚠️ Сброс данных</h2>
          <p className="text-sm text-gray-500 mb-4">
            Удалит все уроки, историю тестов, прогресс и достижения. XP и серия обнулятся. Действие необратимо.
          </p>
          {!confirmReset ? (
            <button
              onClick={() => { setConfirmReset(true); setResetDone(false); }}
              className="text-sm text-red-500 hover:text-red-700 border border-red-200 hover:border-red-400 rounded-xl px-4 py-2 transition-colors"
            >
              🗑️ Очистить историю обучения
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm font-semibold text-red-600">Вы уверены? Это удалит всё обучение {child.name}.</p>
              <div className="flex gap-3">
                <Button
                  onClick={resetHistory}
                  disabled={resetting}
                  className="flex-1 bg-red-500 hover:bg-red-600 border-red-500"
                >
                  {resetting ? '⏳ Очищаем...' : '✅ Да, очистить'}
                </Button>
                <Button variant="ghost" onClick={() => setConfirmReset(false)} className="flex-1">
                  Отмена
                </Button>
              </div>
            </div>
          )}
        </div>

      </div>
    </main>
  );
}
