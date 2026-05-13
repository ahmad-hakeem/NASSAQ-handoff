/**
 * Independent-Teacher §6.7 — Cross-workspace co-teaching tab.
 * Task #210.
 *
 * Renders inside TeacherClassDetailPage as the "المتعاونون" tab.
 *
 * The host IT can:
 *   - Invite a single collaborator IT by email + scope (read|write).
 *   - Cancel a pending invite or revoke an active link via NassaqAlertDialog.
 *   - See the one-shot raw token exactly once (so they can copy + send).
 *
 * Read endpoint: GET /independent-teacher/workspace-collaborators?class_id=
 * Write endpoints: POST .../workspace-collaborators (create), POST .../{id}/cancel,
 * DELETE .../{id}.
 *
 * No native browser dialogs; toast.error is reserved for transient feedback
 * only — every confirmation/warning surfaces through NassaqAlertDialog.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Mail, ShieldCheck, Eye, Pencil, RefreshCw, Trash2, Plus, Copy } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../ui/dialog';

const STATUS_VARIANT = {
  pending: 'secondary',
  accepted: 'default',
  cancelled: 'outline',
  revoked: 'destructive',
  expired: 'destructive',
};

export default function CollaboratorsTab({ classId }) {
  const { api } = useAuth();
  const { t, isRTL } = useTranslation();
  const { confirm, warn, info } = useNassaqAlert();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteScope, setInviteScope] = useState('read');
  const [submitting, setSubmitting] = useState(false);
  const [tokenToShow, setTokenToShow] = useState(null);

  const fetchList = useCallback(async () => {
    if (!classId) return;
    setLoading(true);
    try {
      const res = await api.get('/independent-teacher/workspace-collaborators', {
        params: { class_id: classId },
      });
      setItems(res?.data?.items || []);
    } catch (err) {
      const msg = err?.response?.data?.detail || t('collabFetchFailed');
      warn({ title: t('collabError'), description: msg });
    } finally {
      setLoading(false);
    }
  }, [api, classId, t, warn]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const submitInvite = useCallback(async () => {
    if (!inviteEmail.trim()) {
      warn({ title: t('collabError'), description: t('collabEmailRequired') });
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/independent-teacher/workspace-collaborators', {
        class_id: classId,
        collaborator_email: inviteEmail.trim().toLowerCase(),
        scope: { mode: inviteScope },
      });
      const data = res?.data || {};
      setShowInvite(false);
      setInviteEmail('');
      setInviteScope('read');
      if (data.token) {
        setTokenToShow({ email: data.collaborator_email, token: data.token });
      } else if (data.reused) {
        info({ title: t('collabInviteReusedTitle'), description: t('collabInviteReusedBody') });
      }
      await fetchList();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      warn({ title: t('collabError'), description: detail || t('collabInviteFailed') });
    } finally {
      setSubmitting(false);
    }
  }, [api, classId, fetchList, info, inviteEmail, inviteScope, t, warn]);

  const cancelRow = useCallback(async (row) => {
    const ok = await confirm({
      title: t('collabCancelConfirmTitle'),
      description: t('collabCancelConfirmBody').replace('{0}', row.collaborator_email || ''),
      confirmText: t('collabCancelConfirmAction'),
    });
    if (!ok) return;
    try {
      await api.post(`/independent-teacher/workspace-collaborators/${row.id}/cancel`);
      await fetchList();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      warn({ title: t('collabError'), description: detail || t('collabActionFailed') });
    }
  }, [api, confirm, fetchList, t, warn]);

  const revokeRow = useCallback(async (row) => {
    const ok = await confirm({
      title: t('collabRevokeConfirmTitle'),
      description: t('collabRevokeConfirmBody').replace('{0}', row.collaborator_email || ''),
      confirmText: t('collabRevokeConfirmAction'),
      variant: 'destructive',
    });
    if (!ok) return;
    try {
      await api.delete(`/independent-teacher/workspace-collaborators/${row.id}`);
      await fetchList();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      warn({ title: t('collabError'), description: detail || t('collabActionFailed') });
    }
  }, [api, confirm, fetchList, t, warn]);

  const sortedItems = useMemo(() => {
    const order = { pending: 0, accepted: 1, expired: 2, cancelled: 3, revoked: 4 };
    return [...items].sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));
  }, [items]);

  const copyToken = useCallback(async () => {
    if (!tokenToShow?.token) return;
    try {
      await navigator.clipboard.writeText(tokenToShow.token);
      toast.success(t('collabTokenCopied'));
    } catch {
      // navigator.clipboard may be unavailable; the input is also selectable.
    }
  }, [t, tokenToShow]);

  return (
    <div className="space-y-4" dir={isRTL ? 'rtl' : 'ltr'}>
      <Card>
        <CardContent className="p-4 sm:p-6 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h3 className="text-lg font-bold font-cairo text-brand-navy dark:text-brand-turquoise">
                {t('collabTabTitle')}
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                {t('collabTabSubtitle')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline" size="sm"
                onClick={fetchList} disabled={loading}
                aria-label={t('refresh')}
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
              <Button
                size="sm" className="gap-1.5"
                onClick={() => setShowInvite(true)}
              >
                <Plus className="h-4 w-4" />
                {t('collabInviteAction')}
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin me-2" />
              {t('loading')}
            </div>
          ) : sortedItems.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground font-cairo">
              {t('collabEmptyState')}
            </div>
          ) : (
            <ul className="divide-y divide-border/50">
              {sortedItems.map(row => (
                <li key={row.id} className="py-3 flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-3 min-w-0">
                    <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{row.collaborator_email}</div>
                      <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                        <Badge variant={STATUS_VARIANT[row.status] || 'outline'}>
                          {t(`collabStatus_${row.status}`)}
                        </Badge>
                        <span className="inline-flex items-center gap-1">
                          {row?.scope?.mode === 'write' ? (
                            <Pencil className="h-3 w-3" />
                          ) : (
                            <Eye className="h-3 w-3" />
                          )}
                          {t(`collabScope_${row?.scope?.mode || 'read'}`)}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {row.status === 'pending' && (
                      <Button
                        variant="ghost" size="sm" className="text-destructive"
                        onClick={() => cancelRow(row)}
                      >
                        {t('cancel')}
                      </Button>
                    )}
                    {row.status === 'accepted' && (
                      <Button
                        variant="ghost" size="sm" className="text-destructive gap-1.5"
                        onClick={() => revokeRow(row)}
                      >
                        <Trash2 className="h-4 w-4" />
                        {t('collabRevokeAction')}
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Dialog open={showInvite} onOpenChange={setShowInvite}>
        <DialogContent dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-brand-turquoise" />
              {t('collabInviteDialogTitle')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <p className="text-sm text-muted-foreground">{t('collabInviteDialogBody')}</p>
            <div className="space-y-2">
              <Label>{t('collabEmailLabel')}</Label>
              <Input
                type="email" autoComplete="off" dir="ltr"
                placeholder="teacher@example.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('collabScopeLabel')}</Label>
              <Select value={inviteScope} onValueChange={setInviteScope}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="read">{t('collabScope_read')}</SelectItem>
                  <SelectItem value="write">{t('collabScope_write')}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t('collabScopeHelp')}</p>
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowInvite(false)} disabled={submitting}>
              {t('cancel')}
            </Button>
            <Button onClick={submitInvite} disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : null}
              {t('collabSendInvite')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!tokenToShow} onOpenChange={(o) => !o && setTokenToShow(null)}>
        <DialogContent dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo">{t('collabTokenDialogTitle')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-2">
            <p className="text-sm text-muted-foreground">
              {(t('collabTokenDialogBody') || '').replace('{0}', tokenToShow?.email || '')}
            </p>
            <div className="rounded-md border border-border bg-muted/40 p-3">
              <code dir="ltr" className="block text-[11px] break-all whitespace-pre-wrap font-mono">
                {tokenToShow?.token}
              </code>
            </div>
            <p className="text-xs text-amber-600 dark:text-amber-400">{t('collabTokenOnceWarning')}</p>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setTokenToShow(null)}>{t('done')}</Button>
            <Button onClick={copyToken} className="gap-1.5">
              <Copy className="h-4 w-4" />
              {t('copy')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
