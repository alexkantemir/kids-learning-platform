interface XPBarProps {
  xp: number;
  streak: number;
}

export function XPBar({ xp, streak }: XPBarProps) {
  const level = Math.floor(xp / 100) + 1;
  const xpInLevel = xp % 100;

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">⭐</span>
          <div>
            <div className="text-xs text-gray-500">Уровень {level}</div>
            <div className="font-bold text-purple-700">{xp} XP</div>
          </div>
        </div>
        <div className="flex items-center gap-1 bg-orange-100 rounded-xl px-3 py-1">
          <span className="text-xl">🔥</span>
          <span className="font-bold text-orange-600">{streak}</span>
          <span className="text-xs text-orange-500">дней</span>
        </div>
      </div>
      <div className="h-3 bg-purple-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-500"
          style={{ width: `${xpInLevel}%` }}
        />
      </div>
      <div className="text-xs text-gray-400 mt-1 text-right">{xpInLevel}/100 до уровня {level + 1}</div>
    </div>
  );
}
