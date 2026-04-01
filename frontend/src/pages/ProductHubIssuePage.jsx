import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Progress } from '../components/ui/progress';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import { Separator } from '../components/ui/separator';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ArrowRight, Brain, Bug, Clock, CheckCircle2, XCircle, Copy,
  Send, AlertTriangle, Timer, Shield, Eye, Zap, Lightbulb,
  Target, AlertOctagon, MessageSquare, Activity, FileText,
  Users, ChevronDown, ChevronUp, Loader2, ThumbsUp, ThumbsDown,
  Edit3, UserPlus
} from 'lucide-react';

const STATUS_CONFIG = {
  new: { label: 'جديد', color: 'bg-blue-500', textColor: 'text-blue-700', bgLight: 'bg-blue-50' },
  under_review: { label: 'تحت المراجعة', color: 'bg-orange-500', textColor: 'text-orange-700', bgLight: 'bg-orange-50' },
  in_progress: { label: 'قيد التنفيذ', color: 'bg-purple-500', textColor: 'text-purple-700', bgLight: 'bg-purple-50' },
  qa_validation: { label: 'تحقق الجودة', color: 'bg-cyan-500', textColor: 'text-cyan-700', bgLight: 'bg-cyan-50' },
  done: { label: 'مكتمل', color: 'bg-green-500', textColor: 'text-green-700', bgLight: 'bg-green-50' },
  rejected: { label: 'مرفوض', color: 'bg-red-500', textColor: 'text-red-700', bgLight: 'bg-red-50' },
  user_feedback_confirmed: { label: 'أكده المستخدم', color: 'bg-emerald-600', textColor: 'text-emerald-700', bgLight: 'bg-emerald-50' },
};

const PRIORITY_CONFIG = {
  critical: { label: 'حرج', color: 'bg-red-600' },
  high: { label: 'عالي', color: 'bg-orange-500' },
  medium: { label: 'متوسط', color: 'bg-yellow-500' },
  low: { label: 'منخفض', color: 'bg-gray-400' },
};

const STATUS_PROGRESS = {
  new: 10, under_review: 25, in_progress: 55, qa_validation: 80,
  done: 100, rejected: 100, user_feedback_confirmed: 100,
};

const STATUS_TRANSITIONS = {
  new: ['under_review', 'in_progress', 'rejected'],
  under_review: ['in_progress', 'rejected', 'done'],
  in_progress: ['qa_validation', 'under_review', 'done'],
  qa_validation: ['done', 'in_progress'],
  done: ['user_feedback_confirmed', 'under_review'],
  rejected: ['under_review'],
  user_feedback_confirmed: [],
};

const FINAL_STATUSES = new Set(['done', 'rejected', 'user_feedback_confirmed']);
const TEAMS = ['Frontend', 'Backend', 'DevOps', 'Design', 'QA', 'Product'];

export function ProductHubIssuePage() {
  const { issueId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [issue, setIssue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [showHakim, setShowHakim] = useState(true);
  const [showPrompt, setShowPrompt] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [statusNote, setStatusNote] = useState('');
  const [assignTeam, setAssignTeam] = useState('');

  const isAdmin = user?.role === 'platform_admin';

  const fetchIssue = useCallback(async () => {
    try {
      const res = await axios.get(`/api/product-hub/issues/${issueId}`);
      setIssue(res.data);
    } catch (e) {
      toast.error('فشل في تحميل المشكلة');
      navigate('/admin/product-hub');
    } finally {
      setLoading(false);
    }
  }, [issueId, navigate]);

  useEffect(() => { fetchIssue(); }, [fetchIssue]);

  const handleStatusChange = async (newStatus) => {
    if (FINAL_STATUSES.has(newStatus) && !isAdmin) {
      toast.error('فقط مدير المنصة يمكنه تغيير الحالة النهائية');
      return;
    }
    setUpdatingStatus(true);
    try {
      await axios.put(`/api/product-hub/issues/${issueId}/status`, {
        status: newStatus, note: statusNote
      });
      toast.success('تم تحديث الحالة');
      setStatusNote('');
      fetchIssue();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'فشل في تحديث الحالة');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleAssign = async () => {
    if (!assignTeam) return;
    try {
      await axios.put(`/api/product-hub/issues/${issueId}/assign`, {
        assigned_team: assignTeam
      });
      toast.success('تم التعيين');
      setAssignTeam('');
      fetchIssue();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'فشل في التعيين');
    }
  };

  const handleComment = async () => {
    if (!comment.trim()) return;
    setSubmittingComment(true);
    try {
      await axios.post(`/api/product-hub/issues/${issueId}/comments`, { content: comment });
      toast.success('تم إضافة التعليق');
      setComment('');
      fetchIssue();
    } catch (err) {
      toast.error('فشل في إضافة التعليق');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleCopyPrompt = async () => {
    try {
      const res = await axios.get(`/api/product-hub/issues/${issueId}/prompt`);
      setPrompt(res.data.prompt);
      setShowPrompt(true);
      await navigator.clipboard.writeText(res.data.prompt);
      toast.success('تم نسخ Prompt');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'غير مصرح');
    }
  };

  const handleFeedback = async (resolved) => {
    try {
      await axios.post(`/api/product-hub/issues/${issueId}/feedback`, { resolved });
      toast.success(resolved ? 'شكراً — تم تأكيد الحل' : 'تم إعادة فتح المشكلة');
      fetchIssue();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'فشل');
    }
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="flex justify-center items-center min-h-screen">
          <div className="animate-pulse text-brand-navy text-lg">جاري التحميل...</div>
        </div>
      </Sidebar>
    );
  }

  if (!issue) return null;

  const statusCfg = STATUS_CONFIG[issue.status] || STATUS_CONFIG.new;
  const priorityCfg = PRIORITY_CONFIG[issue.priority] || PRIORITY_CONFIG.medium;
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const hakim = issue.hakim_analysis || {};
  const allowedTransitions = STATUS_TRANSITIONS[issue.status] || [];

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30" dir="rtl">
        <div className="p-4 lg:p-6 space-y-6">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={() => navigate('/admin/product-hub')}>
                <ArrowRight className="h-4 w-4 ml-1" />
                رجوع
              </Button>
              <span className="text-sm text-muted-foreground font-mono">#{issue.issue_number}</span>
              <Badge className={`${statusCfg.color} text-white`}>{statusCfg.label}</Badge>
              <Badge className={`${priorityCfg.color} text-white`}>{priorityCfg.label}</Badge>
              {issue.sla_status === 'exceeded' && (
                <Badge className="bg-red-600 text-white animate-pulse">
                  <Timer className="h-3 w-3 ml-1" />
                  تجاوز SLA
                </Badge>
              )}
            </div>
            {isAdmin && (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleCopyPrompt}>
                  <Copy className="h-4 w-4 ml-1" />
                  نسخ Prompt
                </Button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <Card className="border shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-xl">{issue.title}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Progress value={progress} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1 text-left">{progress}%</p>
                  </div>
                  <Separator />
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                    <InfoField label="المُبلِّغ" value={issue.employee_name} />
                    <InfoField label="نوع الحساب" value={issue.account_type} />
                    <InfoField label="القسم" value={issue.section} />
                    <InfoField label="الصفحة" value={issue.page} />
                    <InfoField label="نوع المشكلة" value={issue.issue_type} />
                    <InfoField label="الفريق" value={issue.assigned_team || '—'} />
                    {issue.sla_remaining_hours !== undefined && (
                      <InfoField
                        label="SLA المتبقي"
                        value={`${Math.round(issue.sla_remaining_hours)} ساعة`}
                        className={issue.sla_status === 'exceeded' ? 'text-red-600' : 'text-green-600'}
                      />
                    )}
                    <InfoField label="تاريخ الإنشاء" value={new Date(issue.created_at).toLocaleDateString('ar-SA')} />
                  </div>
                  <Separator />
                  <div>
                    <h4 className="font-semibold text-sm mb-2">السلوك الحالي</h4>
                    <p className="text-sm bg-red-50 p-3 rounded-lg border border-red-100">{issue.current_behavior}</p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-sm mb-2">السلوك المتوقع</h4>
                    <p className="text-sm bg-green-50 p-3 rounded-lg border border-green-100">{issue.expected_behavior}</p>
                  </div>
                  {issue.steps_to_reproduce && (
                    <div>
                      <h4 className="font-semibold text-sm mb-2">خطوات إعادة الإنتاج</h4>
                      <p className="text-sm bg-gray-50 p-3 rounded-lg">{issue.steps_to_reproduce}</p>
                    </div>
                  )}
                  {issue.error_message && (
                    <div>
                      <h4 className="font-semibold text-sm mb-2">رسالة الخطأ</h4>
                      <p className="text-sm bg-red-50 p-3 rounded-lg font-mono text-xs">{issue.error_message}</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {issue.status === 'done' && issue.feedback_requested && (
                <Card className="border-2 border-amber-300 shadow-sm bg-amber-50/50">
                  <CardContent className="p-6 text-center space-y-4">
                    <Brain className="h-10 w-10 mx-auto text-amber-600" />
                    <h3 className="text-lg font-bold">تم حل المشكلة — هل تم حلها فعلاً؟</h3>
                    <div className="flex justify-center gap-4">
                      <Button onClick={() => handleFeedback(true)} className="bg-green-600 hover:bg-green-700 text-white">
                        <ThumbsUp className="h-4 w-4 ml-2" />
                        نعم، تم الحل
                      </Button>
                      <Button onClick={() => handleFeedback(false)} variant="outline" className="border-red-300 text-red-600 hover:bg-red-50">
                        <ThumbsDown className="h-4 w-4 ml-2" />
                        لا، لم يتم الحل
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {showPrompt && prompt && isAdmin && (
                <Card className="border shadow-sm border-brand-turquoise/30">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <FileText className="h-4 w-4 text-brand-turquoise" />
                      Generated Prompt
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="text-xs bg-gray-900 text-green-400 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed" dir="ltr">
                      {prompt}
                    </pre>
                  </CardContent>
                </Card>
              )}

              <Card className="border shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-brand-turquoise" />
                    التعليقات ({issue.comments?.length || 0})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {issue.comments?.map(c => (
                    <div key={c.id} className="flex gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback className="bg-brand-navy text-white text-xs">
                          {(c.user_name || '?')[0]}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-semibold text-foreground">{c.user_name}</span>
                          <span>•</span>
                          <span>{new Date(c.timestamp).toLocaleString('ar-SA')}</span>
                          {c.user_role === 'platform_admin' && (
                            <Badge variant="outline" className="text-[9px]">مدير</Badge>
                          )}
                        </div>
                        <p className="text-sm mt-1">{c.content}</p>
                      </div>
                    </div>
                  ))}
                  {(!issue.comments || issue.comments.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-4">لا توجد تعليقات بعد</p>
                  )}
                  <Separator />
                  <div className="flex gap-2">
                    <Textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="أضف تعليقاً..."
                      className="text-right min-h-[60px] flex-1"
                    />
                    <Button
                      onClick={handleComment}
                      disabled={!comment.trim() || submittingComment}
                      className="bg-brand-navy hover:bg-brand-navy/90 text-white self-end"
                    >
                      {submittingComment ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="border shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="h-4 w-4 text-brand-turquoise" />
                    سجل النشاط
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {issue.activity_log?.map((a, i) => (
                      <div key={a.id || i} className="flex items-start gap-3 text-sm">
                        <div className="w-2 h-2 rounded-full bg-brand-turquoise mt-2 flex-shrink-0" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium">{a.action_by_name || 'النظام'}</span>
                            <span className="text-muted-foreground">—</span>
                            <span className="text-muted-foreground">{_actionLabel(a.action)}</span>
                          </div>
                          {a.details && Object.keys(a.details).length > 0 && (
                            <div className="text-xs text-muted-foreground mt-1">
                              {a.details.from && a.details.to && (
                                <span>{STATUS_CONFIG[a.details.from]?.label || a.details.from} → {STATUS_CONFIG[a.details.to]?.label || a.details.to}</span>
                              )}
                              {a.details.note && <span className="block">{a.details.note}</span>}
                              {a.details.team && <span className="block">الفريق: {a.details.team}</span>}
                            </div>
                          )}
                          <span className="text-[10px] text-muted-foreground">{new Date(a.timestamp).toLocaleString('ar-SA')}</span>
                        </div>
                      </div>
                    ))}
                    {(!issue.activity_log || issue.activity_log.length === 0) && (
                      <p className="text-sm text-muted-foreground text-center py-4">لا يوجد نشاط</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              {hakim && Object.keys(hakim).length > 0 && (
                <Card className="border shadow-sm border-brand-turquoise/30 bg-gradient-to-br from-brand-turquoise/5 to-transparent">
                  <CardHeader className="pb-2 cursor-pointer" onClick={() => setShowHakim(!showHakim)}>
                    <CardTitle className="text-base flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Brain className="h-5 w-5 text-brand-turquoise" />
                        تحليل حكيم
                      </span>
                      {showHakim ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </CardTitle>
                  </CardHeader>
                  {showHakim && (
                    <CardContent className="space-y-3 text-sm">
                      {hakim.priority_reasoning && (
                        <div className="p-3 bg-white rounded-lg border">
                          <p className="text-xs text-muted-foreground mb-1">الأولوية المقترحة</p>
                          <p className="font-medium">{PRIORITY_CONFIG[hakim.suggested_priority]?.label || hakim.suggested_priority}</p>
                          <p className="text-xs text-muted-foreground mt-1">{hakim.priority_reasoning}</p>
                        </div>
                      )}
                      {hakim.team_reasoning && (
                        <div className="p-3 bg-white rounded-lg border">
                          <p className="text-xs text-muted-foreground mb-1">الفريق المقترح</p>
                          <p className="font-medium">{hakim.suggested_team}</p>
                          <p className="text-xs text-muted-foreground mt-1">{hakim.team_reasoning}</p>
                        </div>
                      )}
                      {hakim.impact_assessment && (
                        <div className="p-3 bg-white rounded-lg border">
                          <p className="text-xs text-muted-foreground mb-1">تقييم الأثر</p>
                          <p className="text-xs">{hakim.impact_assessment}</p>
                        </div>
                      )}
                      {hakim.technical_notes && (
                        <div className="p-3 bg-white rounded-lg border">
                          <p className="text-xs text-muted-foreground mb-1">ملاحظات فنية</p>
                          <p className="text-xs">{hakim.technical_notes}</p>
                        </div>
                      )}
                      {hakim.duplicate_note && (
                        <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                          <p className="text-xs text-amber-700">{hakim.duplicate_note}</p>
                        </div>
                      )}
                      {hakim.duplicate_ids?.length > 0 && (
                        <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                          <p className="text-xs text-muted-foreground mb-1">مشاكل مشابهة</p>
                          <p className="text-xs">{hakim.duplicate_ids.length} مشكلة مشابهة تم اكتشافها</p>
                        </div>
                      )}
                    </CardContent>
                  )}
                </Card>
              )}

              {isAdmin && allowedTransitions.length > 0 && (
                <Card className="border shadow-sm">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Shield className="h-4 w-4 text-brand-navy" />
                      إجراءات الإدارة
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div>
                      <p className="text-xs text-muted-foreground mb-2">تغيير الحالة</p>
                      <div className="flex flex-wrap gap-2">
                        {allowedTransitions.map(s => {
                          const cfg = STATUS_CONFIG[s] || {};
                          return (
                            <Button
                              key={s}
                              size="sm"
                              variant="outline"
                              onClick={() => handleStatusChange(s)}
                              disabled={updatingStatus}
                              className="text-xs"
                            >
                              {cfg.label || s}
                            </Button>
                          );
                        })}
                      </div>
                      <Input
                        value={statusNote}
                        onChange={(e) => setStatusNote(e.target.value)}
                        placeholder="ملاحظة (اختياري)"
                        className="mt-2 text-right text-sm"
                      />
                    </div>
                    <Separator />
                    <div>
                      <p className="text-xs text-muted-foreground mb-2">تعيين الفريق</p>
                      <div className="flex gap-2">
                        <Select value={assignTeam} onValueChange={setAssignTeam}>
                          <SelectTrigger className="flex-1 text-sm"><SelectValue placeholder="اختر الفريق" /></SelectTrigger>
                          <SelectContent>
                            {TEAMS.map(t => (
                              <SelectItem key={t} value={t}>{t}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button size="sm" onClick={handleAssign} disabled={!assignTeam}>
                          <UserPlus className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card className="border shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-muted-foreground">معلومات النظام</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-xs">
                  <InfoRow label="الجهاز" value={issue.device} />
                  <InfoRow label="المتصفح" value={issue.browser} />
                  {issue.url && <InfoRow label="URL" value={issue.url} />}
                  <InfoRow label="المُنشئ" value={issue.created_by_name} />
                  <InfoRow label="الدور" value={issue.created_by_role} />
                  {issue.resolved_at && <InfoRow label="تاريخ الحل" value={new Date(issue.resolved_at).toLocaleString('ar-SA')} />}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </Sidebar>
  );
}

function InfoField({ label, value, className }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`font-medium ${className || ''}`}>{value || '—'}</p>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium truncate max-w-[150px]">{value || '—'}</span>
    </div>
  );
}

function _actionLabel(action) {
  const MAP = {
    issue_created: 'أنشأ المشكلة',
    status_changed: 'غيّر الحالة',
    issue_assigned: 'عيّن الفريق',
    comment_added: 'أضاف تعليق',
    feedback_submitted: 'قدّم ملاحظات',
    title_updated: 'حدّث العنوان',
    priority_changed: 'غيّر الأولوية',
  };
  return MAP[action] || action;
}

export default ProductHubIssuePage;
