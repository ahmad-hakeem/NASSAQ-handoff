import { useTranslation } from '@/shared/contexts/ThemeContext';

const BORDER = {
  quantitative: '#46C1BE',
  academic: '#46C1BE',
  statistical_alert: '#ef4444',
  positive: '#22c55e',
  administrative: '#615090',
};

export default function HakimRecommendations({ recommendations, source }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-lg font-cairo text-[#1C3D74]">{t('nassaqSuggestions')}</h3>
        {source === 'fallback' && (
          <span
            className="text-[10px] font-cairo px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200"
            title={t('aiUnavailableShowingGenericGuidance') || 'الذكاء الاصطناعي غير متاح حالياً — يتم عرض إرشادات عامة'}
          >
            {t('genericGuidanceFallback') || 'إرشادات عامة'}
          </span>
        )}
      </div>
      {!recommendations?.length ? (
        <div className="text-center text-neutral-500 py-8">—</div>
      ) : (
        <ul className="space-y-3">
          {recommendations.map((r, i) => (
            <li
              key={i}
              className="rounded-lg p-3 border-e-4 flex items-start gap-2"
              style={{ borderInlineEndColor: BORDER[r.type] || '#888', background: '#f8fafc' }}
            >
              <span className="text-lg">{r.icon}</span>
              <span className="text-[#312E2F]">{r.text}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
