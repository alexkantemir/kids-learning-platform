'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, WeeklyPlan } from '@/lib/api';
import { getAuth } from '@/lib/auth';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export default function PlanPage() {
  const router = useRouter();
  const [plan, setPlan] = useState<WeeklyPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const auth = getAuth();
    if (!auth || !auth.child_id) { router.push('/login'); return; }
    api.getCurrentPlan(auth.child_id, auth.token)
      .then(setPlan)
      .finally(() => setLoading(false));
  }, [router]);

  async function startTopic(topicId: number) {
    const auth = getAuth();
    if (!auth || !auth.child_id) return;
    try {
      const result = await api.generateLesson({ topic_id: topicId, child_id: auth.child_id }, auth.token);
      router.push(`/child/lesson/${result.lesson_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка запуска урока');
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-teal-50 to-green-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 pt-4 mb-6">
          <button onClick={() => router.back()} aria-label="Назад" className="text-2xl">←</button>
          <h1 className="text-3xl font-bold text-gray-800">План на неделю 📅</h1>
        </div>
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl p-4 mb-4 text-center">
            ❌ {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-12 text-4xl animate-bounce">⏳</div>
        ) : !plan?.plan || plan.items.length === 0 ? (
          <Card className="text-center py-12">
            <div className="text-5xl mb-4">📋</div>
            <div className="text-xl font-bold text-gray-700">План пока не задан</div>
            <div className="text-gray-500 mt-2">Попроси родителей составить план!</div>
            <div className="mt-6">
              <Button onClick={() => router.push('/child/catalog')} variant="secondary">
                📚 Выбрать тему самому
              </Button>
            </div>
          </Card>
        ) : (
          <div className="space-y-4">
            {plan.plan && (
              <Card className="bg-teal-50 border border-teal-200">
                <div className="font-semibold text-teal-700">{plan.plan.title}</div>
                <div className="text-sm text-gray-500">
                  {new Date(plan.plan.week_start).toLocaleDateString('ru-RU')} —{' '}
                  {new Date(plan.plan.week_end).toLocaleDateString('ru-RU')}
                </div>
              </Card>
            )}

            <div className="space-y-3">
              {plan.items.map((item, idx) => (
                <Card key={item.id} className={item.is_completed ? 'opacity-60' : ''}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                        item.is_completed ? 'bg-green-100 text-green-600' : 'bg-purple-100 text-purple-600'
                      }`}>
                        {item.is_completed ? '✓' : idx + 1}
                      </div>
                      <span className="font-medium text-gray-800">{item.topic_title}</span>
                    </div>
                    {!item.is_completed && (
                      <Button
                        onClick={() => startTopic(item.topic_id)}
                        size="sm"
                        variant="secondary"
                      >
                        ▶ Учиться
                      </Button>
                    )}
                  </div>
                </Card>
              ))}
            </div>

            <div className="text-center text-sm text-gray-500">
              Выполнено: {plan.items.filter(i => i.is_completed).length} из {plan.items.length}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
