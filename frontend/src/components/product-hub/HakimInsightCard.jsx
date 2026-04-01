import React from 'react';
import { Brain, Sparkles, AlertTriangle, Users, Target, FileText } from 'lucide-react';
import { PRIORITY_CONFIG } from './hubConstants';

export function HakimInsightCard({ hakim, compact = false, className = '' }) {
  if (!hakim || Object.keys(hakim).length === 0) return null;

  if (compact) {
    return (
      <div className={`flex items-center gap-2 text-xs ${className}`}>
        <Brain className="h-3.5 w-3.5 text-brand-turquoise flex-shrink-0" />
        {hakim.suggested_team && <span className="text-brand-turquoise font-medium">{hakim.suggested_team}</span>}
        {hakim.duplicate_ids?.length > 0 && (
          <span className="text-amber-600 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            {hakim.duplicate_ids.length} مشابه
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={`rounded-2xl border border-brand-turquoise/20 bg-gradient-to-br from-brand-turquoise/5 via-white to-brand-turquoise/3 overflow-hidden ${className}`}>
      <div className="flex items-center gap-2 px-5 py-3 border-b border-brand-turquoise/10 bg-brand-turquoise/5">
        <Brain className="h-5 w-5 text-brand-turquoise" />
        <span className="font-semibold text-brand-navy text-sm">تحليل حكيم</span>
        <Sparkles className="h-3.5 w-3.5 text-brand-turquoise/60" />
      </div>

      <div className="p-5 space-y-3">
        {hakim.priority_reasoning && (
          <InsightRow
            icon={Target}
            title="الأولوية المقترحة"
            value={PRIORITY_CONFIG[hakim.suggested_priority]?.label || hakim.suggested_priority}
            detail={hakim.priority_reasoning}
            valueColor={PRIORITY_CONFIG[hakim.suggested_priority]?.textColor}
          />
        )}

        {hakim.team_reasoning && (
          <InsightRow
            icon={Users}
            title="الفريق المقترح"
            value={hakim.suggested_team}
            detail={hakim.team_reasoning}
            valueColor="text-brand-turquoise"
          />
        )}

        {hakim.impact_assessment && (
          <InsightRow
            icon={AlertTriangle}
            title="تقييم الأثر"
            detail={hakim.impact_assessment}
          />
        )}

        {hakim.technical_notes && (
          <InsightRow
            icon={FileText}
            title="ملاحظات فنية"
            detail={hakim.technical_notes}
          />
        )}

        {hakim.duplicate_ids?.length > 0 && (
          <div className="p-3 bg-amber-50 rounded-xl border border-amber-200">
            <div className="flex items-center gap-2 text-amber-700 text-xs font-medium">
              <AlertTriangle className="h-3.5 w-3.5" />
              {hakim.duplicate_ids.length} مشكلة مشابهة تم اكتشافها
            </div>
            {hakim.duplicate_note && (
              <p className="text-xs text-amber-600 mt-1">{hakim.duplicate_note}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function InsightRow({ icon: Icon, title, value, detail, valueColor = 'text-brand-navy' }) {
  return (
    <div className="p-3 bg-white rounded-xl border border-slate-100 hover:border-brand-turquoise/20 transition-colors">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="h-3.5 w-3.5 text-brand-turquoise/70" />
        <span className="text-[11px] text-muted-foreground font-medium">{title}</span>
      </div>
      {value && <p className={`text-sm font-semibold ${valueColor}`}>{value}</p>}
      {detail && <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{detail}</p>}
    </div>
  );
}
