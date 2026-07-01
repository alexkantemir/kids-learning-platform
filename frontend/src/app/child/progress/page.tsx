'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, ProgressItem } from '@/lib/api';
import { getAuth } from '@/lib/auth';
import { Card } from '@/components/ui/Card';

export default function ProgressPage() {
  const router = useRouter();
  const [progress, setProgress] = useState<ProgressItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    if (!auth || !auth.child_id) { router.push('/login'); return; }
    api.getProgress(auth.child_id, auth.token)
      .then(setProgress)
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 to-teal-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 pt-4 mb-6">
          <button onClick={() => router.back()} className="text-2xl">←</button>
          <h1 className="text-3xl font-bold text-gray-800">Прогресс 📊</h1>
        </div>

        {loading ? <div className="text-center py-12 text-4xl animate-bounce">⏳</div> : progress.length === 0 ? (
          <Card className="text-center py-12">
            <div className="text-5xl mb-4">🎯</div>
            <div className="text-xl font-bold text-gray-700">Начни первый урок!</div>
          </Card>
        ) : (
          <div className="space-y-4">
            {progress.map(p => (
              <Card key={p.id}>
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-3xl">{p.subject.emoji}</span>
                  <div>
                    <div className="font-bold text-gray-800">{p.subject.name}</div>
                    <div className="text-sm text-gray-500">{p.lessons_completed} уроков</div>
                  </div>
                  <div className="ml-auto font-bold text-purple-600">{p.total_xp} XP</div>
                </div>
                <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-purple-400 to-pink-400 rounded-full"
                    style={{ width: `${Math.min((p.total_xp / 200) * 100, 100)}%` }}
                  />
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
