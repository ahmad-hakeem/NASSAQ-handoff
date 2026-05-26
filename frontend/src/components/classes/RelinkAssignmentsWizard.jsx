import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Link2, CheckSquare, Square } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Badge } from '../ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../ui/accordion';
import { useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';

const GROUP_ORDER = [
  'teacher_assignments',
  'teacher_class_assignments',
  'class_subjects',
  'timetable_sessions',
  'class_sessions',
  'curriculum_lessons',
];

const GROUP_LABEL_KEY = {
  teacher_assignments: 'relinkGroupTeacherAssignments',
  teacher_class_assignments: 'relinkGroupTeacherClassAssignments',
  class_subjects: 'relinkGroupClassSubjects',
  timetable_sessions: 'relinkGroupTimetableSessions',
  class_sessions: 'relinkGroupClassSessions',
  curriculum_lessons: 'relinkGroupCurriculumLessons',
};

const dash = (v) => (v == null || v === '' ? '—' : v);

const describeRow = (table, row, t) => {
  if (table === 'teacher_assignments') {
    return `${dash(row.teacher_name)} · ${dash(row.subject_name)}${
      row.weekly_sessions ? ` · ${row.weekly_sessions}/wk` : ''
    }`;
  }
  if (table === 'teacher_class_assignments') {
    return dash(row.teacher_name || row.teacher_id);
  }
  if (table === 'class_subjects') {
    return `${dash(row.subject_name || row.subject_id)}${
      row.weekly_periods ? ` · ${row.weekly_periods}/wk` : ''
    }`;
  }
  if (table === 'timetable_sessions') {
    const d = row.day_of_week != null ? `${t('day') || 'Day'} ${row.day_of_week}` : '';
    const p = row.period_number != null ? `${t('period') || 'Period'} ${row.period_number}` : '';
    return [d, p].filter(Boolean).join(' · ') || dash(row.id);
  }
  if (table === 'class_sessions') {
    return `${dash(row.date)}${row.status ? ` · ${row.status}` : ''}`;
  }
  if (table === 'curriculum_lessons') {
    return `${dash(row.title)}${row.week ? ` · W${row.week}` : ''}`;
  }
  return dash(row.id);
};

export const RelinkAssignmentsWizard = ({ open, onOpenChange, classId, api, onDone }) => {
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [groups, setGroups] = useState({});
  const [selected, setSelected] = useState({});

  useEffect(() => {
    if (!open || !classId) return undefined;
    let cancelled = false;
    setLoading(true);
    setGroups({});
    setSelected({});
    api
      .get(`/classes/${classId}/relink-candidates`)
      .then((res) => {
        if (cancelled) return;
        const g = res.data?.groups || {};
        setGroups(g);
        const preset = {};
        Object.entries(g).forEach(([table, info]) => {
          preset[table] = new Set((info.items || []).map((r) => r.id));
        });
        setSelected(preset);
      })
      .catch((err) => {
        if (cancelled) return;
        nassaqError(err.response?.data?.detail || t('relinkFailedToLoad'));
        onOpenChange(false);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, classId, api]); // eslint-disable-line react-hooks/exhaustive-deps

  const totals = useMemo(() => {
    let total = 0;
    let chosen = 0;
    Object.entries(groups).forEach(([table, info]) => {
      total += info.count || 0;
      chosen += (selected[table]?.size) || 0;
    });
    return { total, chosen };
  }, [groups, selected]);

  const toggleRow = (table, id) => {
    setSelected((prev) => {
      const next = { ...prev };
      const cur = new Set(next[table] || []);
      if (cur.has(id)) cur.delete(id);
      else cur.add(id);
      next[table] = cur;
      return next;
    });
  };

  const setAll = (table, on) => {
    setSelected((prev) => {
      const next = { ...prev };
      const items = groups[table]?.items || [];
      next[table] = new Set(on ? items.map((r) => r.id) : []);
      return next;
    });
  };

  const apply = async ({ all }) => {
    if (!classId) return;
    if (!all && totals.chosen === 0) {
      nassaqError(t('relinkNoSelection'));
      return;
    }
    setSubmitting(true);
    let totalReactivated = 0;
    const failures = [];
    try {
      for (const table of GROUP_ORDER) {
        const info = groups[table];
        if (!info || info.count === 0) continue;
        const ids = all ? null : Array.from(selected[table] || []);
        if (!all && ids.length === 0) continue;
        try {
          const res = await api.post(
            `/classes/${classId}/relink/${table}`,
            all ? { all: true } : { ids },
          );
          totalReactivated += res.data?.reactivated || 0;
        } catch (err) {
          failures.push({ table, detail: err.response?.data?.detail });
        }
      }
      if (failures.length === 0) {
        toast.success(
          t('relinkRowsReactivated').replace('{{count}}', String(totalReactivated)),
        );
      } else {
        nassaqError(t('relinkPartial'));
      }
      onOpenChange(false);
      if (onDone) onDone();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !submitting && onOpenChange(v)}>
      <DialogContent className="sm:max-w-[680px] max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Link2 className="h-5 w-5 text-brand-turquoise" aria-hidden="true" strokeWidth={1.5} />
            {t('relinkWizardTitle')}
          </DialogTitle>
          <DialogDescription>{t('relinkWizardDescription')}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto pe-1">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" />
            </div>
          ) : totals.total === 0 ? (
            <div className="py-12 text-center text-muted-foreground text-sm">
              {t('relinkNothingToDo')}
            </div>
          ) : (
            <Accordion
              type="multiple"
              defaultValue={GROUP_ORDER.filter((g) => (groups[g]?.count || 0) > 0)}
              className="w-full"
            >
              {GROUP_ORDER.map((table) => {
                const info = groups[table];
                if (!info || info.count === 0) return null;
                const items = info.items || [];
                const sel = selected[table] || new Set();
                const allOn = sel.size === items.length && items.length > 0;
                return (
                  <AccordionItem key={table} value={table}>
                    <AccordionTrigger className="hover:no-underline">
                      <div className="flex items-center gap-2 flex-1 text-start">
                        <span className="font-medium">{t(GROUP_LABEL_KEY[table])}</span>
                        <Badge variant="outline" className="rounded-lg">
                          {sel.size} / {info.count}
                        </Badge>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="flex items-center gap-2 mb-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setAll(table, true)}
                          className="rounded-lg"
                        >
                          <CheckSquare
                            className="h-4 w-4 me-1"
                            aria-hidden="true"
                            strokeWidth={1.5}
                          />
                          {t('relinkSelectAll')}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setAll(table, false)}
                          className="rounded-lg"
                        >
                          <Square
                            className="h-4 w-4 me-1"
                            aria-hidden="true"
                            strokeWidth={1.5}
                          />
                          {t('relinkClearAll')}
                        </Button>
                      </div>
                      <ul className="space-y-1 max-h-56 overflow-y-auto rounded-lg border border-border/50 p-2">
                        {items.map((row) => {
                          const checked = sel.has(row.id);
                          return (
                            <li
                              key={row.id}
                              className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-muted/40"
                            >
                              <Checkbox
                                checked={checked}
                                onCheckedChange={() => toggleRow(table, row.id)}
                                id={`relink-${table}-${row.id}`}
                              />
                              <label
                                htmlFor={`relink-${table}-${row.id}`}
                                className="text-sm font-tajawal cursor-pointer flex-1"
                              >
                                {describeRow(table, row, t)}
                              </label>
                            </li>
                          );
                        })}
                      </ul>
                      {info.count > items.length && (
                        <p className="text-xs text-muted-foreground mt-2">
                          {info.count - items.length}+
                        </p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            className="rounded-xl"
          >
            {t('relinkSkip')}
          </Button>
          {!loading && totals.total > 0 && (
            <>
              <Button
                type="button"
                variant="secondary"
                onClick={() => apply({ all: true })}
                disabled={submitting}
                className="rounded-xl"
                data-testid="relink-apply-all"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin me-2" aria-hidden="true" />
                ) : null}
                {t('relinkApplyAll')}
              </Button>
              <Button
                type="button"
                onClick={() => apply({ all: false })}
                disabled={submitting || totals.chosen === 0}
                className="bg-brand-navy rounded-xl"
                data-testid="relink-apply-selected"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin me-2" aria-hidden="true" />
                ) : null}
                {t('relinkApply')} ({totals.chosen})
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default RelinkAssignmentsWizard;
