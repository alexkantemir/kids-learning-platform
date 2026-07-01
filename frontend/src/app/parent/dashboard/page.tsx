'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, ParentChildSummary } from '@/lib/api';
import { getAuth, clearAuth } from '@/lib/auth';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export default function ParentDashboard() {
  const router = useRouter();
  const [data, setData] = useState<{ children: ParentChildSummary[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', age: '', grade: '', username: '', password: '', avatar_color: 'blue' });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [showOwnPassword, setShowOwnPassword] = useState(false);
  const [ownPwForm, setOwnPwForm] = useState({ current_password: '', new_password: '' });
  const [ownPwLoading, setOwnPwLoading] = useState(false);
  const [ownPwError, setOwnPwError] = useState('');
  const [ownPwSuccess, setOwnPwSuccess] = useState(false);
  const [showChildPassword, setShowChildPassword] = useState<number | null>(null);
  const [childPwValue, setChildPwValue] = useState('');
  const [childPwLoading, setChildPwLoading] = useState(false);
  const [childPwError, setChildPwError] = useState('');
  const [childPwSuccess, setChildPwSuccess] = useState<number | null>(null);

  async function loadData() {
    const auth = getAuth();
    if (!auth || auth.role !== 'parent') { router.push('/login'); return; }
    api.getParentDashboard(auth.token)
      .then(setData)
      .catch(() => { clearAuth(); router.push('/login'); })
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadData(); }, [router]);

  async function createChild(e: React.FormEvent) {
    e.preventDefault();
    const auth = getAuth();
    if (!auth) return;
    setCreating(true);
    setError('');
    try {
      await api.createChild({
        name: form.name,
        age: Number(form.age),
        grade: Number(form.grade),
        username: form.username,
        password: form.password,
        avatar_color: form.avatar_color,
      }, auth.token);
      setShowCreate(false);
      setForm({ name: '', age: '', grade: '', username: '', password: '', avatar_color: 'blue' });
      setLoading(true);
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка создания');
    } finally {
      setCreating(false);
    }
  }

  async function changeOwnPassword(e: React.FormEvent) {
    e.preventDefault();
    const auth = getAuth();
    if (!auth) return;
    setOwnPwLoading(true);
    setOwnPwError('');
    setOwnPwSuccess(false);
    try {
      await api.changeOwnPassword(ownPwForm, auth.token);
      setOwnPwSuccess(true);
      setOwnPwForm({ current_password: '', new_password: '' });
      setTimeout(() => { setShowOwnPassword(false); setOwnPwSuccess(false); }, 1500);
    } catch (err: unknown) {
      setOwnPwError(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setOwnPwLoading(false);
    }
  }

  async function changeChildPassword(childId: number) {
    const auth = getAuth();
    if (!auth || !childPwValue) return;
    setChildPwLoading(true);
    setChildPwError('');
    setChildPwSuccess(null);
    try {
      await api.changeChildPassword(childId, childPwValue, auth.token);
      setChildPwSuccess(childId);
      setChildPwValue('');
      setTimeout(() => { setShowChildPassword(null); setChildPwSuccess(null); }, 1500);
    } catch (err: unknown) {
      setChildPwError(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setChildPwLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-50 to-blue-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between pt-4 mb-6">
          <h1 className="text-3xl font-bold text-gray-800">👨‍👩‍👧‍👦 Родительский режим</h1>
          <button onClick={() => { clearAuth(); router.push('/login'); }} className="text-gray-400 hover:text-gray-600 text-sm">Выйти</button>
        </div>

        {loading ? <div className="text-center py-12 text-4xl animate-bounce">⏳</div> : (
          <div className="space-y-6">
            {/* Own password change */}
            {!showOwnPassword ? (
              <button
                onClick={() => setShowOwnPassword(true)}
                className="text-sm text-purple-500 hover:text-purple-700 underline mb-2"
              >
                🔑 Сменить свой пароль
              </button>
            ) : (
              <Card className="mb-4">
                <h3 className="font-bold text-gray-700 mb-3">🔑 Смена пароля</h3>
                <form onSubmit={changeOwnPassword} className="space-y-3">
                  <div>
                    <label htmlFor="own-cur-pw" className="text-sm font-semibold text-gray-600">Текущий пароль</label>
                    <input id="own-cur-pw" type="password" value={ownPwForm.current_password}
                      onChange={e => setOwnPwForm(f => ({ ...f, current_password: e.target.value }))} required
                      className="w-full mt-1 px-4 py-2 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-purple-400" />
                  </div>
                  <div>
                    <label htmlFor="own-new-pw" className="text-sm font-semibold text-gray-600">Новый пароль</label>
                    <input id="own-new-pw" type="password" value={ownPwForm.new_password}
                      onChange={e => setOwnPwForm(f => ({ ...f, new_password: e.target.value }))} required minLength={6}
                      className="w-full mt-1 px-4 py-2 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-purple-400" />
                  </div>
                  {ownPwError && <div className="text-red-500 text-sm">❌ {ownPwError}</div>}
                  {ownPwSuccess && <div className="text-green-600 text-sm font-bold">✅ Пароль изменён!</div>}
                  <div className="flex gap-2">
                    <Button type="submit" disabled={ownPwLoading} className="flex-1">
                      {ownPwLoading ? '⏳' : '✅ Сохранить'}
                    </Button>
                    <Button type="button" variant="ghost" onClick={() => { setShowOwnPassword(false); setOwnPwError(''); }} className="flex-1">
                      Отмена
                    </Button>
                  </div>
                </form>
              </Card>
            )}

            {data?.children.map(({ child, total_lessons, total_quiz_attempts }) => (
              <Card key={child.id} hover onClick={() => router.push(`/parent/child/${child.id}`)}>
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-14 h-14 bg-purple-100 rounded-full flex items-center justify-center text-2xl font-bold text-purple-700">
                    {child.name[0]}
                  </div>
                  <div className="flex-1">
                    <div className="text-xl font-bold text-gray-800">{child.name}</div>
                    <div className="text-sm text-gray-500">{child.age} лет, {child.grade} класс</div>
                  </div>
                  <div className="text-purple-400 text-xl">→</div>
                </div>

                <div className="grid grid-cols-3 gap-3 text-center">
                  {[
                    { label: 'XP', value: child.xp, emoji: '⭐' },
                    { label: 'Уроки', value: total_lessons, emoji: '📚' },
                    { label: 'Серия', value: `${child.streak_days}д`, emoji: '🔥' },
                  ].map(stat => (
                    <div key={stat.label} className="bg-purple-50 rounded-2xl p-3">
                      <div className="text-2xl">{stat.emoji}</div>
                      <div className="font-bold text-purple-700">{stat.value}</div>
                      <div className="text-xs text-gray-500">{stat.label}</div>
                    </div>
                  ))}
                </div>

                {/* Child password change */}
                {showChildPassword === child.id ? (
                  <div className="mt-3 space-y-2" onClick={e => e.stopPropagation()}>
                    <label htmlFor={`child-pw-${child.id}`} className="text-sm font-semibold text-gray-600">Новый пароль</label>
                    <input
                      id={`child-pw-${child.id}`}
                      type="password"
                      value={childPwValue}
                      onChange={e => setChildPwValue(e.target.value)}
                      placeholder="Минимум 6 символов"
                      minLength={6}
                      className="w-full px-3 py-2 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-purple-400 text-sm"
                    />
                    {childPwError && <div className="text-red-500 text-xs">❌ {childPwError}</div>}
                    {childPwSuccess === child.id && <div className="text-green-600 text-xs font-bold">✅ Пароль изменён!</div>}
                    <div className="flex gap-2">
                      <Button size="sm" disabled={childPwLoading || childPwValue.length < 6}
                        onClick={() => changeChildPassword(child.id)} className="flex-1">
                        {childPwLoading ? '⏳' : '✅ Сохранить'}
                      </Button>
                      <Button size="sm" variant="ghost"
                        onClick={() => { setShowChildPassword(null); setChildPwValue(''); setChildPwError(''); }} className="flex-1">
                        Отмена
                      </Button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={e => { e.stopPropagation(); setShowChildPassword(child.id); setChildPwValue(''); setChildPwError(''); }}
                    className="mt-3 w-full text-sm text-purple-400 hover:text-purple-600 underline text-left"
                  >
                    🔑 Сменить пароль
                  </button>
                )}
              </Card>
            ))}

            {/* Add child button */}
            {!showCreate ? (
              <Button onClick={() => setShowCreate(true)} variant="secondary" fullWidth size="lg">
                + Добавить ребёнка
              </Button>
            ) : (
              <Card>
                <h3 className="text-xl font-bold text-gray-800 mb-4">Новый профиль</h3>
                <form onSubmit={createChild} className="space-y-3">
                  {[
                    { name: 'name', label: 'Имя', type: 'text', placeholder: 'Имя ребёнка' },
                    { name: 'age', label: 'Возраст', type: 'number', placeholder: '9' },
                    { name: 'grade', label: 'Класс', type: 'number', placeholder: '3' },
                    { name: 'username', label: 'Логин', type: 'text', placeholder: 'masha2015' },
                    { name: 'password', label: 'Пароль', type: 'password', placeholder: 'Пароль' },
                  ].map(field => (
                    <div key={field.name}>
                      <label htmlFor={`child-${field.name}`} className="text-sm font-semibold text-gray-600">{field.label}</label>
                      <input
                        id={`child-${field.name}`}
                        type={field.type}
                        placeholder={field.placeholder}
                        value={form[field.name as keyof typeof form]}
                        onChange={e => setForm(f => ({ ...f, [field.name]: e.target.value }))}
                        required
                        className="w-full mt-1 px-4 py-2 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-purple-400"
                      />
                    </div>
                  ))}
                  {error && <div className="text-red-500 text-sm">{error}</div>}
                  <div className="flex gap-3">
                    <Button type="submit" disabled={creating} className="flex-1">
                      {creating ? '⏳ Создаём...' : '✅ Создать'}
                    </Button>
                    <Button type="button" variant="ghost" onClick={() => setShowCreate(false)} className="flex-1">
                      Отмена
                    </Button>
                  </div>
                </form>
              </Card>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
