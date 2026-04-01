import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain, Timer } from 'lucide-react';
import { PriorityBadge } from './PriorityBadge';
import { SLAIndicator } from './SLAIndicator';
import { TYPE_CONFIG, STATUS_PROGRESS } from './hubConstants';
import { Progress } from '../ui/progress';

export function IssueKanbanCard({ issue }) {
  const navigate = useNavigate();
  const typeCfg = TYPE_CONFIG[issue.issue_type] || TYPE_CONFIG.other;
  const TypeIcon = typeCfg.icon;
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const hasDuplicates = issue.hakim_analysis?.duplicate_ids?.length > 0 ||
                        issue.ai?.duplicate_detected;

  return (
    <div
      onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
      className="group bg-white rounded-xl border border-slate-200 p-3.5 shadow-sm hover:shadow-md hover:border-brand-turquoise/40 transition-all cursor-pointer"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-[10px] text-muted-foreground font-mono">#{issue.issue_number}</span>
        <PriorityBadge priority={issue.priority} size="sm" />
      </div>

      <h4 className="text-sm font-semibold text-brand-navy leading-snug line-clamp-2 mb-2">
        {issue.title}
      </h4>

      <div className="flex items-center gap-2 text-[11px] text-muted-foreground mb-2">
        <TypeIcon className={`h-3 w-3 ${typeCfg.color}`} />
        <span>{issue.section}</span>
        {issue.assigned_team && (
          <>
            <span className="text-slate-300">|</span>
            <span className="text-brand-turquoise font-medium">{issue.assigned_team}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-1 mb-2">
        <Progress value={progress} className="h-1 flex-1" />
        <span className="text-[10px] text-muted-foreground min-w-[28px] text-left">{progress}%</span>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">{issue.employee_name}</span>
        <div className="flex items-center gap-1.5">
          <SLAIndicator issue={issue} size="sm" />
          {hasDuplicates && (
            <span className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200">
              <Brain className="h-2.5 w-2.5" />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
