'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, Subject } from '@/lib/api';
import { getAuth } from '@/lib/auth';

const colorMap: Record<string, string> = {
  blue: 'from-blue-400 to-blue-600',
  red: 'from-red-400 to-red-600',
  purple: 'from-purple-400 to-purple-600',
  green: 'from-green-400 to-green-600',
  orange: 'from-orange-400 to-orange-600',
  indigo: 'from-indigo-400 to-indigo-600',
};

export default function CatalogPage() {
  const router = useRouter();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    if (!auth) { router.push('/login'); return; }
    api.getSubjects(auth.token)
      .then(setSubjects)
      .catch(() => router.push('/login'))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="text-4xl animate-spin">🌀</div></div>;

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 pt-4 mb-6">
          <button onClick={() => router.back()} className="text-2xl hover:scale-110 transition-transform">←</button>
          <h1 className="text-3xl font-bold text-gray-800">Предметы 📚</h1>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {subjects.map(subject => (
            <div
              key={subject.id}
              onClick={() => router.push(`/child/catalog/${subject.id}`)}
              className={`bg-gradient-to-br ${colorMap[subject.color] || 'from-gray-400 to-gray-600'}
                rounded-3xl p-6 text-white cursor-pointer hover:shadow-xl hover:-translate-y-1
                transition-all duration-200 active:scale-95`}
            >
              <div className="text-5xl mb-3">{subject.emoji}</div>
              <div className="text-xl font-bold">{subject.name}</div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
