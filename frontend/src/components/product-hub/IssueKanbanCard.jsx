import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain, MessageSquare, Paperclip, ArrowUpRight } from 'lucide-react';
import { PriorityBadge } from './PriorityBadge';
import { SLAIndicator } from './SLAIndicator';
import { TYPE_CONFIG, STATUS_PROGRESS } from './hubConstants';

function getProgressGradient(progress, status) {
  if (status === 'rejected') return 'from-red-400 to-red-500';
  if (progress >= 100) return 'from-emerald-400 to-emerald-500';
  if (progress >= 75) return 'from-emerald-300 to-emerald-500';
  if (progress >= 50) return 'from-brand-turquoise/80 to-brand-turquoise';
  if (progress >= 25) return 'from-amber-300 to-amber-500';
  return 'from-red-300 to-red-500';
}

function getProgressColor(progress, status) {
  if (status === 'rejected') return '#ef4444';
  if (progress >= 75) return '#10b981';
  if (progress >= 50) return '#46C1BE';
  if (progress >= 25) return '#f59e0b';
  return '#ef4444';
}

function getInitials(name) {
  if (!name) return '؟';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return parts[0][0] + parts[1][0];
  return parts[0].slice(0, 2);
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
  const commentCount = issue.discussion?.length || 0;
  const attachmentCount = issue.attachments?.length || 0;

  return (
    <div
      onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
      className="group relative bg-white rounded-xl border border-slate-200/80 hover:border-brand-turquoise/50 shadow-[0_1px_3px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_25px_rgba(70,193,190,0.12)] transition-all duration-300 cursor-pointer overflow-hidden"
    >
      <div
        className={`absolute inset-x-0 top-0 h-[3px] bg-gradient-to-l ${getProgressGradient(progress, issue.status)} transition-all duration-500`}
        style={{ width: `${progress}%`, minWidth: progress > 0 ? '8px' : '0' }}
      />

      <div className="p-3.5 pt-4">
        <div className="flex items-center justify-between gap-1.5 mb-2">
          <div className="flex items-center gap-1.5">
            <div className={`flex items-center justify-center w-5 h-5 rounded-md ${typeCfg.bgClass || 'bg-slate-100'}`}>
              <TypeIcon className={`h-3 w-3 ${typeCfg.color}`} />
            </div>
            <span className="text-[10px] text-slate-400 font-mono tracking-tight">#{issue.issue_number}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <PriorityBadge priority={issue.priority} size="sm" />
            <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              <ArrowUpRight className="h-3 w-3 text-brand-turquoise" />
            </div>
          </div>
        </div>

        <h4 className={`text-[13px] font-bold leading-[1.5] line-clamp-2 mb-2.5 transition-colors duration-200 ${isDone ? 'text-emerald-600 line-through decoration-emerald-300/60 decoration-1' : isRejected ? 'text-red-400 line-through decoration-red-200/60 decoration-1' : 'text-slate-800 group-hover:text-brand-navy'}`}>
          {issue.title}
        </h4>

        {issue.section && (
          <div className="flex items-center gap-1.5 mb-2.5">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-100 truncate max-w-full">
              {issue.section}
            </span>
            {issue.assigned_team && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-turquoise/5 text-brand-turquoise border border-brand-turquoise/15 font-medium truncate">
                {issue.assigned_team}
              </span>
            )}
          </div>
        )}

        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: getProgressColor(progress, issue.status) }}
              />
              <span className="text-[9px] font-semibold" style={{ color: getProgressColor(progress, issue.status) }}>
                {progress}%
              </span>
            </div>
            <span className="text-[9px] text-slate-400">
              {isDone ? '✓ مكتمل' : isRejected ? '✕ مرفوض' : 'التقدم'}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-[5px] overflow-hidden">
            <div
              className={`h-full rounded-full bg-gradient-to-l ${getProgressGradient(progress, issue.status)} transition-all duration-700 ease-out`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-2.5 border-t border-slate-100">
          <div className="flex items-center gap-2 min-w-0">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0"
              style={{
                background: isDone ? 'linear-gradient(135deg, #10b981, #059669)' :
                             isRejected ? 'linear-gradient(135deg, #ef4444, #dc2626)' :
                             'linear-gradient(135deg, #1C3D74, #46C1BE)'
              }}
            >
              {getInitials(issue.employee_name)}
            </div>
            <span className="text-[10px] text-slate-500 truncate">{issue.employee_name}</span>
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            {commentCount > 0 && (
              <span className="inline-flex items-center gap-0.5 text-[9px] text-slate-400">
                <MessageSquare className="h-2.5 w-2.5" />
                {commentCount}
              </span>
            )}
            {attachmentCount > 0 && (
              <span className="inline-flex items-center gap-0.5 text-[9px] text-slate-400">
                <Paperclip className="h-2.5 w-2.5" />
                {attachmentCount}
              </span>
            )}
            <SLAIndicator issue={issue} size="sm" />
            {hasDuplicates && (
              <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-amber-50 border border-amber-200">
                <Brain className="h-2.5 w-2.5 text-amber-500" />
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
