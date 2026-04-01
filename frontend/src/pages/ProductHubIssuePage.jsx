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
  StatusChip, PriorityBadge, SLAIndicator, HakimInsightCard, EmptyState,
  STATUS_CONFIG, TYPE_CONFIG, STATUS_PROGRESS,
  FINAL_STATUSES, TEAMS, EVENT_LABELS, COMMENT_TYPE_CONFIG, IMPACT_LABELS,
  formatDualDate, formatDualDateTime, formatDualDateCompact,
} from '../components/product-hub';
import {
  ArrowRight, Brain, Copy, Send, Shield, MessageSquare, Activity,
  FileText, Loader2, ThumbsUp, ThumbsDown, UserPlus, ChevronDown, ChevronUp,
  Monitor, Globe, Eye, AlertTriangle, CheckCircle2, ClipboardCheck,
} from 'lucide-react';

const authHeaders = () => {
  const t = localStorage.getItem('nassaq_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export function ProductHubIssuePage() {
  const { issueId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [issue, setIssue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState('');
  const [commentType, setCommentType] = useState('general');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [statusNote, setStatusNote] = useState('');
  const [assignTeam, setAssignTeam] = useState('');
  const [expandedSections, setExpandedSections] = useState({ timeline: false });

  const isAdmin = user?.role === 'platform_admin';
  const perms = issue?.permissions || {};
  const isMainAdmin = perms.is_main_admin || false;

  const fetchIssue = useCallback(async () => {
    try {
      const res = await axios.get(`/api/product-hub/issues/${issueId}`, { headers: authHeaders() });
      setIssue(res.data);
    } catch (e) {
      toast.error('فشل في تحميل التحدي');
      navigate('/admin/product-hub');
    } finally {
      setLoading(false);
    }
  }, [issueId, navigate]);

  useEffect(() => { fetchIssue(); }, [fetchIssue]);

  const handleStatusChange = async (newStatus) => {
    if (FINAL_STATUSES.has(newStatus) && !isMainAdmin) {
      toast.error('هذا الإجراء مقصور على المديرين الأساسيين فقط');
      return;
    }
    setUpdatingStatus(true);
    try {
      await axios.put(`/api/product-hub/issues/${issueId}/status`, {
        status: newStatus, note: statusNote
      }, { headers: authHeaders() });
      toast.success('تم تحديث الحالة');
      setStatusNote('');
      fetchIssue();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في تحديث الحالة'));
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleAssign = async () => {
    if (!assignTeam) return;
    try {
      await axios.put(`/api/product-hub/issues/${issueId}/assign`, { assigned_team: assignTeam }, { headers: authHeaders() });
      toast.success('تم التعيين');
      setAssignTeam('');
      fetchIssue();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في التعيين'));
    }
  };

  const handleComment = async () => {
    if (!comment.trim()) return;
    setSubmittingComment(true);
    try {
      await axios.post(`/api/product-hub/issues/${issueId}/comments`, {
        content: comment, comment_type: isMainAdmin ? commentType : 'general'
      }, { headers: authHeaders() });
      toast.success('تم إضافة التعليق');
      setComment('');
      setCommentType('general');
      fetchIssue();
    } catch (err) {
      toast.error('فشل في إضافة التعليق');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleCopyPrompt = async () => {
    try {
      const res = await axios.get(`/api/product-hub/issues/${issueId}/prompt`, { headers: authHeaders() });
      setPrompt(res.data.prompt);
      setShowPrompt(true);
      await navigator.clipboard.writeText(res.data.prompt);
      toast.success('تم نسخ Prompt');
    } catch (err) {
      toast.error(err.response?.data?.detail?.message || 'غير مصرح');
    }
  };

  const handleFeedback = async (resolved) => {
    try {
      await axios.post(`/api/product-hub/issues/${issueId}/feedback`, { resolved }, { headers: authHeaders() });
      toast.success(resolved ? 'شكراً — تم تأكيد الحل' : 'تم إعادة فتح التحدي');
      fetchIssue();
    } catch (err) {
      toast.error(err.response?.data?.detail?.message || 'فشل');
    }
  };

  const toggleSection = (key) => {
    setExpandedSections(s => ({ ...s, [key]: !s[key] }));
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="flex justify-center items-center min-h-screen">
          <div className="flex flex-col items-center gap-3">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-brand-turquoise border-t-transparent" />
            <p className="text-sm text-muted-foreground">جاري تحميل التحدي...</p>
          </div>
        </div>
      </Sidebar>
    );
  }

  if (!issue) return null;

  const typeCfg = TYPE_CONFIG[issue.issue_type] || TYPE_CONFIG.other;
  const TypeIcon = typeCfg.icon;
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const hakim = issue.hakim_analysis || {};
  const allowedTransitions = issue.valid_transitions || [];
  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/20" dir="rtl">
        <div className="p-4 lg:p-8 max-w-[1400px] mx-auto space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <Button variant="outline" size="sm" onClick={() => navigate('/admin/product-hub')} className="rounded-lg mt-1">
                <ArrowRight className="h-4 w-4 ml-1" />
                رجوع
              </Button>
              <div>
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="text-xs text-muted-foreground font-mono bg-slate-100 px-2 py-0.5 rounded">#{issue.issue_number}</span>
                  <StatusChip status={issue.status} showIcon />
                  <PriorityBadge priority={issue.priority} showIcon />
                  <SLAIndicator issue={issue} />
                </div>
                <h1 className="text-xl lg:text-2xl font-bold text-brand-navy leading-tight">{issue.title}</h1>
                <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground flex-wrap">
                  <span className="flex items-center gap-1">
                    <TypeIcon className={`h-3.5 w-3.5 ${typeCfg.color}`} />
                    {typeCfg.label}
                  </span>
                  <span>•</span>
                  <span>{issue.employee_name}</span>
                  <span>•</span>
                  <span>{issue.section} › {issue.page}</span>
                  <span>•</span>
                  <span>{formatDualDateCompact(issue.created_at)}</span>
                </div>
              </div>
            </div>
            {isAdmin && (
              <div className="flex items-center gap-2 flex-shrink-0">
                <Button variant="outline" size="sm" onClick={handleCopyPrompt} className="rounded-lg gap-1.5">
                  <Copy className="h-3.5 w-3.5" />
                  نسخ Prompt
                </Button>
              </div>
            )}
          </div>

          <div className="w-full">
            <div className="flex items-center gap-3 mb-1.5">
              <span className="text-xs text-muted-foreground">التقدم</span>
              <span className="text-xs font-semibold text-brand-navy">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>

          {issue.status === 'done' && issue.feedback_requested && !issue.feedback_response && (
            <Card className="border-2 border-amber-300 shadow-md bg-gradient-to-r from-amber-50 to-amber-50/50 rounded-xl">
              <CardContent className="p-6 text-center space-y-4">
                <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-amber-100 mx-auto">
                  <Brain className="h-8 w-8 text-amber-600" />
                </div>
                <h3 className="text-lg font-bold text-brand-navy">تم المعالجة — هل تمت بنجاح؟</h3>
                <p className="text-sm text-muted-foreground">رأيك يساعدنا في تحسين جودة الحلول</p>
                <div className="flex justify-center gap-4">
                  <Button onClick={() => handleFeedback(true)} className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm">
                    <ThumbsUp className="h-4 w-4 ml-2" />
                    نعم، تم الحل
                  </Button>
                  <Button onClick={() => handleFeedback(false)} variant="outline" className="border-red-300 text-red-600 hover:bg-red-50 rounded-lg">
                    <ThumbsDown className="h-4 w-4 ml-2" />
                    لا، لم يتم الحل
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <Card className="border shadow-sm rounded-xl">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="h-4 w-4 text-brand-turquoise" />
                    تفاصيل التحدي
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <InfoField label="المُبلِّغ" value={issue.employee_name} />
                    <InfoField label="نوع الحساب" value={{
                      platform_admin: 'Platform Admin',
                      school_admin: 'School Admin',
                      teacher: 'Teacher',
                      student: 'Student',
                      parent: 'Parent',
                      website_user: 'Website User',
                    }[issue.account_type] || issue.account_type} />
                    <InfoField label="القسم" value={issue.section} />
                    <InfoField label="الصفحة" value={issue.page} />
                    <InfoField label="الفريق" value={issue.assigned_team || '—'} highlight={!!issue.assigned_team} />
                    {issue.sla_remaining_hours !== undefined && (
                      <InfoField
                        label="SLA المتبقي"
                        value={`${Math.round(issue.sla_remaining_hours)} ساعة`}
                        className={issue.sla_status === 'exceeded' ? 'text-red-600 font-semibold' : 'text-emerald-600 font-semibold'}
                      />
                    )}
                    <InfoField label="تاريخ الإنشاء" value={formatDualDateTime(issue.created_at)} />
                    {issue.resolved_at && <InfoField label="تاريخ الحل" value={formatDualDateTime(issue.resolved_at)} />}
                  </div>

                  <Separator />

                  <div>
                    <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                      السلوك الحالي
                    </h4>
                    <p className="text-sm bg-red-50 p-4 rounded-xl border border-red-100 leading-relaxed">{issue.current_behavior}</p>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                      السلوك المتوقع
                    </h4>
                    <p className="text-sm bg-emerald-50 p-4 rounded-xl border border-emerald-100 leading-relaxed">{issue.expected_behavior}</p>
                  </div>

                  {issue.steps_to_reproduce && (
                    <div>
                      <h4 className="text-sm font-semibold mb-2">خطوات إعادة الإنتاج</h4>
                      <p className="text-sm bg-slate-50 p-4 rounded-xl border leading-relaxed">{issue.steps_to_reproduce}</p>
                    </div>
                  )}

                  {issue.error_message && (
                    <div>
                      <h4 className="text-sm font-semibold mb-2">رسالة الخطأ</h4>
                      <pre className="text-xs bg-slate-900 text-red-400 p-4 rounded-xl font-mono overflow-x-auto" dir="ltr">{issue.error_message}</pre>
                    </div>
                  )}

                  {issue.impact && issue.impact.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold mb-2">التأثير</h4>
                      <div className="flex flex-wrap gap-2">
                        {issue.impact.map(i => (
                          <Badge key={i} variant="secondary" className="text-[11px] bg-slate-100">{IMPACT_LABELS[i] || i}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {(issue.url || issue.device || issue.browser) && (
                    <>
                      <Separator />
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs text-muted-foreground">
                        {issue.url && (
                          <div className="flex items-center gap-1.5">
                            <Globe className="h-3 w-3" />
                            <span className="truncate">{issue.url}</span>
                          </div>
                        )}
                        {issue.device && (
                          <div className="flex items-center gap-1.5">
                            <Monitor className="h-3 w-3" />
                            <span>{issue.device}</span>
                          </div>
                        )}
                        {issue.browser && (
                          <div className="flex items-center gap-1.5">
                            <Globe className="h-3 w-3" />
                            <span>{issue.browser}</span>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {showPrompt && prompt && isAdmin && (
                <Card className="border shadow-sm rounded-xl border-brand-turquoise/30">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <ClipboardCheck className="h-4 w-4 text-brand-turquoise" />
                      Developer Prompt
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="text-xs bg-slate-900 text-emerald-400 p-5 rounded-xl overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed" dir="ltr">
                      {prompt}
                    </pre>
                    <div className="flex justify-end mt-3 gap-2">
                      <Button
                        size="sm" variant="outline"
                        onClick={async () => {
                          await navigator.clipboard.writeText(prompt);
                          toast.success('تم النسخ');
                        }}
                        className="rounded-lg text-xs"
                      >
                        <Copy className="h-3 w-3 ml-1" />
                        نسخ مرة أخرى
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card className="border shadow-sm rounded-xl">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-brand-turquoise" />
                    التعليقات ({issue.comments?.length || 0})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {issue.comments?.map(c => {
                    const typeCfg = COMMENT_TYPE_CONFIG[c.type] || COMMENT_TYPE_CONFIG.general;
                    return (
                      <div key={c.id} className={`flex gap-3 p-3 rounded-xl border ${typeCfg.borderColor} ${typeCfg.bgColor}`}>
                        <Avatar className="h-8 w-8 flex-shrink-0">
                          <AvatarFallback className="bg-brand-navy text-white text-xs">
                            {(c.user_name || '?')[0]}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 text-xs flex-wrap">
                            <span className="font-semibold text-foreground">{c.user_name}</span>
                            {c.user_role === 'platform_admin' && (
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0 h-4">مدير</Badge>
                            )}
                            {c.type && c.type !== 'general' && (
                              <Badge className={`text-[9px] px-1.5 py-0 h-4 ${typeCfg.bgColor} ${typeCfg.textColor} border ${typeCfg.borderColor}`}>
                                {typeCfg.label}
                              </Badge>
                            )}
                            <span className="text-muted-foreground">•</span>
                            <span className="text-muted-foreground">{formatDualDateTime(c.timestamp)}</span>
                          </div>
                          <p className="text-sm mt-1.5 leading-relaxed">{c.content}</p>
                        </div>
                      </div>
                    );
                  })}

                  {(!issue.comments || issue.comments.length === 0) && (
                    <EmptyState icon={MessageSquare} title="لا توجد تعليقات بعد" className="py-6" />
                  )}

                  <Separator />

                  <div className="space-y-3">
                    {isMainAdmin && (
                      <div className="flex gap-2">
                        {Object.entries(COMMENT_TYPE_CONFIG).map(([key, cfg]) => (
                          <button
                            key={key}
                            onClick={() => setCommentType(key)}
                            className={`px-3 py-1 rounded-full text-[11px] font-medium border transition-all ${
                              commentType === key
                                ? `${cfg.bgColor} ${cfg.textColor} ${cfg.borderColor}`
                                : 'border-slate-200 text-muted-foreground hover:border-slate-300'
                            }`}
                          >
                            {cfg.label}
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="أضف تعليقاً..."
                        className="text-right min-h-[60px] flex-1 rounded-lg"
                      />
                      <Button
                        onClick={handleComment}
                        disabled={!comment.trim() || submittingComment}
                        className="bg-brand-navy hover:bg-brand-navy/90 text-white self-end rounded-lg"
                      >
                        {submittingComment ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border shadow-sm rounded-xl">
                <CardHeader
                  className="pb-3 cursor-pointer"
                  onClick={() => toggleSection('timeline')}
                >
                  <CardTitle className="text-base flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-brand-turquoise" />
                      سجل النشاط ({issue.activity_log?.length || 0})
                    </span>
                    {expandedSections.timeline ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </CardTitle>
                </CardHeader>
                {expandedSections.timeline && (
                  <CardContent>
                    <div className="relative">
                      <div className="absolute top-0 bottom-0 right-[11px] w-0.5 bg-slate-200" />
                      <div className="space-y-4">
                        {issue.activity_log?.map((a, i) => {
                          const eventKey = a.event_type || a.action;
                          const eventLabel = EVENT_LABELS[eventKey] || eventKey;
                          return (
                            <div key={a.id || i} className="flex items-start gap-4 relative">
                              <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 z-10 ${
                                eventKey === 'created' || eventKey === 'issue_created' ? 'bg-emerald-100' :
                                eventKey === 'status_changed' ? 'bg-blue-100' :
                                eventKey === 'closed' || eventKey === 'issue_marked_done' ? 'bg-emerald-100' :
                                eventKey === 'reopened' || eventKey === 'issue_reopened' ? 'bg-amber-100' :
                                'bg-slate-100'
                              }`}>
                                <div className={`w-2 h-2 rounded-full ${
                                  eventKey === 'created' || eventKey === 'issue_created' ? 'bg-emerald-500' :
                                  eventKey === 'status_changed' ? 'bg-blue-500' :
                                  eventKey === 'closed' || eventKey === 'issue_marked_done' ? 'bg-emerald-500' :
                                  eventKey === 'reopened' || eventKey === 'issue_reopened' ? 'bg-amber-500' :
                                  'bg-slate-400'
                                }`} />
                              </div>
                              <div className="flex-1 min-w-0 pb-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-sm font-medium">{a.performed_by_name || a.action_by_name || 'النظام'}</span>
                                  <span className="text-xs text-muted-foreground bg-slate-50 px-2 py-0.5 rounded-full">{eventLabel}</span>
                                </div>
                                {a.details && (
                                  <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
                                    {a.details.from && a.details.to && (
                                      <div className="flex items-center gap-2">
                                        <StatusChip status={a.details.from} size="sm" />
                                        <span>→</span>
                                        <StatusChip status={a.details.to} size="sm" />
                                      </div>
                                    )}
                                    {a.details.note && <p className="text-slate-500">{a.details.note}</p>}
                                    {a.details.team && <p>الفريق: <span className="text-brand-turquoise font-medium">{a.details.team}</span></p>}
                                  </div>
                                )}
                                <span className="text-[10px] text-muted-foreground mt-1 block">
                                  {formatDualDateTime(a.timestamp)}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                        {(!issue.activity_log || issue.activity_log.length === 0) && (
                          <EmptyState icon={Activity} title="لا يوجد نشاط" className="py-6" />
                        )}
                      </div>
                    </div>
                  </CardContent>
                )}
              </Card>
            </div>

            <div className="space-y-6">
              <HakimInsightCard hakim={hakim} />

              {isMainAdmin && allowedTransitions.length > 0 && (
                <Card className="border shadow-sm rounded-xl">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold flex items-center gap-2">
                      <Shield className="h-4 w-4 text-brand-navy" />
                      إجراءات الإدارة
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <p className="text-xs text-muted-foreground mb-2 font-medium">تغيير الحالة</p>
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
                              className={`text-xs rounded-lg border-2 hover:${cfg.bgLight} hover:${cfg.textColor} hover:${cfg.borderColor}`}
                            >
                              {updatingStatus && <Loader2 className="h-3 w-3 animate-spin ml-1" />}
                              {cfg.label || s}
                            </Button>
                          );
                        })}
                      </div>
                      <Input
                        value={statusNote}
                        onChange={(e) => setStatusNote(e.target.value)}
                        placeholder="ملاحظة (اختياري)"
                        className="mt-2 text-right text-sm rounded-lg"
                      />
                    </div>

                    <Separator />

                    <div>
                      <p className="text-xs text-muted-foreground mb-2 font-medium">تعيين الفريق</p>
                      <div className="flex gap-2">
                        <Select value={assignTeam} onValueChange={setAssignTeam}>
                          <SelectTrigger className="flex-1 text-sm rounded-lg"><SelectValue placeholder="اختر الفريق" /></SelectTrigger>
                          <SelectContent>
                            {TEAMS.map(t => (
                              <SelectItem key={t} value={t}>{t}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button
                          onClick={handleAssign}
                          disabled={!assignTeam}
                          size="sm"
                          className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-lg"
                        >
                          <UserPlus className="h-4 w-4" />
                        </Button>
                      </div>
                      {issue.assigned_team && (
                        <p className="text-xs text-muted-foreground mt-2">
                          الفريق الحالي: <span className="text-brand-turquoise font-medium">{issue.assigned_team}</span>
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card className="border shadow-sm rounded-xl">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Eye className="h-4 w-4 text-brand-turquoise" />
                    معلومات سريعة
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <QuickInfoRow label="الحالة" value={<StatusChip status={issue.status} size="sm" showIcon />} />
                  <QuickInfoRow label="الأولوية" value={<PriorityBadge priority={issue.priority} size="sm" showIcon />} />
                  <QuickInfoRow label="النوع" value={typeCfg.label} />
                  <QuickInfoRow label="المُبلِّغ" value={issue.employee_name} />
                  <QuickInfoRow label="الفريق" value={issue.assigned_team || '—'} />
                  <QuickInfoRow label="التقدم" value={`${progress}%`} />
                  {issue.created_by_name && <QuickInfoRow label="أنشأه" value={issue.created_by_name} />}
                </CardContent>
              </Card>

              {issue.duplicates && issue.duplicates.length > 0 && isAdmin && (
                <Card className="border shadow-sm rounded-xl border-amber-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold flex items-center gap-2 text-amber-700">
                      <AlertTriangle className="h-4 w-4" />
                      تحديات مشابهة ({issue.duplicates.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {issue.duplicates.map((d, i) => (
                      <div key={d.id || i} className="text-xs p-2 rounded-lg bg-amber-50 border border-amber-200">
                        <span className="font-mono text-amber-600">{d.duplicate_of?.slice(0, 8) || d.issue_id?.slice(0, 8)}</span>
                        <span className="text-muted-foreground mr-2">({d.detected_by || 'hakim'})</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </div>
    </Sidebar>
  );
}

function InfoField({ label, value, className = '', highlight = false }) {
  return (
    <div>
      <p className="text-[11px] text-muted-foreground mb-0.5">{label}</p>
      <p className={`text-sm font-medium ${highlight ? 'text-brand-turquoise' : ''} ${className}`}>{value || '—'}</p>
    </div>
  );
}

function QuickInfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium">{typeof value === 'string' ? value : value}</span>
    </div>
  );
}

export default ProductHubIssuePage;
