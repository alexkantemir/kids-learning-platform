const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://kids.it-kant.ru/api';

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; role: string; user_id: number; child_id: number | null }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ username, password }) }
    ),

  getChildProfile: (token: string) =>
    request<Child>('/children/me', {}, token),

  getChildren: (token: string) =>
    request<Child[]>('/children', {}, token),

  getSubjects: (token: string) =>
    request<Subject[]>('/subjects', {}, token),

  getTopics: (subjectId: number, token: string) =>
    request<Topic[]>(`/subjects/${subjectId}/topics`, {}, token),

  createCustomTopic: (data: { title: string; subject_id: number; difficulty: number }, token: string) =>
    request<Topic>('/subjects/topics/custom', { method: 'POST', body: JSON.stringify(data) }, token),

  generateLesson: (data: { topic_id: number; child_id: number; difficulty?: number }, token: string) =>
    request<{ lesson_id: number; title: string; status: string; xp_reward: number }>(
      '/lessons/generate',
      { method: 'POST', body: JSON.stringify(data) },
      token
    ),

  getLessonHistory: (childId: number, token: string) =>
    request<LessonSummary[]>(`/lessons/child/${childId}`, {}, token),

  getLesson: (lessonId: number, token: string) =>
    request<LessonFull>(`/lessons/${lessonId}`, {}, token),

  submitQuiz: (quizId: number, answers: number[], timeSpent: number | null, token: string) =>
    request<QuizResult>(`/quizzes/${quizId}/attempt`, {
      method: 'POST',
      body: JSON.stringify({ answers, time_spent_seconds: timeSpent }),
    }, token),

  getAchievements: (childId: number, token: string) =>
    request<AchievementItem[]>(`/achievements/child/${childId}`, {}, token),

  getProgress: (childId: number, token: string) =>
    request<ProgressItem[]>(`/progress/child/${childId}`, {}, token),

  getParentDashboard: (token: string) =>
    request<{ children: ParentChildSummary[] }>('/parent/dashboard', {}, token),

  createChild: (data: { name: string; age: number; grade: number; username: string; password: string; avatar_color?: string }, token: string) =>
    request<Child>('/children', { method: 'POST', body: JSON.stringify(data) }, token),

  getCurrentPlan: (childId: number, token: string) =>
    request<WeeklyPlan>(`/plans/child/${childId}/current`, {}, token),

  changeOwnPassword: (data: { current_password: string; new_password: string }, token: string) =>
    request<{ ok: boolean }>('/parent/password', { method: 'PUT', body: JSON.stringify(data) }, token),

  changeChildPassword: (childId: number, new_password: string, token: string) =>
    request<{ ok: boolean }>(`/parent/child/${childId}/password`, { method: 'PUT', body: JSON.stringify({ new_password }) }, token),

  resetChildHistory: (childId: number, token: string) =>
    request<{ ok: boolean; deleted_lessons: number }>(`/parent/child/${childId}/history`, { method: 'DELETE' }, token),

  getWarmup: (childId: number, token: string) =>
    request<WarmupQuestion[]>(`/children/${childId}/warmup`, {}, token),
};

export interface Child {
  id: number;
  name: string;
  age: number;
  grade: number;
  avatar_color: string;
  xp: number;
  streak_days: number;
  last_activity_date: string | null;
}

export interface Subject {
  id: number;
  name: string;
  slug: string;
  emoji: string;
  color: string;
}

export interface Topic {
  id: number;
  title: string;
  description: string | null;
  difficulty: number;
  is_catalog: boolean;
  subject_id: number;
}

export interface LessonSummary {
  id: number;
  title: string;
  topic: string | null;
  xp_reward: number;
  created_at: string;
}

export interface LessonStep {
  id: number;
  type: 'explain' | 'game' | 'multiple_choice' | 'fill_blank' | 'match_pairs' | 'sort_items';
  title: string;
  content: string | null;
  explanation: string | null;
  task: string | null;
  options: string[] | null;
  correct_index: number | null;
  sort_order: number;
  feedback_correct: string | null;
  feedback_wrong: string | null;
  hint: string | null;
  step_data: {
    correct_answers?: string[] | string[][];  // string[] for single blank, string[][] for multiple
    question?: string;
    pairs?: { left: string; right: string }[];
    items?: string[];
    correct_order?: string[];
    instruction?: string;
    text?: string;
  } | null;
}

export interface LessonFull {
  id: number;
  title: string;
  age_band: string;
  goal: string | null;
  story_intro: string | null;
  xp_reward: number;
  badge_candidate: string | null;
  status: string;
  topic: { id: number; title: string } | null;
  steps: LessonStep[];
  quiz: {
    id: number;
    questions: {
      id: number;
      question: string;
      options: string[];
      sort_order: number;
    }[];
  } | null;
  created_at: string;
}

export interface QuizResult {
  score: number;
  correct: number;
  total: number;
  xp_earned: number;
  attempt_id: number;
  correct_answers: number[];
  explanations: (string | null)[];
  new_achievements: string[];
}

export interface AchievementItem {
  id: number;
  slug: string;
  title: string;
  description: string;
  emoji: string;
  xp_bonus: number;
  earned: boolean;
  earned_at: string | null;
}

export interface ProgressItem {
  id: number;
  lessons_completed: number;
  quizzes_passed: number;
  total_xp: number;
  subject: Subject;
}

export interface ParentChildSummary {
  child: Child;
  total_lessons: number;
  total_quiz_attempts: number;
}

export interface PlanItem {
  id: number;
  topic_id: number;
  topic_title: string | null;
  is_completed: boolean;
  sort_order: number;
}

export interface WarmupQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string | null;
  lesson_title: string;
}

export interface WeeklyPlan {
  plan: {
    id: number;
    title: string;
    week_start: string;
    week_end: string;
  } | null;
  items: PlanItem[];
}
