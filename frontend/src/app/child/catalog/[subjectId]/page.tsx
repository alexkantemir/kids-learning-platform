'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { api, Topic, Subject } from '@/lib/api';
import { getAuth } from '@/lib/auth';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

const difficultyEmoji = ['', '⭐', '⭐⭐', '⭐⭐⭐'];

export default function SubjectTopicsPage() {
  const router = useRouter();
  const params = useParams();
  const subjectId = Number(params.subjectId);

  const [topics, setTopics] = useState<Topic[]>([]);
  const [subject, setSubject] = useState<Subject | null>(null);
  const [customTitle, setCustomTitle] = useState('');
  const [showCustom, setShowCustom] = useState(false);
  const [generating, setGenerating] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const auth = getAuth();
    if (!auth) { router.push('/login'); return; }

    Promise.all([
      api.getSubjects(auth.token),
      api.getTopics(subjectId, auth.token),
    ]).then(([subjects, topicsData]) => {
      setSubject(subjects.find(s => s.id === subjectId) || null);
      setTopics(topicsData);
    }).catch(() => router.push('/login'))
      .finally(() => setLoading(false));
  }, [subjectId, router]);

  async function startLesson(topicId: number) {
    const auth = getAuth();
    if (!auth || !auth.child_id) return;
    setGenerating(topicId);
    try {
      const result = await api.generateLesson({ topic_id: topicId, child_id: auth.child_id }, auth.token);
      router.push(`/child/lesson/${result.lesson_id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError('Не удалось создать урок: ' + message);
    } finally {
      setGenerating(null);
    }
  }

  async function createCustomLesson() {
    const auth = getAuth();
    if (!auth || !auth.child_id || !customTitle.trim()) return;
    setGenerating(-1);
    try {
      const topic = await api.createCustomTopic({ title: customTitle.trim(), subject_id: subjectId, difficulty: 1 }, auth.token);
      const result = await api.generateLesson({ topic_id: topic.id, child_id: auth.child_id }, auth.token);
      router.push(`/child/lesson/${result.lesson_id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError('Ошибка: ' + message);
    } finally {
      setGenerating(null);
    }
  }

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="text-4xl animate-bounce">📚</div></div>;

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 pt-4 mb-6">
          <button onClick={() => router.back()} aria-label="Назад" className="text-2xl">←</button>
          <h1 className="text-3xl font-bold text-gray-800">
            {subject?.emoji} {subject?.name}
          </h1>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl p-4 mb-4 text-center">
            ❌ {error}
          </div>
        )}
        {generating !== null && (
          <div className="bg-purple-50 border-2 border-purple-200 rounded-3xl p-6 mb-4 text-center">
            <div className="text-4xl animate-spin mb-2">🤖</div>
            <div className="font-bold text-purple-700">ИИ создаёт твой урок...</div>
            <div className="text-sm text-gray-500 mt-1">Это займёт 10-30 секунд</div>
          </div>
        )}

        <div className="space-y-3 mb-6">
          {topics.map(topic => (
            <Card key={topic.id} className="flex items-center justify-between">
              <div>
                <div className="font-bold text-gray-800">{topic.title}</div>
                <div className="text-sm text-yellow-500">{difficultyEmoji[topic.difficulty]}</div>
              </div>
              <Button
                onClick={() => startLesson(topic.id)}
                disabled={generating !== null}
                size="sm"
              >
                {generating === topic.id ? '⏳' : '▶ Учиться'}
              </Button>
            </Card>
          ))}
        </div>

        {/* Custom topic */}
        <Card className="border-2 border-dashed border-purple-300">
          <button
            onClick={() => setShowCustom(!showCustom)}
            className="w-full text-left font-bold text-purple-600 flex items-center gap-2"
          >
            <span className="text-2xl">✨</span>
            Своя тема
          </button>
          {showCustom && (
            <div className="mt-4 space-y-3">
              <input
                type="text"
                value={customTitle}
                onChange={e => setCustomTitle(e.target.value)}
                placeholder="Напиши что хочешь изучить..."
                className="w-full px-4 py-3 border-2 border-purple-200 rounded-2xl focus:outline-none focus:border-purple-500"
                maxLength={200}
              />
              <Button
                onClick={createCustomLesson}
                disabled={!customTitle.trim() || generating !== null}
                fullWidth
              >
                {generating === -1 ? '⏳ Создаём урок...' : '🚀 Создать урок'}
              </Button>
            </div>
          )}
        </Card>
      </div>
    </main>
  );
}
