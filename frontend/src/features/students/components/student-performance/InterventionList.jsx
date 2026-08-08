import { useTranslation } from '@/shared/contexts/ThemeContext';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '@/shared/components/ui/dropdown-menu';
import { Button } from '@/shared/components/ui/button';

const BADGE = {
  at_risk: { bg: '#fee2e2', fg: '#ef4444' },
  needs_followup: { bg: '#fef3c7', fg: '#eab308' },
};

export default function InterventionList({ items, onAction }) {
  const { t } = useTranslation();
  if (!items?.length) {
    return (
      <div className="rounded-xl bg-white p-5 text-center text-neutral-500 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
        {t('noStudentsAtRisk')}
      </div>
    );
  }
  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <h3 className="text-lg font-cairo text-[#1C3D74] mb-3">{t('studentsNeedIntervention')}</h3>
      <ul className="divide-y divide-[#EAECED]">
        {items.map((s) => {
          const b = BADGE[s.category] || BADGE.needs_followup;
          return (
            <li key={s.student_id} className="py-3 flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="font-bold text-[#312E2F] truncate">{s.name}</div>
                <div className="text-xs text-neutral-500">
                  {s.class_name} · {s.issue_label_ar}
                </div>
              </div>
              <span
                className="text-xs rounded-full px-2 py-1 shrink-0"
                style={{ background: b.bg, color: b.fg }}
              >
                {t(s.category === 'at_risk' ? 'educationalRisk' : 'needsFollowup')}
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" style={{ background: '#46C1BE', color: 'white' }}>
                    {t('takeAction')}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem
                    disabled={!s.parent_id}
                    onSelect={() => onAction(s, 'notify_parent')}
                  >
                    {t('sendParentMessage')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => onAction(s, 'remedial_plan')}>
                    {t('createRemedialPlan')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => onAction(s, 'schedule_followup')}>
                    {t('scheduleFollowup')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
