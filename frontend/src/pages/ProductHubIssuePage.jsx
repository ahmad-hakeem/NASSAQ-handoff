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
  CommentInput, CommentBubble,
  STATUS_CONFIG, TYPE_CONFIG, STATUS_PROGRESS,
  FINAL_STATUSES, TEAMS, EVENT_LABELS, COMMENT_TYPE_CONFIG, IMPACT_LABELS,
  formatDualDate, formatDualDateTime, formatDualDateCompact, getInitials, getUserColor,
} from '../components/product-hub';
import {
  ArrowRight, Brain, Copy, Send, Shield, MessageSquare, Activity,
  FileText, Loader2, ThumbsUp, ThumbsDown, UserPlus, ChevronDown, ChevronUp,
  Monitor, Globe, Eye, AlertTriangle, CheckCircle2, Clock, Users, Tag,
  Zap, Calendar, BarChart3, RefreshCw,
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
  const [commentType, setCommentType] = useState('general');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [statusNote, setStatusNote] = useState('');
  const [assignTeam, setAssignTeam] = useState('');
  const [expandedSections, setExpandedSections] = useState({ timeline: false });
  const [generatingPrompt, setGeneratingPrompt] = useState(false);
  const [promptCopied, setPromptCopied] = useState(false);

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

  const handleComment = async (content, mentions = []) => {
    if (!content.trim()) return;
    setSubmittingComment(true);
    try {
      await axios.post(`/api/product-hub/issues/${issueId}/comments`, {
        content, comment_type: isMainAdmin ? commentType : 'general', mentions
      }, { headers: authHeaders() });
      toast.success('تم إضافة التعليق');
      setCommentType('general');
      fetchIssue();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message : (detail || 'فشل في إضافة التعليق');
      toast.error(msg);
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleEditComment = async (commentId, content, mentions = []) => {
    try {
      await axios.put(`/api/product-hub/issues/${issueId}/comments/${commentId}`, { content, mentions }, { headers: authHeaders() });
      toast.success('تم تعديل التعليق');
      fetchIssue();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message : (detail || 'فشل في تعديل التعليق');
      toast.error(msg);
    }
  };

  const handleDeleteComment = async (commentId) => {
    try {
      await axios.delete(`/api/product-hub/issues/${issueId}/comments/${commentId}`, { headers: authHeaders() });
      toast.success('تم حذف التعليق');
      fetchIssue();
    } catch {
      toast.error('فشل في حذف التعليق');
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

  const handleGeneratePrompt = async () => {
    setGeneratingPrompt(true);
    try {
      await axios.post(`/api/product-hub/issues/${issueId}/generate-prompt`, {}, { headers: authHeaders() });
      toast.success('تم إنشاء البرومبت');
      fetchIssue();
    } catch (err) {
      toast.error('فشل في إنشاء البرومبت');
    } finally {
      setGeneratingPrompt(false);
    }
  };

  const handleCopyPrompt = () => {
    if (issue?.generated_prompt) {
      navigator.clipboard.writeText(issue.generated_prompt);
      setPromptCopied(true);
      toast.success('تم نسخ البرومبت');
      setTimeout(() => setPromptCopied(false), 2000);
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
  const statusCfg = STATUS_CONFIG[issue.status] || {};

  const progressColor = progress === 100 ? 'text-emerald-600' :
    progress >= 75 ? 'text-blue-600' :
    progress >= 50 ? 'text-brand-turquoise' :
    progress >= 25 ? 'text-amber-600' : 'text-slate-500';

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/20" dir="rtl">
        <div className="p-4 lg:p-8 max-w-[1400px] mx-auto space-y-6">

          {/* ═══════ 1. HERO TITLE ═══════ */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-l from-brand-navy via-brand-navy/95 to-brand-navy/90 p-6 lg:p-8 shadow-lg">
            <div className="absolute inset-0 opacity-[0.04]" style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            }} />
            <div className="relative flex flex-col lg:flex-row lg:items-start justify-between gap-4">
              <div className="flex items-start gap-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/admin/product-hub')}
                  className="rounded-lg mt-1 text-white/70 hover:text-white hover:bg-white/10 border border-white/20"
                >
                  <ArrowRight className="h-4 w-4 ml-1" />
                  رجوع
                </Button>
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <span className="text-xs font-mono bg-white/15 text-white/80 px-2.5 py-1 rounded-md">#{issue.issue_number}</span>
                    <Badge className={`text-[11px] ${typeCfg.color} bg-white/15 border-white/20`}>
                      <TypeIcon className="h-3 w-3 ml-1" />
                      {typeCfg.label}
                    </Badge>
                  </div>
                  <h1 className="text-2xl lg:text-3xl font-bold text-white leading-tight tracking-tight">
                    {issue.title}
                  </h1>
                  <div className="flex items-center gap-3 mt-3 flex-wrap">
                    <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-1.5 border border-white/15">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-brand-navy bg-white flex-shrink-0">
                        {getInitials(issue.employee_name)}
                      </div>
                      <div>
                        <span className="text-[9px] text-brand-turquoise font-semibold block leading-none">المُبلّغ</span>
                        <span className="text-sm font-bold text-white">{issue.employee_name}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-white/60">
                      <span>{issue.section} › {issue.page}</span>
                      <span className="text-white/30">•</span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDualDateCompact(issue.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ═══════ 2. QUICK INFO CARDS (Horizontal) ═══════ */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            <QuickInfoCard
              icon={<BarChart3 className="h-4 w-4" />}
              label="الحالة"
              value={<StatusChip status={issue.status} size="sm" showIcon />}
              accent="bg-blue-50 border-blue-200"
            />
            <QuickInfoCard
              icon={<Zap className="h-4 w-4" />}
              label="الأولوية"
              value={<PriorityBadge priority={issue.priority} size="sm" showIcon />}
              accent="bg-amber-50 border-amber-200"
            />
            <QuickInfoCard
              icon={<Tag className="h-4 w-4" />}
              label="النوع"
              value={<span className="text-xs font-medium">{typeCfg.label}</span>}
              accent="bg-purple-50 border-purple-200"
            />
            <QuickInfoCard
              icon={<Users className="h-4 w-4" />}
              label="الفريق المسؤول"
              value={<span className={`text-xs font-medium ${issue.assigned_team ? 'text-brand-turquoise' : 'text-muted-foreground'}`}>{issue.assigned_team || '—'}</span>}
              accent="bg-teal-50 border-teal-200"
            />
            <QuickInfoCard
              icon={<Clock className="h-4 w-4" />}
              label="SLA"
              value={<SLAIndicator issue={issue} size="sm" />}
              accent={issue.sla_status === 'exceeded' ? 'bg-red-50 border-red-200' : 'bg-emerald-50 border-emerald-200'}
            />
          </div>

          {/* ═══════ 3. PROGRESS HERO ═══════ */}
          <Card className="border shadow-sm rounded-2xl overflow-hidden">
            <div className="p-5 lg:p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    progress === 100 ? 'bg-emerald-100' :
                    progress >= 50 ? 'bg-blue-100' : 'bg-slate-100'
                  }`}>
                    <BarChart3 className={`h-5 w-5 ${progressColor}`} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-brand-navy">التقدم المحرز</h3>
                    <p className="text-xs text-muted-foreground">
                      {statusCfg.label || issue.status}
                      {issue.sla_remaining_hours !== undefined && (
                        <span className={`mr-2 ${issue.sla_status === 'exceeded' ? 'text-red-500' : 'text-emerald-500'}`}>
                          • SLA: {Math.round(issue.sla_remaining_hours)} ساعة
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <span className={`text-3xl font-black ${progressColor}`}>{progress}%</span>
              </div>
              <div className="relative">
                <div className="w-full h-4 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ease-out ${
                      progress === 100 ? 'bg-gradient-to-l from-emerald-500 to-emerald-400' :
                      progress >= 75 ? 'bg-gradient-to-l from-blue-500 to-blue-400' :
                      progress >= 50 ? 'bg-gradient-to-l from-brand-turquoise to-brand-turquoise/80' :
                      progress >= 25 ? 'bg-gradient-to-l from-amber-500 to-amber-400' :
                      'bg-gradient-to-l from-slate-400 to-slate-300'
                    }`}
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="flex justify-between mt-2">
                  {['جديد', 'مراجعة', 'قيد العمل', 'اختبار', 'منجز'].map((label, i) => {
                    const stepProgress = i * 25;
                    return (
                      <span key={label} className={`text-[10px] ${progress >= stepProgress ? 'text-brand-navy font-medium' : 'text-muted-foreground'}`}>
                        {label}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>
          </Card>

          {/* ═══════ 4. ADMIN ACTION BAR (Main Admins Only) ═══════ */}
          {isMainAdmin && (
            <Card className="border-2 border-brand-navy/10 shadow-sm rounded-2xl bg-gradient-to-l from-brand-navy/[0.02] to-transparent">
              <CardContent className="p-4 lg:p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Shield className="h-4 w-4 text-brand-navy" />
                  <span className="text-sm font-bold text-brand-navy">لوحة التحكم</span>
                </div>

                <div className="flex flex-col lg:flex-row gap-4 items-start">
                  {/* Status Action Buttons */}
                  <div className="flex-1">
                    <p className="text-[11px] text-muted-foreground mb-3 font-medium">تغيير الحالة</p>
                    <div className="flex flex-wrap gap-3">
                      {issue.status !== 'in_progress' && (
                        <Button
                          onClick={() => handleStatusChange('in_progress')}
                          disabled={updatingStatus}
                          className="h-12 px-6 text-sm font-bold rounded-xl gap-2 bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-200 transition-all"
                        >
                          {updatingStatus ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                          قيد التنفيذ
                        </Button>
                      )}
                      {issue.status === 'in_progress' && (
                        <div className="flex items-center gap-2 h-12 px-5 rounded-xl bg-blue-50 border-2 border-blue-200 text-blue-700 font-bold text-sm">
                          <CheckCircle2 className="h-4 w-4" />
                          قيد التنفيذ حالياً
                        </div>
                      )}

                      {issue.status !== 'done' && issue.status !== 'user_feedback_confirmed' && (
                        <Button
                          onClick={() => handleStatusChange('done')}
                          disabled={updatingStatus}
                          className="h-12 px-6 text-sm font-bold rounded-xl gap-2 bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-200 transition-all"
                        >
                          {updatingStatus ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                          مكتمل
                        </Button>
                      )}
                      {(issue.status === 'done' || issue.status === 'user_feedback_confirmed') && (
                        <div className="flex items-center gap-2 h-12 px-5 rounded-xl bg-emerald-50 border-2 border-emerald-200 text-emerald-700 font-bold text-sm">
                          <CheckCircle2 className="h-4 w-4" />
                          مكتمل
                        </div>
                      )}
                    </div>
                    <Input
                      value={statusNote}
                      onChange={(e) => setStatusNote(e.target.value)}
                      placeholder="ملاحظة (اختياري)"
                      className="mt-3 text-right text-xs rounded-lg h-8 max-w-xs"
                    />
                  </div>

                </div>
              </CardContent>
            </Card>
          )}

          {/* ═══════ FEEDBACK BANNER ═══════ */}
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

          {/* ═══════ MAIN CONTENT GRID ═══════ */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">

              {/* ═══════ 5. CHALLENGE DETAILS ═══════ */}
              <Card className="border shadow-sm rounded-xl">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="h-4 w-4 text-brand-turquoise" />
                    تفاصيل التحدي
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="flex items-center gap-3 p-3 bg-gradient-to-l from-brand-navy/5 to-brand-turquoise/5 rounded-xl border border-brand-turquoise/15 mb-1">
                    <div className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                      style={{ background: 'linear-gradient(135deg, #1C3D74, #46C1BE)' }}>
                      {getInitials(issue.employee_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-[10px] text-brand-turquoise font-semibold block leading-none mb-0.5">المُبلّغ</span>
                      <p className="text-sm font-bold text-brand-navy truncate">{issue.employee_name}</p>
                    </div>
                    {issue.section && (
                      <span className="text-[10px] px-2 py-1 rounded-lg bg-white text-slate-500 border border-slate-100">{issue.section}</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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

              {/* ═══════ 6. AI GENERATED PROMPT (Main Admins Only) ═══════ */}
              {isMainAdmin && (
                <Card className="border-2 border-brand-purple/20 shadow-md rounded-2xl overflow-hidden">
                  <div className="bg-gradient-to-l from-brand-purple/10 via-brand-purple/5 to-transparent px-5 py-4 flex items-center justify-between border-b border-brand-purple/10">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-xl bg-brand-purple/10">
                        <Brain className="h-5 w-5 text-brand-purple" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-brand-purple" dir="ltr">AI Generated Prompt by Hakim</h3>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {issue.generated_prompt ? (
                            <span className="text-emerald-600 font-medium flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Generated
                            </span>
                          ) : (
                            <span className="text-amber-600 font-medium flex items-center gap-1">
                              <AlertTriangle className="h-3 w-3" />
                              Not Generated
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleGeneratePrompt}
                        disabled={generatingPrompt}
                        className="text-xs rounded-lg h-8 gap-1.5 border-brand-purple/30 text-brand-purple hover:bg-brand-purple/10"
                      >
                        {generatingPrompt ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                        {issue.generated_prompt ? 'Regenerate Prompt' : 'Generate Prompt'}
                      </Button>
                      {issue.generated_prompt && (
                        <Button
                          variant={promptCopied ? "default" : "outline"}
                          size="sm"
                          onClick={handleCopyPrompt}
                          className={`text-xs rounded-lg h-8 gap-1.5 ${promptCopied ? 'bg-emerald-500 hover:bg-emerald-600 text-white border-emerald-500' : 'border-brand-purple/30 text-brand-purple hover:bg-brand-purple/10'}`}
                        >
                          {promptCopied ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                          {promptCopied ? 'Copied!' : 'Copy Prompt'}
                        </Button>
                      )}
                    </div>
                  </div>

                  {issue.generated_prompt ? (
                    <CardContent className="p-0">
                      <pre
                        className="text-[13px] bg-slate-950 text-slate-200 p-6 font-mono leading-[1.8] whitespace-pre-wrap overflow-x-auto max-h-[600px] overflow-y-auto scrollbar-thin"
                        dir="ltr"
                        style={{ tabSize: 4 }}
                      >{issue.generated_prompt}</pre>
                      <div className="px-5 py-3 bg-slate-50 border-t flex items-center justify-between">
                        <p className="text-[11px] text-muted-foreground">
                          Ready to use in Vibe Coding Platform
                        </p>
                        <Button
                          variant={promptCopied ? "default" : "outline"}
                          size="sm"
                          onClick={handleCopyPrompt}
                          className={`text-xs rounded-lg h-8 gap-1.5 ${promptCopied ? 'bg-emerald-500 hover:bg-emerald-600 text-white border-emerald-500' : 'border-brand-purple/30 text-brand-purple hover:bg-brand-purple/10'}`}
                        >
                          {promptCopied ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                          {promptCopied ? 'Copied!' : 'Copy Prompt'}
                        </Button>
                      </div>
                    </CardContent>
                  ) : (
                    <CardContent className="p-8 text-center">
                      <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-brand-purple/5 mb-4">
                        <Brain className="h-8 w-8 text-brand-purple/40" />
                      </div>
                      <p className="text-sm text-muted-foreground mb-1">لم يتم إنشاء البرومبت بعد</p>
                      <p className="text-xs text-muted-foreground/70 mb-4">اضغط على "Generate Prompt" لإنشاء برومبت تنفيذي بواسطة Hakim AI</p>
                      <Button
                        onClick={handleGeneratePrompt}
                        disabled={generatingPrompt}
                        className="bg-brand-purple hover:bg-brand-purple/90 text-white rounded-lg gap-2"
                      >
                        {generatingPrompt ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
                        Generate Prompt
                      </Button>
                    </CardContent>
                  )}
                </Card>
              )}

              {/* ═══════ COMMENTS ═══════ */}
              {issue.permissions?.can_comment && (
                <Card className="border shadow-sm rounded-xl">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 text-brand-turquoise" />
                      التعليقات ({issue.comments?.length || 0})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {issue.comments?.map(c => {
                      const cTypeCfg = COMMENT_TYPE_CONFIG[c.type] || COMMENT_TYPE_CONFIG.general;
                      const uColor = getUserColor(c.created_by || c.user_id);
                      return (
                        <div key={c.id} className={`flex gap-3 p-3 rounded-xl border ${cTypeCfg.borderColor} ${cTypeCfg.bgColor}`}>
                          <div
                            className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 shadow-sm"
                            style={{ backgroundColor: uColor.avatar }}
                          >
                            {getInitials(c.user_name)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 text-xs flex-wrap">
                              <span className={`font-semibold ${uColor.text}`}>{c.user_name}</span>
                              {c.user_role === 'platform_admin' && (
                                <Badge variant="outline" className="text-[9px] px-1.5 py-0 h-4">مدير</Badge>
                              )}
                              {c.type && c.type !== 'general' && (
                                <Badge className={`text-[9px] px-1.5 py-0 h-4 ${cTypeCfg.bgColor} ${cTypeCfg.textColor} border ${cTypeCfg.borderColor}`}>
                                  {cTypeCfg.label}
                                </Badge>
                              )}
                              <span className="text-muted-foreground">•</span>
                              <span className="text-muted-foreground">{formatDualDateTime(c.timestamp)}</span>
                            </div>
                            <CommentBubble
                              comment={c}
                              currentUserId={user?.id}
                              isMainAdmin={isMainAdmin}
                              isAdmin={isAdmin}
                              onEdit={handleEditComment}
                              onDelete={handleDeleteComment}
                            />
                          </div>
                        </div>
                      );
                    })}

                    {(!issue.comments || issue.comments.length === 0) && (
                      <EmptyState icon={MessageSquare} title="لا توجد تعليقات بعد" description="اكتب تعليقك الأول أو استخدم @ للإشارة إلى شخص" className="py-6" />
                    )}

                    <Separator />

                    <CommentInput
                      onSubmit={handleComment}
                      submitting={submittingComment}
                      isMainAdmin={isMainAdmin}
                      isAdmin={isAdmin}
                      commentType={commentType}
                      setCommentType={setCommentType}
                      COMMENT_TYPE_CONFIG={COMMENT_TYPE_CONFIG}
                    />
                  </CardContent>
                </Card>
              )}

            </div>

            {/* ═══════ RIGHT SIDEBAR ═══════ */}
            <div className="space-y-6">

              {/* ═══════ ACTIVITY LOG ═══════ */}
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
                            <div key={a.id || i} className="flex items-start gap-3 relative">
                              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 z-10 ${
                                eventKey === 'created' || eventKey === 'issue_created' ? 'bg-emerald-100' :
                                eventKey === 'status_changed' ? 'bg-blue-100' :
                                eventKey === 'closed' || eventKey === 'issue_marked_done' ? 'bg-emerald-100' :
                                eventKey === 'reopened' || eventKey === 'issue_reopened' ? 'bg-amber-100' :
                                'bg-slate-100'
                              }`}>
                                <div className={`w-1.5 h-1.5 rounded-full ${
                                  eventKey === 'created' || eventKey === 'issue_created' ? 'bg-emerald-500' :
                                  eventKey === 'status_changed' ? 'bg-blue-500' :
                                  eventKey === 'closed' || eventKey === 'issue_marked_done' ? 'bg-emerald-500' :
                                  eventKey === 'reopened' || eventKey === 'issue_reopened' ? 'bg-amber-500' :
                                  'bg-slate-400'
                                }`} />
                              </div>
                              <div className="flex-1 min-w-0 pb-2">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="text-xs font-medium">{a.performed_by_name || a.action_by_name || 'النظام'}</span>
                                  <span className="text-[10px] text-muted-foreground bg-slate-50 px-1.5 py-0.5 rounded-full">{eventLabel}</span>
                                </div>
                                {a.details && (
                                  <div className="text-[11px] text-muted-foreground mt-1 space-y-0.5">
                                    {a.details.from && a.details.to && (
                                      <div className="flex items-center gap-1.5">
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
              {issue.duplicates && issue.duplicates.length > 0 && isMainAdmin && (
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

          {/* ═══════ 6. HAKIM ANALYSIS (Bottom of Page — Main Admins Only) ═══════ */}
          {isMainAdmin && hakim && Object.keys(hakim).length > 0 && (
            <div className="relative">
              <div className="absolute -top-3 right-6 bg-brand-purple text-white text-[11px] font-medium px-3 py-1 rounded-full shadow-sm z-10 flex items-center gap-1.5">
                <Brain className="h-3 w-3" />
                تحليل Hakim AI
              </div>
              <Card className="border-2 border-brand-purple/20 shadow-md rounded-2xl bg-gradient-to-l from-brand-purple/[0.02] to-transparent pt-4">
                <CardContent className="p-5 lg:p-6">
                  <HakimInsightCard hakim={hakim} />
                </CardContent>
              </Card>
            </div>
          )}

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

function QuickInfoCard({ icon, label, value, accent = 'bg-slate-50 border-slate-200' }) {
  return (
    <div className={`rounded-xl border p-3 ${accent} flex flex-col gap-2`}>
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <span className="text-[11px] font-medium">{label}</span>
      </div>
      <div>{value}</div>
    </div>
  );
}

export default ProductHubIssuePage;
