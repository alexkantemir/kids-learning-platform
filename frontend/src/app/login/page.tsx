'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { saveAuth } from '@/lib/auth';
import { Button } from '@/components/ui/Button';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await api.login(username.trim().toLowerCase(), password);
      saveAuth({
        token: data.access_token,
        role: data.role as 'parent' | 'child',
        user_id: data.user_id,
        child_id: data.child_id,
      });
      if (data.role === 'child') {
        router.push('/child/dashboard');
      } else {
        router.push('/parent/dashboard');
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Неверный логин или пароль';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-purple-100 via-blue-50 to-pink-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-6xl mb-4">🚀</div>
          <h1 className="text-4xl font-bold text-purple-800">Kids Learning</h1>
          <p className="text-gray-500 mt-2">Войди и начни учиться!</p>
        </div>

        <div className="bg-white rounded-3xl shadow-xl p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-username" className="block text-sm font-semibold text-gray-700 mb-2">Логин</label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Твой логин"
                required
                className="w-full px-4 py-3 border-2 border-purple-200 rounded-2xl focus:outline-none focus:border-purple-500 text-lg"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="block text-sm font-semibold text-gray-700 mb-2">Пароль</label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Твой пароль"
                required
                className="w-full px-4 py-3 border-2 border-purple-200 rounded-2xl focus:outline-none focus:border-purple-500 text-lg"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 rounded-2xl p-3 text-sm">
                ❌ {error}
              </div>
            )}

            <Button type="submit" fullWidth size="lg" disabled={loading}>
              {loading ? '⏳ Входим...' : '🎯 Войти'}
            </Button>
          </form>
        </div>
      </div>
    </main>
  );
}
