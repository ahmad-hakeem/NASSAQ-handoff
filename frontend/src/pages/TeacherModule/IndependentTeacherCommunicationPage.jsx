import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Send, Users, UserPlus, MessageSquare } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Checkbox } from '../../components/ui/checkbox';

const COHORTS = [
  { id: 'my_students', icon: Users, labelKey: 'itCohortMyStudents' },
  { id: 'my_parents', icon: UserPlus, labelKey: 'itCohortMyParents' },
];

export default function IndependentTeacherCommunicationPage() {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError, nassaqSuccess } = useNassaqAlert();

  const [cohort, setCohort] = useState('my_students');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setSelected(new Set());
      try {
        const { data } = await api.get(
          `/independent-teacher/communication/recipients?cohort=${cohort}`,
        );
        if (cancelled) return;
        setItems(Array.isArray(data?.items) ? data.items : []);
      } catch (err) {
        if (cancelled) return;
        const msg = err?.response?.data?.detail
          || err?.response?.data?.error?.message
          || t('itLoadRecipientsFailed');
        nassaqError(msg);
        setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [api, cohort, nassaqError, t]);

  const toggle = useCallback((uid) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid); else next.add(uid);
      return next;
    });
  }, []);

  const allSelected = useMemo(
    () => items.length > 0 && items.every(i => selected.has(i.user_id)),
    [items, selected],
  );

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(items.map(i => i.user_id)));
  };

  const handleSend = async () => {
    if (!subject.trim() || !body.trim()) {
      nassaqError(t('itSubjectAndBodyRequired'));
      return;
    }
    if (selected.size === 0) {
      nassaqError(t('itPickRecipientsHint'));
      return;
    }
    setSending(true);
    try {
      await api.post('/notifications/bulk', {
        title: subject.trim(),
        message: body.trim(),
        notification_type: 'communication',
        priority: 'medium',
        recipient_ids: Array.from(selected),
      });
      nassaqSuccess(t('itSendSuccess'));
      setSubject('');
      setBody('');
      setSelected(new Set());
    } catch (err) {
      const msg = err?.response?.data?.detail
        || err?.response?.data?.error?.message
        || t('itSendFailure');
      nassaqError(msg);
    } finally {
      setSending(false);
    }
  };

  const dir = isRTL ? 'rtl' : 'ltr';
  const inputDir = isRTL ? 'rtl' : 'ltr';
  const inputAlign = isRTL ? 'text-right' : 'text-left';

  return (
    <div dir={dir} className="min-h-screen bg-slate-50 py-6 px-4">
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-emerald-800">{t('itCommHubTitle')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('itCommHubSubtitle')}</p>
        </div>

        <Card className="bg-white shadow-sm border-emerald-100">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center">
                <MessageSquare className="h-5 w-5 text-white" />
              </div>
              <div>
                <CardTitle className="text-lg text-emerald-800">{t('itRecipientsCardTitle')}</CardTitle>
                <CardDescription>{t('itRecipientsCardDesc')}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {COHORTS.map(c => {
                const Icon = c.icon;
                const on = cohort === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setCohort(c.id)}
                    className={`flex items-center gap-2 px-4 h-10 rounded-lg border transition ${on
                      ? 'bg-emerald-50 border-emerald-500 text-emerald-800'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-emerald-300'
                    }`}
                    data-testid={`it-cohort-tab-${c.id}`}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="text-sm font-medium">{t(c.labelKey)}</span>
                  </button>
                );
              })}
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-lg border border-dashed border-emerald-200 bg-emerald-50/40 p-6 text-center">
                <h3 className="text-base font-semibold text-emerald-800">{t('itNoRecipientsTitle')}</h3>
                <p className="text-sm text-slate-600 mt-1">{t('itNoRecipientsBody')}</p>
              </div>
            ) : (
              <>
                <label className="flex items-center gap-2 px-2">
                  <Checkbox checked={allSelected} onCheckedChange={toggleAll} data-testid="it-toggle-all" />
                  <span className="text-sm text-slate-700">
                    {t('itSelectAllWithCount', { count: items.length })}
                  </span>
                </label>
                <div className="max-h-72 overflow-y-auto divide-y divide-slate-100 rounded-lg border border-slate-200">
                  {items.map(item => {
                    const on = selected.has(item.user_id);
                    return (
                      <label
                        key={item.user_id}
                        className={`flex items-center gap-3 px-4 py-2 cursor-pointer transition ${on ? 'bg-emerald-50' : 'hover:bg-slate-50'}`}
                        data-testid={`it-recipient-${item.user_id}`}
                      >
                        <Checkbox checked={on} onCheckedChange={() => toggle(item.user_id)} />
                        <span className="text-sm text-slate-800 flex-1">{item.full_name || item.user_id}</span>
                      </label>
                    );
                  })}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="bg-white shadow-sm border-emerald-100">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg text-emerald-800">{t('itMessageCardTitle')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="mb-2 block">{t('itSubjectLabel')}</Label>
              <Input
                dir={inputDir}
                value={subject}
                onChange={e => setSubject(e.target.value)}
                className={`h-11 border-slate-200 focus:border-emerald-600 ${inputAlign}`}
                data-testid="it-msg-subject"
              />
            </div>
            <div>
              <Label className="mb-2 block">{t('itBodyLabel')}</Label>
              <Textarea
                dir={inputDir}
                rows={5}
                value={body}
                onChange={e => setBody(e.target.value)}
                className={`border-slate-200 focus:border-emerald-600 ${inputAlign}`}
                data-testid="it-msg-body"
              />
            </div>
            <div className="flex items-center justify-end">
              <Button
                onClick={handleSend}
                disabled={sending || loading}
                className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 h-11"
                data-testid="it-send-btn"
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin ms-2" /> : <Send className="h-4 w-4 ms-2" />}
                {t('itSendBtn')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
