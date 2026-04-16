import { useState } from 'react';
import { useTranslation } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { toast } from 'sonner';

const DEFAULT_MESSAGE = (name, issue) =>
  `ولي أمر ${name} الكريم، نود إبلاغكم بأن ابنكم/ابنتكم بحاجة لمتابعة بخصوص ${issue}. نرجو التواصل مع المدرسة.`;

function plusDays(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

const TITLE_KEY = {
  notify_parent: 'sendParentMessage',
  remedial_plan: 'createRemedialPlan',
  schedule_followup: 'scheduleFollowup',
};

const SUCCESS_KEY = {
  notify_parent: 'messageSentToParent',
  remedial_plan: 'remedialPlanCreated',
  schedule_followup: 'followupScheduled',
};

export default function InterventionActionModal({ student, actionType, onClose, onSuccess }) {
  const { t } = useTranslation();
  const { api } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(
    DEFAULT_MESSAGE(student.name, student.issue_label_ar || ''),
  );
  const [description, setDescription] = useState('');
  const [targetDate, setTargetDate] = useState(plusDays(14));
  const [milestones, setMilestones] = useState(['']);
  const [followUpDate, setFollowUpDate] = useState(plusDays(7));
  const [notes, setNotes] = useState('');

  async function submit() {
    setSubmitting(true);
    try {
      const data =
        actionType === 'notify_parent'
          ? { message, issue_type: student.issue_type }
          : actionType === 'remedial_plan'
            ? {
                issue_type: student.issue_type,
                description,
                target_date: targetDate,
                milestones: milestones.map((m) => m.trim()).filter(Boolean),
              }
            : { follow_up_date: followUpDate, notes, issue_type: student.issue_type };

      await api.post('/ai/insights/intervention', {
        student_id: student.student_id,
        action_type: actionType,
        data,
      });
      toast.success(t(SUCCESS_KEY[actionType]));
      onSuccess();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent dir="rtl" className="font-tajawal">
        <DialogHeader>
          <DialogTitle>{t(TITLE_KEY[actionType])}</DialogTitle>
        </DialogHeader>

        {actionType === 'notify_parent' && (
          <Textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={5} />
        )}

        {actionType === 'remedial_plan' && (
          <div className="space-y-3">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('planDescription')}
              rows={4}
            />
            <div>
              <label className="text-sm">{t('targetDate')}</label>
              <Input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
            </div>
            <div>
              <label className="text-sm">{t('milestones')}</label>
              {milestones.map((m, i) => (
                <Input
                  key={i}
                  value={m}
                  className="mt-2"
                  onChange={(e) => {
                    const cp = [...milestones];
                    cp[i] = e.target.value;
                    setMilestones(cp);
                  }}
                />
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() => setMilestones([...milestones, ''])}
              >
                +
              </Button>
            </div>
          </div>
        )}

        {actionType === 'schedule_followup' && (
          <div className="space-y-3">
            <div>
              <label className="text-sm">{t('followupDate')}</label>
              <Input
                type="date"
                value={followUpDate}
                onChange={(e) => setFollowUpDate(e.target.value)}
              />
            </div>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('followupNotes')}
              rows={3}
            />
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t('cancel')}</Button>
          <Button
            onClick={submit}
            disabled={submitting}
            style={{ background: '#1C3D74', color: 'white' }}
          >
            {t('confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
