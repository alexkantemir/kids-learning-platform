'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, LessonSummary } from '@/lib/api';
import { getAuth } from '@/lib/auth';
import { Card } from '@/components/ui/Card';

export default function HistoryPage() {
  const router = useRouter();
  const [lessons, setLessons] = useState<LessonSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    if (!auth || !auth.child_id) { router.push('/login'); return; }
    api.getLessonHistory(auth.child_id, auth.token)
      .then(setLessons)
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 pt-4 mb-6">
          <button onClick={() => router.back()} className="text-2xl">←</button>
          <h1 className="text-3xl font-bold text-gray-800">История уроков 📖</h1>
        </div>
        {loading ? (
          <div className="text-center py-12 text-4xl animate-bounce">⏳</div>
        ) : lessons.length === 0 ? (
          <Card className="text-center py-12">
            <div className="text-5xl mb-4">🎯</div>
            <div className="text-xl font-bold text-gray-700">Уроков пока нет</div>
            <div className="text-gray-500 mt-2">Начни первый урок!</div>
          </Card>
        ) : (
          <div className="space-y-3">
            {lessons.map(lesson => (
              <Card key={lesson.id} hover onClick={() => router.push(`/child/lesson/${lesson.id}`)}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-bold text-gray-800">{lesson.title}</div>
                    <div className="text-sm text-gray-500">{lesson.topic}</div>
                    <div className="text-xs text-gray-400 mt-1">
                      {new Date(lesson.created_at).toLocaleDateString('ru-RU')}
                    </div>
                  </div>
                  <div className="font-bold text-purple-600">+{lesson.xp_reward} XP</div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
