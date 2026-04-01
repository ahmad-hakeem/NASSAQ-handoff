import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain } from 'lucide-react';
import { PriorityBadge } from './PriorityBadge';
import { SLAIndicator } from './SLAIndicator';
import { TYPE_CONFIG, STATUS_PROGRESS } from './hubConstants';

function getProgressGradient(progress, status) {
  if (status === 'rejected') return 'from-red-300 to-red-500';
  if (progress >= 100) return 'from-emerald-400 to-emerald-600';
  if (progress >= 75) return 'from-emerald-300 to-emerald-500';
  if (progress >= 50) return 'from-brand-turquoise/80 to-brand-turquoise';
  if (progress >= 25) return 'from-amber-300 to-amber-500';
  return 'from-red-300 to-red-500';
}

function getProgressTextColor(progress, status) {
  if (status === 'rejected') return 'text-red-500';
  if (progress >= 100) return 'text-emerald-600';
  if (progress >= 75) return 'text-emerald-500';
  if (progress >= 50) return 'text-brand-turquoise';
  if (progress >= 25) return 'text-amber-500';
  return 'text-red-500';
}

export function IssueKanbanCard({ issue }) {
  const navigate = useNavigate();
  const typeCfg = TYPE_CONFIG[issue.issue_type] || TYPE_CONFIG.other;
  const TypeIcon = typeCfg.icon;
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const hasDuplicates = issue.hakim_analysis?.duplicate_ids?.length > 0 ||
                        issue.ai?.duplicate_detected;
  const isDone = issue.status === 'done' || issue.status === 'user_feedback_confirmed';
  const isRejected = issue.status === 'rejected';

  return (
    <div
      onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
      className={`group bg-white rounded-xl border p-3 shadow-sm hover:shadow-md transition-all cursor-pointer overflow-hidden relative ${isDone ? 'border-emerald-200 bg-emerald-50/20' : isRejected ? 'border-red-200 bg-red-50/10' : 'border-slate-200 hover:border-brand-turquoise/40'}`}
    >
      <div className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-l ${getProgressGradient(progress, issue.status)}`} style={{ width: `${progress}%`, minWidth: progress > 0 ? '4px' : '0' }} />

      <div className="flex items-start justify-between gap-1.5 mb-1.5">
        <span className="text-[9px] text-muted-foreground font-mono bg-slate-50 px-1 py-0.5 rounded">#{issue.issue_number}</span>
        <PriorityBadge priority={issue.priority} size="sm" />
      </div>

      <h4 className={`text-[13px] font-semibold leading-snug line-clamp-2 mb-2 ${isDone ? 'text-emerald-700 line-through decoration-emerald-300' : isRejected ? 'text-red-400 line-through decoration-red-200' : 'text-brand-navy group-hover:text-brand-turquoise'}`}>
        {issue.title}
      </h4>

      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-2">
        <TypeIcon className={`h-2.5 w-2.5 ${typeCfg.color}`} />
        <span className="truncate">{issue.section}</span>
        {issue.assigned_team && (
          <>
            <span className="text-slate-200">|</span>
            <span className="text-brand-turquoise font-medium truncate">{issue.assigned_team}</span>
          </>
        )}
      </div>

      <div className="mb-2">
        <div className="flex items-center justify-between mb-0.5">
          <span className={`text-[9px] font-bold ${getProgressTextColor(progress, issue.status)}`}>{progress}%</span>
          <span className="text-[8px] text-muted-foreground">
            {isDone ? 'مكتمل' : isRejected ? 'مرفوض' : 'التقدم'}
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-1.5 rounded-full bg-gradient-to-l ${getProgressGradient(progress)} transition-all duration-500`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[9px] text-muted-foreground truncate max-w-[100px]">{issue.employee_name}</span>
        <div className="flex items-center gap-1">
          <SLAIndicator issue={issue} size="sm" />
          {hasDuplicates && (
            <span className="inline-flex items-center text-[8px] px-1 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200">
              <Brain className="h-2 w-2" />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
