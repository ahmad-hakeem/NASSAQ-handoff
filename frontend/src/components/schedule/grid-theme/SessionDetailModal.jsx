/**
 * SessionDetailModal — glass-morphism cell-click pop-up.
 *
 * Pure visual + a11y wiring. Quick actions delegate back to the parent
 * grid via onEdit / onMove / onLockToggle so the existing edit/drag/lock
 * pipelines remain authoritative. Pass `hideActions` to render in a
 * read-only / visual mode (no footer buttons) — used by the master grid
 * where the surrounding page does not yet expose those handlers.
 */
import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Pencil, Move, Lock, Unlock, MapPin } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '../../ui/avatar';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { useTranslation } from '../../../contexts/ThemeContext';
import { getDayBandClass, getDayTextOnBand } from './dayPalette';

export default function SessionDetailModal({
  open,
  session,
  onClose,
  onEdit,
  onMove,
  onLockToggle,
  hideActions = false,
}) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && session && (
        <motion.div
          key="session-modal"
          data-testid="session-detail-modal"
          className="fixed inset-0 z-[100] flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          <div
            data-testid="session-detail-backdrop"
            onClick={onClose}
            className="absolute inset-0 bg-[rgba(28,61,116,0.35)] backdrop-blur-md"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="session-detail-title"
            initial={{ scale: 0.95, opacity: 0, y: 8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.97, opacity: 0, y: 4 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="relative w-[420px] max-w-[92vw] rounded-2xl bg-white/75 backdrop-blur-2xl border border-brand-navy/15 shadow-[0_20px_60px_-15px_rgba(28,61,116,0.35)] overflow-hidden"
          >
            <div
              id="session-detail-title"
              className={`${getDayBandClass(session.day_of_week)} ${getDayTextOnBand(session.day_of_week)} px-4 py-2 text-sm font-cairo font-bold text-center`}
            >
              {t(session.day_of_week)} · {t('periodNumberLabel', { n: session.slot_number })}
              {(session.start_time || session.end_time) && (
                <> · {session.start_time || ''}{session.start_time && session.end_time ? ' - ' : ''}{session.end_time || ''}</>
              )}
            </div>

            <button
              type="button"
              data-testid="session-detail-close"
              onClick={onClose}
              aria-label={t('closeAction')}
              className="absolute top-2 start-2 h-7 w-7 inline-flex items-center justify-center rounded-full bg-white/70 hover:bg-white text-brand-navy/80 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="p-5 space-y-4">
              <div className="text-center">
                <h3 className="text-xl font-cairo font-bold text-brand-navy">
                  {session.subject_name}
                </h3>
                <p className="text-sm font-tajawal text-brand-navy/70 mt-0.5">
                  {session.class_name}
                </p>
              </div>

              {session.teacher_name && (
                <div className="flex items-center gap-3 bg-white/50 rounded-xl p-2.5 border border-brand-navy/10">
                  <Avatar className="h-9 w-9 flex-shrink-0">
                    <AvatarImage src={session.teacher_avatar_url} alt={session.teacher_name} />
                    <AvatarFallback className="bg-brand-navy text-white text-xs">
                      {(session.teacher_name || '?').split(' ').map((n) => n[0]).join('').slice(0, 2)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-cairo font-semibold text-brand-navy truncate">
                      {session.teacher_name || t('teacher2')}
                    </p>
                    <p className="text-[11px] font-tajawal text-brand-navy/60 truncate">
                      {session.teacher_specialty || ''}
                    </p>
                  </div>
                </div>
              )}

              {session.room && (
                <div className="inline-flex items-center gap-1.5 text-xs font-tajawal text-brand-navy/80 bg-brand-turquoise/10 border border-brand-turquoise/30 rounded-full px-2.5 py-1">
                  <MapPin className="h-3 w-3" />
                  {session.room}
                </div>
              )}

              <div className="flex flex-wrap gap-1.5">
                {session.is_locked && (
                  <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700">
                    <Lock className="h-2.5 w-2.5 me-1" />
                    {t('lockedBadge')}
                  </Badge>
                )}
                {session.is_relocated && (
                  <Badge variant="outline" className="text-[10px] border-orange-300 text-orange-700">
                    {t('relocatedBadge')}
                  </Badge>
                )}
                {session.is_substitute && (
                  <Badge variant="outline" className="text-[10px] border-violet-300 text-violet-700">
                    {t('substituteShortLabel')}
                  </Badge>
                )}
              </div>

              {!hideActions && (
                <div className="flex gap-2 pt-1">
                  <Button
                    data-testid="session-action-edit"
                    onClick={() => onEdit?.(session)}
                    className="flex-1 bg-brand-turquoise hover:bg-brand-turquoise-dark text-white gap-1.5"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    {t('editAction')}
                  </Button>
                  <Button
                    data-testid="session-action-move"
                    variant="outline"
                    onClick={() => onMove?.(session)}
                    className="flex-1 gap-1.5"
                  >
                    <Move className="h-3.5 w-3.5" />
                    {t('moveAction')}
                  </Button>
                  <Button
                    data-testid="session-action-lock"
                    variant="outline"
                    onClick={() => onLockToggle?.(session)}
                    className="flex-1 gap-1.5"
                  >
                    {session.is_locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                    {session.is_locked ? t('unlockAction') : t('lockAction')}
                  </Button>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
