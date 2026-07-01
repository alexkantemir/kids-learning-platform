'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, AchievementItem } from '@/lib/api';
import { getAuth } from '@/lib/auth';
import { Card } from '@/components/ui/Card';

export default function AchievementsPage() {
  const router = useRouter();
  const [achievements, setAchievements] = useState<AchievementItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    if (!auth || !auth.child_id) { router.push('/login'); return; }
    api.getAchievements(auth.child_id, auth.token)
      .then(setAchievements)
      .finally(() => setLoading(false));
  }, [router]);

  const earned = achievements.filter(a => a.earned);
  const locked = achievements.filter(a => !a.earned);

  return (
    <main className="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 pt-4 mb-6">
          <button onClick={() => router.back()} className="text-2xl">←</button>
          <h1 className="text-3xl font-bold text-gray-800">Достижения 🏆</h1>
        </div>

        {loading ? <div className="text-center py-12 text-4xl animate-bounce">⏳</div> : (
          <>
            <div className="text-sm font-semibold text-gray-500 mb-3">
              Получено: {earned.length} из {achievements.length}
            </div>
            <div className="grid grid-cols-1 gap-3">
              {[...earned, ...locked].map(a => (
                <Card key={a.id} className={a.earned ? '' : 'opacity-50'}>
                  <div className="flex items-center gap-4">
                    <div className="text-4xl">{a.earned ? a.emoji : '🔒'}</div>
                    <div className="flex-1">
                      <div className="font-bold text-gray-800">{a.title}</div>
                      <div className="text-sm text-gray-500">{a.description}</div>
                      {a.xp_bonus > 0 && <div className="text-xs text-purple-600 font-semibold">+{a.xp_bonus} XP</div>}
                    </div>
                    {a.earned && <div className="text-green-500 text-2xl">✓</div>}
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
