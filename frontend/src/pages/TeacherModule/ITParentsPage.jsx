import { useCallback, useEffect, useMemo, useState } from 'react';
import React from 'react';
import {
  Users, Loader2, KeyRound, Copy, Eye, EyeOff, UserPlus, RefreshCw,
  Search, ShieldCheck, Mail, Phone, CheckCircle2, Clock, CircleSlash,
  Link2,
} from 'lucide-react';

import Sidebar from '../../components/layout/Sidebar';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../components/ui/dialog';
import { getApiErrorMessage } from '../../utils/apiError';

const PORTAL_BADGE = {
  active: { icon: CheckCircle2, key: 'itParentPortalActive', cls: 'border-emerald-300 bg-emerald-50 text-emerald-700' },
  pending: { icon: Clock, key: 'itParentPortalPending', cls: 'border-amber-300 bg-amber-50 text-amber-700' },
  none: { icon: CircleSlash, key: 'itParentPortalNone', cls: 'border-slate-300 bg-slate-50 text-slate-600' },
};

// §5.7 step-up envelope is replayed by the global axios interceptor after
// passkey assertion; we must NOT surface it as a hard error toast.
const STEP_UP_CODES = new Set([
  'MFA_STEPUP_REQUIRED', 'MFA_PASSKEY_REQUIRED', 'MFA_RESTORE_REQUIRED',
]);

function isStepUpError(err) {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  return (status === 401 || status === 403)
    && typeof detail === 'object'
    && STEP_UP_CODES.has(detail?.code);
}

function PortalStateBadge({ state }) {
  const { t } = useTranslation();
  const meta = PORTAL_BADGE[state] || PORTAL_BADGE.none;
  const Icon = meta.icon;
  return (
    <Badge variant="outline" className={`gap-1 ${meta.cls}`}>
      <Icon className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
      <span className="text-xs">{t(meta.key)}</span>
    </Badge>
  );
}

export function ITParentsPanel({ embedded = false } = {}) {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError, nassaqSuccess, nassaqConfirm } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [parents, setParents] = useState([]);
  const [pending, setPending] = useState([]);
  const [search, setSearch] = useState('');

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [credParent, setCredParent] = useState(null);
  const [credForm, setCredForm] = useState({ new_email: '', new_password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [credSaving, setCredSaving] = useState(false);
  const [credResult, setCredResult] = useState(null);

  // Materialize/link flow — reuses the canonical IT invite-parent writer
  // (POST /independent-teacher/students/{id}/invite-parent), the same path
  // the Students tab uses. No ad-hoc frontend insert.
  const [linkTarget, setLinkTarget] = useState(null);
  const [linkForm, setLinkForm] = useState({
    full_name: '', phone: '', email: '', national_id: '', relationship: 'guardian',
  });
  const [linkSaving, setLinkSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/independent-teacher/parents');
      setParents(Array.isArray(data?.parents) ? data.parents : []);
      setPending(Array.isArray(data?.pending) ? data.pending : []);
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || t('itParentsLoadFailed'));
      setParents([]);
      setPending([]);
    } finally {
      setLoading(false);
    }
  }, [api, nassaqError, t]);

  useEffect(() => { load(); }, [load]);

  const filteredParents = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return parents;
    return parents.filter(p =>
      (p.full_name || '').toLowerCase().includes(q)
      || (p.phone || '').toLowerCase().includes(q)
      || (p.email || '').toLowerCase().includes(q)
      || (p.national_id || '').toLowerCase().includes(q),
    );
  }, [parents, search]);

  const openDetail = useCallback(async (parentId) => {
    setDetail({ loading: true });
    setDetailLoading(true);
    try {
      const { data } = await api.get(`/independent-teacher/parents/${parentId}`);
      setDetail(data);
    } catch (err) {
      setDetail(null);
      nassaqError(getApiErrorMessage(err) || t('itParentDetailFailed'));
    } finally {
      setDetailLoading(false);
    }
  }, [api, nassaqError, t]);

  const openCredentials = useCallback((parent) => {
    setCredParent(parent);
    setCredForm({ new_email: '', new_password: '' });
    setCredResult(null);
    setShowPassword(false);
  }, []);

  const openLink = useCallback((student) => {
    setLinkTarget(student);
    setLinkForm({
      full_name: student.pending_parent_name || '',
      phone: student.pending_parent_phone || '',
      email: student.pending_parent_email || '',
      national_id: '',
      relationship: 'guardian',
    });
  }, []);

  const copyToClipboard = useCallback((text, label) => {
    if (!text) return;
    navigator.clipboard.writeText(text)
      .then(() => nassaqSuccess(t('itCopied', { what: label }) || t('itCopiedGeneric')))
      .catch(() => nassaqError(t('itCopyFailed')));
  }, [nassaqError, nassaqSuccess, t]);

  // Sensitive mutation — gate behind NassaqAlertDialog confirmation before
  // calling the canonical link writer (spec step 7).
  const handleLink = useCallback(() => {
    if (!linkTarget) return;
    const f = linkForm;
    if (!f.phone?.trim() && !f.email?.trim() && !f.national_id?.trim()) {
      nassaqError(t('itLinkContactRequired'));
      return;
    }
    nassaqConfirm(
      t('itLinkParentConfirmBody', { name: linkTarget.student_name || '' })
        || t('itLinkParentConfirmBodyGeneric'),
      async () => {
        setLinkSaving(true);
        try {
          const body = {
            full_name: f.full_name?.trim() || null,
            phone: f.phone?.trim() || null,
            email: f.email?.trim() || null,
            national_id: f.national_id?.trim() || null,
            relationship: f.relationship || 'guardian',
          };
          await api.post(
            `/independent-teacher/students/${linkTarget.student_id}/invite-parent`,
            body,
          );
          setLinkTarget(null);
          await load();
          nassaqSuccess(t('itLinkParentSuccess'));
        } catch (err) {
          if (!isStepUpError(err)) {
            nassaqError(getApiErrorMessage(err) || t('itLinkParentFailed'));
          }
        } finally {
          setLinkSaving(false);
        }
      },
      {
        title: t('itLinkParentConfirmTitle'),
        confirmText: t('itLinkParentSubmit'),
        cancelText: t('cancel'),
        type: 'info',
      },
    );
  }, [api, linkTarget, linkForm, load, nassaqConfirm, nassaqError, nassaqSuccess, t]);

  // Sensitive mutation — confirm before invalidating the old login secret
  // (spec step 7). The actual rotation runs inside the confirm callback.
  const handleRotate = useCallback(() => {
    if (!credParent) return;
    if (credForm.new_password && credForm.new_password.length < 6) {
      nassaqError(t('itParentPasswordTooShort'));
      return;
    }
    nassaqConfirm(
      credParent.full_name
        ? t('itRotateConfirmBody', { name: credParent.full_name })
        : t('itRotateConfirmBodyGeneric'),
      async () => {
        setCredSaving(true);
        try {
          const reqBody = {};
          if (credForm.new_email.trim()) reqBody.new_email = credForm.new_email.trim();
          if (credForm.new_password.trim()) reqBody.new_password = credForm.new_password.trim();
          const { data } = await api.put(
            `/independent-teacher/parents/${credParent.id}/credentials`, reqBody,
          );
          setCredResult(data);
          nassaqSuccess(t('itParentCredentialsSaved'));
          load();
        } catch (err) {
          if (!isStepUpError(err)) {
            nassaqError(getApiErrorMessage(err) || t('itParentCredentialsFailed'));
          }
        } finally {
          setCredSaving(false);
        }
      },
      {
        title: t('itRotateConfirmTitle'),
        confirmText: t('itRotateConfirmBtn'),
        cancelText: t('cancel'),
        type: 'warning',
      },
    );
  }, [api, credParent, credForm, load, nassaqConfirm, nassaqError, nassaqSuccess, t]);

  const dir = isRTL ? 'rtl' : 'ltr';
  const inputAlign = isRTL ? 'text-right' : 'text-left';

  const body = (
    <div className={embedded ? 'w-full space-y-6' : 'mx-auto max-w-5xl space-y-6 p-4 lg:p-6'}>
      {!embedded && (
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-emerald-800">{t('itParentsTitle')}</h1>
            <p className="text-sm text-slate-500 mt-1">{t('itParentsSubtitle')}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="h-9 px-3 flex items-center gap-1.5 border-emerald-200 text-emerald-700">
              <Users className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
              {t('itParentsLinkedCount', { count: parents.length })}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              className="h-9 gap-1.5"
              onClick={load}
              disabled={loading}
              data-testid="it-parents-refresh"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.5} aria-hidden="true" />
              <span className="hidden sm:inline">{t('refresh')}</span>
            </Button>
          </div>
        </div>
      )}

      {embedded && (
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <Badge variant="outline" className="h-9 px-3 flex items-center gap-1.5 border-emerald-200 text-emerald-700">
            <Users className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
            {t('itParentsLinkedCount', { count: parents.length })}
          </Badge>
          <Button
            size="sm"
            variant="outline"
            className="h-9 gap-1.5"
            onClick={load}
            disabled={loading}
            data-testid="it-parents-refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.5} aria-hidden="true" />
            <span className="hidden sm:inline">{t('refresh')}</span>
          </Button>
        </div>
      )}

      <Card className="bg-white shadow-sm border-emerald-100">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center">
                <Users className="h-5 w-5 text-white" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <div>
                <CardTitle className="text-lg text-emerald-800">{t('itParentsListTitle')}</CardTitle>
                <CardDescription>{t('itParentsListDesc')}</CardDescription>
              </div>
            </div>
            <div className="relative w-full sm:w-64">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" strokeWidth={1.5} aria-hidden="true" />
              <Input
                dir={dir}
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder={t('search')}
                className={`h-10 ps-9 border-slate-200 ${inputAlign}`}
                data-testid="it-parents-search"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-600" aria-hidden="true" />
            </div>
          ) : filteredParents.length === 0 ? (
            <div className="rounded-lg border border-dashed border-emerald-200 bg-emerald-50/40 p-8 text-center">
              <h3 className="text-base font-semibold text-emerald-800">{t('itParentsEmptyTitle')}</h3>
              <p className="text-sm text-slate-600 mt-1">{t('itParentsEmptyBody')}</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 overflow-hidden">
              {filteredParents.map(p => (
                <div
                  key={p.id}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition flex-wrap"
                  data-testid={`it-parent-row-${p.id}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-slate-800 truncate">{p.full_name || '—'}</span>
                      <PortalStateBadge state={p.portal_state} />
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 flex-wrap">
                      {p.phone && (
                        <span className="flex items-center gap-1">
                          <Phone className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />{p.phone}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
                        {t('itParentChildrenCount', { count: p.children_count })}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 text-xs"
                      onClick={() => openDetail(p.id)}
                      data-testid={`it-parent-detail-${p.id}`}
                    >
                      {t('view')}
                    </Button>
                    <Button
                      size="sm"
                      className="h-8 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => openCredentials(p)}
                      data-testid={`it-parent-creds-${p.id}`}
                    >
                      <KeyRound className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                      {t('itParentCredentialsBtn')}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {pending.length > 0 && (
        <Card className="bg-white shadow-sm border-amber-100">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500 flex items-center justify-center">
                <UserPlus className="h-5 w-5 text-white" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <div>
                <CardTitle className="text-lg text-amber-800">{t('itPendingParentsTitle')}</CardTitle>
                <CardDescription>{t('itPendingParentsDesc')}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 overflow-hidden">
              {pending.map(s => (
                <div
                  key={s.student_id}
                  className="flex items-center gap-3 px-4 py-3 flex-wrap"
                  data-testid={`it-pending-row-${s.student_id}`}
                >
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-semibold text-slate-800">{s.student_name || '—'}</span>
                    {s.class_name && <span className="text-xs text-slate-400 ms-2">{s.class_name}</span>}
                    <div className="text-xs text-slate-500 mt-1">
                      {s.pending_parent_name || t('itPendingParentNoName')}
                      {s.pending_parent_phone ? ` · ${s.pending_parent_phone}` : ''}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    className="h-8 text-xs gap-1.5 bg-amber-500 hover:bg-amber-600 text-white"
                    onClick={() => openLink(s)}
                    data-testid={`it-pending-link-${s.student_id}`}
                  >
                    <Link2 className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                    {t('itLinkParentBtn')}
                  </Button>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-400 mt-3">{t('itPendingParentsHint')}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );

  return (
    <>
      {body}

      {/* Parent detail dialog */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent dir={dir} className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-emerald-800">{t('itParentDetailTitle')}</DialogTitle>
          </DialogHeader>
          {detailLoading || detail?.loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-600" aria-hidden="true" />
            </div>
          ) : detail ? (
            <div className="space-y-4">
              <div>
                <div className="text-lg font-semibold text-slate-800">{detail.full_name || '—'}</div>
                <div className="flex flex-col gap-1 mt-2 text-sm text-slate-600">
                  {detail.email && (
                    <span className="flex items-center gap-2"><Mail className="h-4 w-4 text-slate-400" strokeWidth={1.5} aria-hidden="true" />{detail.email}</span>
                  )}
                  {detail.phone && (
                    <span className="flex items-center gap-2"><Phone className="h-4 w-4 text-slate-400" strokeWidth={1.5} aria-hidden="true" />{detail.phone}</span>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">{t('itParentPortalAccount')}</span>
                  <PortalStateBadge state={detail.user_account?.portal_state} />
                </div>
                {detail.user_account?.login_email && (
                  <div className="text-xs text-slate-500 mt-2 flex items-center gap-2">
                    <ShieldCheck className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                    {detail.user_account.login_email}
                  </div>
                )}
              </div>

              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">
                  {t('itParentChildrenCount', { count: detail.children_count || 0 })}
                </div>
                {detail.children?.length ? (
                  <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                    {detail.children.map(c => (
                      <div key={c.id} className="flex items-center justify-between px-3 py-2">
                        <span className="text-sm text-slate-800">{c.name}</span>
                        {c.class_name && <span className="text-xs text-slate-400">{c.class_name}</span>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">{t('itParentNoChildren')}</p>
                )}
              </div>

              <DialogFooter>
                <Button
                  className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                  onClick={() => { const p = detail; setDetail(null); openCredentials({ id: p.id, full_name: p.full_name }); }}
                >
                  <KeyRound className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                  {t('itParentCredentialsBtn')}
                </Button>
              </DialogFooter>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Materialize / link parent dialog */}
      <Dialog open={!!linkTarget} onOpenChange={(o) => { if (!o) setLinkTarget(null); }}>
        <DialogContent dir={dir} className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-emerald-800 flex items-center gap-2">
              <Link2 className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
              {t('itLinkParentTitle')}
            </DialogTitle>
            <DialogDescription>
              {linkTarget?.student_name
                ? t('itLinkParentFor', { name: linkTarget.student_name })
                : t('itLinkParentDesc')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="mb-1.5 block text-sm">{t('itLinkNameLabel')}</Label>
              <Input
                dir={dir}
                value={linkForm.full_name}
                onChange={e => setLinkForm(p => ({ ...p, full_name: e.target.value }))}
                className={`h-10 ${inputAlign}`}
                data-testid="it-link-name"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-sm">{t('itLinkPhoneLabel')}</Label>
              <Input
                dir="ltr"
                value={linkForm.phone}
                onChange={e => setLinkForm(p => ({ ...p, phone: e.target.value }))}
                className="h-10"
                data-testid="it-link-phone"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-sm">{t('itLinkEmailLabel')}</Label>
              <Input
                dir="ltr"
                type="email"
                value={linkForm.email}
                onChange={e => setLinkForm(p => ({ ...p, email: e.target.value }))}
                className="h-10"
                data-testid="it-link-email"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-sm">{t('itLinkNationalIdLabel')}</Label>
              <Input
                dir="ltr"
                value={linkForm.national_id}
                onChange={e => setLinkForm(p => ({ ...p, national_id: e.target.value }))}
                className="h-10"
                data-testid="it-link-national-id"
              />
            </div>
            <p className="text-xs text-slate-400">{t('itLinkContactRequired')}</p>
            <DialogFooter>
              <Button variant="outline" onClick={() => setLinkTarget(null)} disabled={linkSaving}>
                {t('cancel')}
              </Button>
              <Button
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                onClick={handleLink}
                disabled={linkSaving}
                data-testid="it-link-submit"
              >
                {linkSaving
                  ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  : <Link2 className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
                {t('itLinkParentSubmit')}
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      {/* Credentials rotation dialog */}
      <Dialog open={!!credParent} onOpenChange={(o) => { if (!o) { setCredParent(null); setCredResult(null); } }}>
        <DialogContent dir={dir} className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-emerald-800 flex items-center gap-2">
              <KeyRound className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
              {t('itParentCredentialsTitle')}
            </DialogTitle>
            <DialogDescription>
              {credParent?.full_name
                ? t('itParentCredentialsFor', { name: credParent.full_name })
                : t('itParentCredentialsDesc')}
            </DialogDescription>
          </DialogHeader>

          {credResult ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-4 space-y-3">
                <p className="text-xs text-emerald-700">{t('itParentCredentialsResultHint')}</p>
                <div>
                  <Label className="text-xs text-slate-500">{t('email')}</Label>
                  <div className="flex items-center gap-2 mt-1">
                    <Input readOnly value={credResult.login_email || ''} className="h-9 text-sm" dir="ltr" />
                    <Button size="icon" variant="ghost" className="h-9 w-9 shrink-0" onClick={() => copyToClipboard(credResult.login_email, t('email'))}>
                      <Copy className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                    </Button>
                  </div>
                </div>
                <div>
                  <Label className="text-xs text-slate-500">{t('password')}</Label>
                  <div className="flex items-center gap-2 mt-1">
                    <Input readOnly value={credResult.password || ''} className="h-9 text-sm font-mono" dir="ltr" />
                    <Button size="icon" variant="ghost" className="h-9 w-9 shrink-0" onClick={() => copyToClipboard(credResult.password, t('password'))}>
                      <Copy className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                    </Button>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => { setCredParent(null); setCredResult(null); }}>
                  {t('done')}
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <Label className="mb-1.5 block text-sm">{t('itParentNewEmailLabel')}</Label>
                <Input
                  dir="ltr"
                  type="email"
                  value={credForm.new_email}
                  onChange={e => setCredForm(p => ({ ...p, new_email: e.target.value }))}
                  placeholder={t('itParentNewEmailPlaceholder')}
                  className="h-10"
                  data-testid="it-parent-new-email"
                />
              </div>
              <div>
                <Label className="mb-1.5 block text-sm">{t('itParentNewPasswordLabel')}</Label>
                <div className="relative">
                  <Input
                    dir="ltr"
                    type={showPassword ? 'text' : 'password'}
                    value={credForm.new_password}
                    onChange={e => setCredForm(p => ({ ...p, new_password: e.target.value }))}
                    placeholder={t('itParentNewPasswordPlaceholder')}
                    className="h-10 pe-10"
                    data-testid="it-parent-new-password"
                  />
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                    onClick={() => setShowPassword(s => !s)}
                  >
                    {showPassword
                      ? <EyeOff className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                      : <Eye className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
                  </Button>
                </div>
                <p className="text-xs text-slate-400 mt-1">{t('itParentPasswordAutoHint')}</p>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setCredParent(null)} disabled={credSaving}>
                  {t('cancel')}
                </Button>
                <Button
                  className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                  onClick={handleRotate}
                  disabled={credSaving}
                  data-testid="it-parent-creds-submit"
                >
                  {credSaving
                    ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    : <KeyRound className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
                  {t('itParentGenerateBtn')}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function ITParentsPage() {
  const { isRTL } = useTheme();
  const dir = isRTL ? 'rtl' : 'ltr';
  return (
    <Sidebar>
      <div dir={dir} className="min-h-screen bg-slate-50">
        <ITParentsPanel embedded={false} />
      </div>
    </Sidebar>
  );
}
