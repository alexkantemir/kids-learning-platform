'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, Child, LessonSummary, WarmupQuestion } from '@/lib/api';
import { getAuth, clearAuth } from '@/lib/auth';
import { XPBar } from '@/components/ui/XPBar';
import { Card } from '@/components/ui/Card';
import { DailyWarmup } from '@/components/ui/DailyWarmup';

export default function ChildDashboard() {
  const router = useRouter();
  const [child, setChild] = useState<Child | null>(null);
  const [recentLessons, setRecentLessons] = useState<LessonSummary[]>([]);
  const [warmupQuestions, setWarmupQuestions] = useState<WarmupQuestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    if (!auth || auth.role !== 'child') {
      router.push('/login');
      return;
    }

    async function load() {
      const currentAuth = getAuth();
      if (!currentAuth) return;
      try {
        const [childData, lessons] = await Promise.all([
          api.getChildProfile(currentAuth.token),
          api.getLessonHistory(currentAuth.child_id!, currentAuth.token),
        ]);
        setChild(childData);
        setRecentLessons(lessons.slice(0, 3));

        const warmup = await api.getWarmup(currentAuth.child_id!, currentAuth.token).catch(() => []);
        setWarmupQuestions(warmup);
      } catch {
        clearAuth();
        router.push('/login');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-100 to-blue-100">
        <div className="text-4xl animate-bounce">⏳</div>
      </div>
    );
  }

  if (!child) return null;

  return (
    <main className="min-h-screen bg-gradient-to-br from-purple-50 via-blue-50 to-pink-50 p-4">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pt-4">
          <div>
            <h1 className="text-3xl font-bold text-purple-800">
              Привет, {child.name}! 👋
            </h1>
            <p className="text-gray-500">{child.grade} класс</p>
          </div>
          <button
            onClick={() => { clearAuth(); router.push('/login'); }}
            className="text-gray-400 hover:text-gray-600 text-sm"
          >
            Выйти
          </button>
        </div>

        {/* XP Bar */}
        <XPBar xp={child.xp} streak={child.streak_days} />

        {/* Daily warmup */}
        {warmupQuestions.length > 0 && (
          <DailyWarmup questions={warmupQuestions} />
        )}

        {/* Big action button */}
        <Card className="bg-gradient-to-r from-purple-500 to-pink-500 text-white cursor-pointer hover:shadow-2xl transition-all"
          onClick={() => router.push('/child/catalog')}>
          <div className="text-center py-2">
            <div className="text-5xl mb-3">📚</div>
            <div className="text-2xl font-bold">Начать урок!</div>
            <div className="text-purple-100 mt-1">Выбери тему и учись</div>
          </div>
        </Card>

        {/* Recent lessons */}
        {recentLessons.length > 0 && (
          <div>
            <h2 className="text-xl font-bold text-gray-700 mb-3">📖 Недавние уроки</h2>
            <div className="space-y-3">
              {recentLessons.map(lesson => (
                <Card key={lesson.id} hover onClick={() => router.push(`/child/lesson/${lesson.id}`)}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-bold text-gray-800">{lesson.title}</div>
                      <div className="text-sm text-gray-500">{lesson.topic}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-purple-600">+{lesson.xp_reward} XP</div>
                      <div className="text-xs text-gray-400">⭐</div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="grid grid-cols-2 gap-3">
          {[
            { icon: '📅', label: 'План', path: '/child/plan' },
            { icon: '🗺️', label: 'История', path: '/child/history' },
            { icon: '🏆', label: 'Награды', path: '/child/achievements' },
            { icon: '📊', label: 'Прогресс', path: '/child/progress' },
          ].map(item => (
            <Card key={item.path} hover onClick={() => router.push(item.path)}
              className="text-center py-4 px-2">
              <div className="text-3xl mb-1">{item.icon}</div>
              <div className="text-sm font-semibold text-gray-700">{item.label}</div>
            </Card>
          ))}
        </div>
      </div>
    </main>
  );
}
