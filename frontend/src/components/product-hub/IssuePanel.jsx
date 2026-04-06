import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';
import {
  StatusChip, PriorityBadge, SLAIndicator, EmptyState,
  HakimInsightCard, CommentInput, CommentBubble,
  STATUS_CONFIG, PRIORITY_CONFIG, TYPE_CONFIG, STATUS_PROGRESS, COMMENT_TYPE_CONFIG,
  formatDualDateCompact, getInitials, getUserColor,
} from './index';
import {
  Brain, Users, Target, Sparkles,
  AlertTriangle, CheckCircle2, Eye, Clock,
  XCircle, ExternalLink, Copy, MessageSquare, FileText, Paperclip,
  ChevronDown, Loader2, Wand2, RefreshCw,
} from 'lucide-react';

const SLA_HOURS = { critical: 24, high: 72, medium: 120, low: 240 };

export function computePredictions(issue, _nowBucket) {
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const isDone = issue.status === 'done' || issue.status === 'user_feedback_confirmed' || issue.status === 'rejected';
  if (isDone) return { risk: 'low', delay: 'on_track', escalation: 'stable' };

  const created = new Date(issue.created_at);
  if (isNaN(created.getTime())) return { risk: 'medium', delay: 'on_track', escalation: 'stable' };

  const now = new Date();
  const hoursElapsed = (now - created) / (1000 * 60 * 60);
  const daysElapsed = hoursElapsed / 24;
  const slaHours = SLA_HOURS[issue.priority] || 120;
  const slaRatio = hoursElapsed / slaHours;
  const progressRatio = progress / 100;

  let riskScore = 0;
  if (issue.priority === 'critical') riskScore += 3;
  else if (issue.priority === 'high') riskScore += 2;
  else if (issue.priority === 'medium') riskScore += 1;

  if (issue.sla_status === 'exceeded') riskScore += 3;
  else if (typeof issue.sla_remaining_hours === 'number' && issue.sla_remaining_hours <= 12) riskScore += 2;

  if (slaRatio > 0.8 && progressRatio < 0.5) riskScore += 2;
  if (slaRatio > 0.5 && progressRatio < 0.25) riskScore += 1;
  if (issue.hakim_analysis?.duplicate_ids?.length > 0) riskScore += 1;

  const risk = riskScore >= 5 ? 'high' : riskScore >= 3 ? 'medium' : 'low';

  let delay = 'on_track';
  const velocityGap = slaRatio - progressRatio;
  if (issue.sla_status === 'exceeded') delay = 'likely_delayed';
  else if (velocityGap > 0.5) delay = 'likely_delayed';
  else if (velocityGap > 0.2 && daysElapsed > 2) delay = 'at_risk';

  let escalation = 'stable';
  if (riskScore >= 5 && progressRatio < 0.3) escalation = 'escalating';
  else if (riskScore >= 3 && slaRatio > 0.7 && progressRatio < 0.5) escalation = 'escalating';
  else if (isDone || progressRatio > 0.7) escalation = 'decreasing';

  return { risk, delay, escalation, riskScore };
}

export const PREDICTION_CFG = {
  delay: {
    on_track: { label: 'في الموعد', labelEn: 'On Track', icon: '✅', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
    at_risk: { label: 'معرض للتأخير', labelEn: 'At Risk', icon: '⚠️', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200' },
    likely_delayed: { label: 'متأخر محتمل', labelEn: 'Likely Delayed', icon: '🔴', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' },
  },
  escalation: {
    stable: { label: 'مستقر', labelEn: 'Stable', icon: '➡️', color: 'text-slate-600', bg: 'bg-slate-50', border: 'border-slate-200' },
    escalating: { label: 'خطر متصاعد', labelEn: 'Escalating', icon: '📈', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' },
    decreasing: { label: 'خطر متناقص', labelEn: 'Decreasing', icon: '📉', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  },
  risk: {
    high: { label: 'خطر عالي', labelEn: 'High Risk', dot: 'bg-red-500', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200', tooltip: 'هذا التحدي يؤثر على وظائف أساسية أو يمنع المستخدمين' },
    medium: { label: 'خطر متوسط', labelEn: 'Medium Risk', dot: 'bg-amber-500', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', tooltip: 'هذا التحدي يحتاج متابعة ومعالجة في الوقت المناسب' },
    low: { label: 'خطر منخفض', labelEn: 'Low Risk', dot: 'bg-emerald-500', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', tooltip: 'هذا التحدي تحت السيطرة ولا يشكل خطراً حالياً' },
  },
};

export const HEATMAP_CFG = {
  critical: { bg: 'bg-red-50/50', hoverBg: 'hover:bg-red-50/70', borderAccent: 'border-r-red-500', glow: 'shadow-red-100/50' },
  high: { bg: 'bg-orange-50/40', hoverBg: 'hover:bg-orange-50/60', borderAccent: 'border-r-orange-400', glow: 'shadow-orange-100/50' },
  medium: { bg: 'bg-amber-50/25', hoverBg: 'hover:bg-amber-50/40', borderAccent: 'border-r-amber-400', glow: '' },
  low: { bg: 'bg-slate-50/30', hoverBg: 'hover:bg-slate-50/50', borderAccent: 'border-r-slate-300', glow: '' },
};

export const PROGRESS_STATUS_COLOR = {
  new: 'from-blue-400 to-blue-500',
  under_review: 'from-amber-400 to-amber-500',
  in_progress: 'from-violet-400 to-violet-500',
  qa_validation: 'from-cyan-400 to-cyan-500',
  done: 'from-emerald-400 to-emerald-500',
  user_feedback_confirmed: 'from-emerald-500 to-emerald-600',
  rejected: 'from-red-400 to-red-500',
};

function getProgressGradient(progress, status) {
  if (status === 'rejected') return 'from-red-300 to-red-500';
  if (progress >= 100) return 'from-emerald-400 to-emerald-600';
  if (progress >= 75) return 'from-emerald-300 to-emerald-500';
  if (progress >= 50) return 'from-brand-turquoise/80 to-brand-turquoise';
  if (progress >= 25) return 'from-amber-300 to-amber-500';
  return 'from-red-300 to-red-500';
}

function HakimMicroInsight({ label, value, detail, icon: Icon, valueColor = 'text-brand-navy' }) {
  return (
    <div className="p-3 bg-white rounded-xl border border-slate-100 hover:border-brand-turquoise/25 transition-all hover:shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-5 h-5 rounded-md bg-brand-turquoise/8 flex items-center justify-center flex-shrink-0">
          <Icon className="h-3 w-3 text-brand-turquoise" />
        </div>
        <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wide">{label}</span>
      </div>
      {value && <p className={`text-xs font-bold ${valueColor} mt-1`}>{value}</p>}
      {detail && <p className="text-[10px] text-slate-500 mt-1 leading-relaxed line-clamp-3">{detail}</p>}
    </div>
  );
}

export default function IssuePanel({ issue, navigate, isHighlighted, isMainAdmin, isAdmin, userId, onRefresh, isExpanded, onToggleExpand, isSelected, onToggleSelect }) {
  const { api } = useAuth();
  const typeCfg = TYPE_CONFIG[issue.issue_type] || TYPE_CONFIG.other;
  const TypeIcon = typeCfg.icon;
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const isDone = issue.status === 'done' || issue.status === 'user_feedback_confirmed';
  const isRejected = issue.status === 'rejected';
  const cardRef = useRef(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const [commentType, setCommentType] = useState('general');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  const commentCount = issue.comment_count || 0;
  const attachmentCount = issue.attachments?.length || 0;
  const hasDuplicates = issue.hakim_analysis?.duplicate_ids?.length > 0;
  const recentComments = issue.recent_comments || [];

  useEffect(() => {
    if (isHighlighted && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [isHighlighted]);

  useEffect(() => {
    if (isExpanded && !detailData && !detailLoading && !detailError) {
      setDetailLoading(true);
      api.get(`/product-hub/issues/${issue.id}`)
        .then(res => { setDetailData(res.data); setDetailError(false); })
        .catch(() => { toast.error('فشل في تحميل التفاصيل'); setDetailError(true); })
        .finally(() => setDetailLoading(false));
    }
  }, [isExpanded, issue.id, detailData, detailLoading, detailError]);

  const refetchDetail = useCallback(async () => {
    try {
      const res = await api.get(`/product-hub/issues/${issue.id}`);
      setDetailData(res.data);
    } catch (e) {
      console.error('[ProductHub] refetchDetail failed:', e?.message);
    }
    if (onRefresh) onRefresh();
  }, [issue.id, onRefresh]);

  const handleGenerate = async (e) => {
    if (e) e.stopPropagation();
    setGenerating(true);
    try {
      await api.post(`/product-hub/issues/${issue.id}/generate-prompt`);
      toast.success('تم إنشاء البرومبت');
      await refetchDetail();
    } catch {
      toast.error('فشل في إنشاء البرومبت');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async (e) => {
    if (e) e.stopPropagation();
    const prompt = detailData?.generated_prompt || issue.generated_prompt;
    if (prompt) {
      try {
        await navigator.clipboard.writeText(prompt);
        setCopied(true);
        toast.success('تم نسخ البرومبت');
        setTimeout(() => setCopied(false), 2000);
      } catch {
        toast.error('فشل في النسخ');
      }
    }
  };

  const handleComment = async (content, mentions = []) => {
    if (!content.trim()) return;
    setSubmittingComment(true);
    try {
      await api.post(`/product-hub/issues/${issue.id}/comments`, {
        content, comment_type: isMainAdmin ? commentType : 'general', mentions
      });
      toast.success('تم إضافة التعليق');
      setCommentType('general');
      await refetchDetail();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في إضافة التعليق'));
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleEditComment = async (commentId, content, mentions = []) => {
    try {
      await api.put(`/product-hub/issues/${issue.id}/comments/${commentId}`, { content, mentions });
      toast.success('تم تعديل التعليق');
      await refetchDetail();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في تعديل التعليق'));
    }
  };

  const handleDeleteComment = async (commentId) => {
    try {
      await api.delete(`/product-hub/issues/${issue.id}/comments/${commentId}`);
      toast.success('تم حذف التعليق');
      await refetchDetail();
    } catch {
      toast.error('فشل في حذف التعليق');
    }
  };

  const handleReanalyze = async (e) => {
    if (e) e.stopPropagation();
    setReanalyzing(true);
    try {
      const res = await api.post(`/product-hub/issues/${issue.id}/reanalyze`);
      if (res.data?.hakim_analysis) {
        setDetailData(prev => prev ? { ...prev, hakim_analysis: res.data.hakim_analysis } : prev);
      }
      toast.success('تم إعادة تحليل حكيم بنجاح');
      if (onRefresh) onRefresh();
    } catch {
      toast.error('فشل في إعادة التحليل');
    } finally {
      setReanalyzing(false);
    }
  };

  const heatmap = HEATMAP_CFG[issue.priority] || HEATMAP_CFG.medium;
  const nowBucket = useMemo(() => Math.floor(Date.now() / (5 * 60 * 1000)), []);
  const predictions = useMemo(() => computePredictions(issue, nowBucket), [issue, nowBucket]);
  const riskCfg = PREDICTION_CFG.risk[predictions.risk];
  const delayCfg = PREDICTION_CFG.delay[predictions.delay];
  const escalationCfg = PREDICTION_CFG.escalation[predictions.escalation];
  const progressColor = PROGRESS_STATUS_COLOR[issue.status] || 'from-slate-300 to-slate-500';
  const isHighRiskLowProgress = (predictions.risk === 'high' && progress < 50);

  const comments = detailData?.comments || [];
  const hakimAnalysis = detailData?.hakim_analysis || issue.hakim_analysis;
  const promptText = detailData?.generated_prompt || issue.generated_prompt;

  const statusLabel = STATUS_CONFIG[issue.status]?.label || issue.status;

  if (isMainAdmin) {
    return (
      <div
        ref={cardRef}
        className={`w-full rounded-2xl border overflow-hidden ${
          isDone ? 'bg-gradient-to-l from-emerald-50/60 to-white border-emerald-200/60'
          : isRejected ? 'bg-gradient-to-l from-red-50/40 to-white border-red-200/50'
          : 'bg-white border-slate-200 hover:border-slate-300'
        } hover:shadow-md transition-all ${isHighlighted ? 'ring-2 ring-brand-turquoise ring-offset-2' : ''}`}
        dir="rtl"
      >
        <div className="p-4 space-y-3">
          <div className="flex items-start gap-3">
            {onToggleSelect && (
              <div
                onClick={(e) => { e.stopPropagation(); onToggleSelect(issue.id); }}
                className={`w-5 h-5 rounded-md border-2 flex items-center justify-center cursor-pointer transition-all flex-shrink-0 mt-0.5 ${
                  isSelected
                    ? 'bg-brand-turquoise border-brand-turquoise text-white shadow-sm'
                    : 'border-slate-300 hover:border-brand-turquoise/50 bg-white'
                }`}
              >
                {isSelected && <CheckCircle2 className="h-3.5 w-3.5" />}
              </div>
            )}
            <h3 className={`text-sm font-bold leading-relaxed flex-1 min-w-0 ${isDone ? 'text-emerald-800' : isRejected ? 'text-red-400' : 'text-brand-navy'}`}>
              {isDone && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 inline-block ml-1 -mt-0.5" />}
              {issue.title}
            </h3>
            <span className="text-[10px] font-mono text-slate-400 bg-slate-50 px-2 py-1 rounded-md font-semibold border border-slate-100 flex-shrink-0">
              #{issue.issue_number}
            </span>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5">
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center text-[7px] font-bold text-white flex-shrink-0"
                style={{ background: isDone ? 'linear-gradient(135deg, #10b981, #059669)' : isRejected ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #1C3D74, #46C1BE)' }}
              >
                {getInitials(issue.employee_name)}
              </div>
              <span className="text-[11px] font-medium text-slate-600 truncate max-w-[140px]">{issue.employee_name}</span>
            </div>
            <div className="w-px h-4 bg-slate-200" />
            <StatusChip status={issue.status} size="default" showIcon />
            <div className="w-px h-4 bg-slate-200" />
            {hasDuplicates ? (
              <div className="flex items-center gap-1 px-2 py-0.5 bg-amber-50 rounded-md border border-amber-200">
                <Copy className="h-3 w-3 text-amber-500" />
                <span className="text-[10px] text-amber-700 font-semibold">مكرر</span>
              </div>
            ) : (
              <div className="flex items-center gap-1 px-2 py-0.5 bg-emerald-50 rounded-md border border-emerald-200">
                <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                <span className="text-[10px] text-emerald-700 font-semibold">غير مكرر</span>
              </div>
            )}
          </div>

          <div className="pt-1 border-t border-slate-100">
            <Button
              size="sm"
              onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
              className="w-full bg-brand-navy hover:bg-brand-navy/90 text-white text-xs gap-2"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              فتح الصفحة الكاملة
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={cardRef}
      className={`w-full rounded-2xl border overflow-hidden group hub-card ${
        isDone
          ? 'bg-gradient-to-l from-emerald-50/80 via-emerald-50/40 to-white border-emerald-200/60 hub-card-done'
          : isRejected
          ? 'bg-gradient-to-l from-red-50/50 via-red-50/20 to-white border-red-200/50'
          : 'bg-white border-slate-200'
      } ${isExpanded ? 'md:col-span-2 hub-card-expanded border-brand-turquoise/40 shadow-[0_8px_32px_rgba(70,193,190,0.12)] ring-1 ring-brand-turquoise/15' : `hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)] ${!isDone && !isRejected ? 'hover:border-slate-300' : ''}`} ${isHighlighted ? 'ring-2 ring-brand-turquoise ring-offset-2' : ''}`}
    >
      <div
        onClick={() => onToggleExpand(issue.id)}
        className="cursor-pointer"
      >
        <div className="px-5 pt-5 pb-2.5">
          <div className="flex items-start gap-3" dir="rtl">
            <div className="flex-1 min-w-0 text-right">
              <h3 className={`text-base font-bold leading-relaxed ${isDone ? 'text-emerald-800' : isRejected ? 'text-red-400' : 'text-brand-navy'}`}>
                {isDone && <CheckCircle2 className="h-4 w-4 text-emerald-500 inline-block ml-1.5 -mt-0.5" />}
                {issue.title}
              </h3>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 pt-0.5">
              {hasDuplicates && (
                <div className="flex items-center gap-1 px-1.5 py-0.5 bg-amber-50 rounded-md border border-amber-100">
                  <Copy className="h-2.5 w-2.5 text-amber-500" />
                  <span className="text-[9px] text-amber-600 font-semibold">مكرر</span>
                </div>
              )}
              <span className="text-[10px] font-mono text-slate-400 bg-slate-50 px-2 py-1 rounded-md font-semibold border border-slate-100">
                #{issue.issue_number}
              </span>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${isExpanded ? 'bg-brand-turquoise/10 text-brand-turquoise' : 'bg-slate-50 text-slate-400 group-hover:bg-slate-100'}`}>
                <ChevronDown className={`h-4 w-4 hub-chevron ${isExpanded ? 'hub-chevron-open' : ''}`} />
              </div>
            </div>
          </div>
        </div>

        <div className="px-5 pb-3" dir="rtl">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-[8px] font-bold text-white flex-shrink-0 shadow-sm"
                style={{ background: isDone ? 'linear-gradient(135deg, #10b981, #059669)' : isRejected ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #1C3D74, #46C1BE)' }}
              >
                {getInitials(issue.employee_name)}
              </div>
              <span className="text-[11px] font-semibold text-brand-navy truncate max-w-[130px]">{issue.employee_name}</span>
            </div>
            <div className="w-px h-4 bg-slate-200" />
            <StatusChip status={issue.status} size="default" showIcon />
            <PriorityBadge priority={issue.priority} size="sm" showIcon />
            <SLAIndicator issue={issue} size="sm" />
            {issue.assigned_team && (
              <Badge variant="outline" className="text-[9px] border-brand-turquoise/20 text-brand-turquoise px-2 py-0.5 h-5 font-medium max-md:hidden rounded-md">
                {issue.assigned_team}
              </Badge>
            )}
          </div>
        </div>

        <div className="px-5 pb-3" dir="rtl">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-500 font-medium">التقدم</span>
              <span className="text-[10px] text-slate-400">({statusLabel})</span>
            </div>
            <span className={`text-xs font-bold tabular-nums ${progress >= 75 ? 'text-emerald-600' : progress >= 50 ? 'text-brand-turquoise' : progress >= 25 ? 'text-amber-500' : 'text-red-500'}`}>
              {progress}%
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full bg-gradient-to-l ${progressColor} hub-progress-fill`}
              style={{ width: `${Math.max(progress, 2)}%` }}
            />
          </div>
        </div>


        <div className="px-5 pb-4 pt-1" dir="rtl">
          <div className="flex items-center justify-between border-t border-slate-100 pt-2.5">
            <div className="flex items-center gap-2">
              <Clock className="h-3 w-3 text-slate-300" />
              <span className="text-[10px] text-slate-400">{formatDualDateCompact(issue.created_at)}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1 text-[10px] text-slate-400">
                <MessageSquare className="h-3 w-3" />
                <span className="font-semibold">{commentCount}</span>
              </div>
              {attachmentCount > 0 && (
                <div className="flex items-center gap-1 text-[10px] text-slate-400">
                  <Paperclip className="h-3 w-3" />
                  <span className="font-semibold">{attachmentCount}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div
        className="overflow-hidden hub-expand-content"
        style={{
          maxHeight: isExpanded ? '2000px' : '0px',
          opacity: isExpanded ? 1 : 0,
        }}
      >
        <div className="border-t border-slate-100">
          {detailLoading ? (
            <div className="p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="hub-skeleton w-10 h-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <div className="hub-skeleton h-4 w-3/4 rounded-md" />
                  <div className="hub-skeleton h-3 w-1/2 rounded-md" />
                </div>
              </div>
              <div className="hub-skeleton h-20 w-full rounded-xl" />
              <div className="hub-skeleton h-16 w-full rounded-xl" />
              <div className="flex gap-2">
                <div className="hub-skeleton h-9 flex-1 rounded-lg" />
              </div>
            </div>
          ) : detailError ? (
            <div className="flex justify-center items-center py-16">
              <div className="flex flex-col items-center gap-3">
                <AlertTriangle className="h-8 w-8 text-amber-400" />
                <p className="text-sm text-muted-foreground">فشل في تحميل التفاصيل</p>
                <Button variant="outline" size="sm" onClick={() => { setDetailError(false); }} className="gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5" /> إعادة المحاولة
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
              <div className="lg:col-span-5 p-5 lg:border-l border-slate-100 hub-zone-stagger hub-zone-stagger-1">
                <div className="space-y-4">
                  <div className="flex items-center gap-3 mb-4 flex-wrap">
                    <div className="flex items-center gap-2 bg-gradient-to-l from-brand-navy/5 to-brand-turquoise/5 rounded-lg px-3 py-2 border border-brand-turquoise/15">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                        style={{ background: isDone ? 'linear-gradient(135deg, #10b981, #059669)' : isRejected ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #1C3D74, #46C1BE)' }}
                      >
                        {getInitials(issue.employee_name)}
                      </div>
                      <div className="min-w-0">
                        <span className="text-[9px] text-brand-turquoise font-semibold block leading-none">المُبلّغ</span>
                        <span className="text-xs font-bold text-brand-navy truncate block">{issue.employee_name}</span>
                      </div>
                    </div>
                    {issue.section && <span className="text-[10px] px-2 py-1 rounded-lg bg-slate-50 text-slate-600 border border-slate-100">{issue.section}</span>}
                    {issue.page && <span className="text-[10px] px-2 py-1 rounded-lg bg-slate-50 text-slate-500 border border-slate-100">{issue.page}</span>}
                    {issue.assigned_team && (
                      <Badge variant="outline" className="text-[10px] border-brand-turquoise/30 text-brand-turquoise px-2 py-0.5 font-medium">{issue.assigned_team}</Badge>
                    )}
                    {issue.platform && <span className="text-[10px] px-2 py-1 rounded-lg bg-violet-50 text-violet-600 border border-violet-100">{issue.platform}</span>}
                  </div>

                  {(issue.current_behavior || issue.expected_behavior) && (
                    <div className="grid grid-cols-1 gap-3">
                      {issue.current_behavior && (
                        <div className="p-3 rounded-xl bg-red-50/60 border border-red-100">
                          <span className="text-[10px] font-semibold text-red-500 block mb-1.5">السلوك الحالي</span>
                          <p className="text-xs text-slate-700 leading-relaxed">{issue.current_behavior}</p>
                        </div>
                      )}
                      {issue.expected_behavior && (
                        <div className="p-3 rounded-xl bg-emerald-50/60 border border-emerald-100">
                          <span className="text-[10px] font-semibold text-emerald-600 block mb-1.5">السلوك المتوقع</span>
                          <p className="text-xs text-slate-700 leading-relaxed">{issue.expected_behavior}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {issue.impact && issue.impact.length > 0 && (
                    <div className="p-3 rounded-xl bg-amber-50/50 border border-amber-100">
                      <span className="text-[10px] font-semibold text-amber-600 block mb-2 flex items-center gap-1.5">
                        <AlertTriangle className="h-3 w-3" /> التأثير
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {issue.impact.map((imp, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded-lg bg-white text-amber-700 border border-amber-200 font-medium">{imp}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {detailData?.steps_to_reproduce && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                      <span className="text-[10px] font-semibold text-slate-600 block mb-1.5">خطوات إعادة الإنتاج</span>
                      <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line">{detailData.steps_to_reproduce}</p>
                    </div>
                  )}

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] text-muted-foreground font-medium">التقدم</span>
                      <span className={`text-xs font-bold ${progress >= 75 ? 'text-emerald-600' : progress >= 50 ? 'text-brand-turquoise' : progress >= 25 ? 'text-amber-500' : 'text-red-500'}`}>{progress}%</span>
                    </div>
                    <div className="w-full bg-slate-200/60 rounded-full h-2.5 overflow-hidden">
                      <div className={`h-full rounded-full bg-gradient-to-l ${getProgressGradient(progress, issue.status)} transition-all duration-500`} style={{ width: `${progress}%` }} />
                    </div>
                  </div>

                  <div className="flex gap-2 pt-1">
                    <Button
                      onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
                      size="sm"
                      className="flex-1 h-9 text-xs font-semibold rounded-lg gap-1.5 bg-brand-navy hover:bg-brand-navy/90 text-white hub-btn"
                    >
                      <ExternalLink className="h-3.5 w-3.5" /> فتح الصفحة الكاملة
                    </Button>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-4 p-5 lg:border-l border-slate-100 border-t lg:border-t-0 flex flex-col hub-zone-stagger hub-zone-stagger-2">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="h-4 w-4 text-brand-navy" />
                  <span className="text-sm font-semibold text-brand-navy">المناقشة</span>
                  <span className="text-[10px] text-muted-foreground">({comments.length})</span>
                </div>

                <div className="flex-1 overflow-y-auto max-h-[400px] space-y-3 mb-3 scrollbar-thin">
                  {comments.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center hub-empty-state">
                      <MessageSquare className="h-8 w-8 text-slate-200 mb-2" />
                      <p className="text-xs text-muted-foreground">لا توجد تعليقات بعد</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">كن أول من يعلّق</p>
                    </div>
                  ) : (
                    comments.map((comment, idx) => {
                      const uColor = getUserColor(comment.created_by || comment.user_id);
                      return (
                        <div key={comment.id} className="hub-comment-enter flex gap-2.5" style={{ animationDelay: `${Math.min(idx * 40, 200)}ms` }}>
                          <div
                            className="w-7 h-7 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0 mt-0.5 shadow-sm"
                            style={{ backgroundColor: uColor.avatar }}
                          >
                            {getInitials(comment.user_name)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span className={`text-[11px] font-semibold ${uColor.text}`}>{comment.user_name}</span>
                              <span className="text-[9px] text-slate-400">{formatDualDateCompact(comment.timestamp)}</span>
                            </div>
                            <CommentBubble
                              comment={comment}
                              currentUserId={userId}
                              isMainAdmin={isMainAdmin}
                              isAdmin={isAdmin}
                              onEdit={handleEditComment}
                              onDelete={handleDeleteComment}
                            />
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="border-t border-slate-100 pt-3">
                  <CommentInput
                    onSubmit={handleComment}
                    submitting={submittingComment}
                    isMainAdmin={isMainAdmin}
                    isAdmin={isAdmin}
                    commentType={commentType}
                    setCommentType={setCommentType}
                    COMMENT_TYPE_CONFIG={COMMENT_TYPE_CONFIG}
                  />
                </div>
              </div>

              {isMainAdmin ? <div className="lg:col-span-3 p-5 border-t lg:border-t-0 bg-gradient-to-b from-brand-turquoise/[0.04] via-transparent to-brand-navy/[0.02] hub-zone-stagger hub-zone-stagger-3 hub-hakim-enter">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-turquoise to-brand-navy flex items-center justify-center shadow-md shadow-brand-turquoise/20">
                    <Brain className="h-4.5 w-4.5 text-white" />
                  </div>
                  <div className="flex-1">
                    <span className="text-sm font-bold text-brand-navy block leading-tight">حكيم</span>
                    <span className="text-[10px] text-brand-turquoise font-medium">مساعد ذكي للتحليل</span>
                  </div>
                </div>

                {isMainAdmin && (
                  <Button
                    onClick={handleReanalyze}
                    disabled={reanalyzing}
                    className={`w-full h-10 text-xs font-bold rounded-xl gap-2 mb-4 shadow-sm hub-btn ${
                      hakimAnalysis && Object.keys(hakimAnalysis).length > 0
                        ? 'bg-white border-2 border-brand-turquoise/30 text-brand-turquoise hover:bg-brand-turquoise/5 hover:border-brand-turquoise/50 hover:shadow-md'
                        : 'bg-gradient-to-l from-brand-turquoise to-brand-turquoise/90 text-white hover:from-brand-turquoise/90 hover:to-brand-turquoise/80 shadow-brand-turquoise/25'
                    }`}
                    variant={hakimAnalysis && Object.keys(hakimAnalysis).length > 0 ? 'outline' : 'default'}
                  >
                    {reanalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
                    <span className={reanalyzing ? 'hub-analyzing' : ''}>{reanalyzing ? 'حكيم يحلّل...' : hakimAnalysis && Object.keys(hakimAnalysis).length > 0 ? 'إعادة التحليل بحكيم' : 'تحليل بواسطة حكيم'}</span>
                  </Button>
                )}

                {hakimAnalysis && Object.keys(hakimAnalysis).length > 0 ? (
                  <div className="space-y-2.5">
                    {hakimAnalysis.suggested_priority && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight
                          label="الأولوية المقترحة"
                          value={PRIORITY_CONFIG[hakimAnalysis.suggested_priority]?.label || hakimAnalysis.suggested_priority}
                          detail={hakimAnalysis.priority_reasoning}
                          icon={Target}
                          valueColor={PRIORITY_CONFIG[hakimAnalysis.suggested_priority]?.textColor}
                        />
                      </div>
                    )}
                    {hakimAnalysis.suggested_team && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight
                          label="الفريق المقترح"
                          value={hakimAnalysis.suggested_team}
                          detail={hakimAnalysis.team_reasoning}
                          icon={Users}
                          valueColor="text-brand-turquoise"
                        />
                      </div>
                    )}
                    {hakimAnalysis.impact_assessment && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight label="تقييم الأثر" detail={hakimAnalysis.impact_assessment} icon={AlertTriangle} />
                      </div>
                    )}
                    {hakimAnalysis.technical_notes && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight label="ملاحظات فنية" detail={hakimAnalysis.technical_notes} icon={FileText} />
                      </div>
                    )}
                    {hakimAnalysis.duplicate_ids?.length > 0 && (
                      <div className="hub-insight-item p-2.5 bg-amber-50/80 rounded-xl border border-amber-200/80">
                        <div className="flex items-center gap-1.5 text-amber-700 text-[10px] font-semibold mb-1">
                          <Copy className="h-3 w-3" />
                          {hakimAnalysis.duplicate_ids.length} تحدي مشابه
                        </div>
                        {hakimAnalysis.duplicate_note && (
                          <p className="text-[10px] text-amber-600 leading-relaxed">{hakimAnalysis.duplicate_note}</p>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-5 px-3 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 hub-empty-state">
                    <Sparkles className="h-8 w-8 text-slate-200 mx-auto mb-2" />
                    <p className="text-xs text-slate-400 font-medium">لم يتم التحليل بعد</p>
                    <p className="text-[10px] text-slate-300 mt-0.5">اضغط الزر أعلاه لبدء تحليل حكيم</p>
                  </div>
                )}

                {isMainAdmin && (
                  <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
                    <div className="text-[10px] text-slate-400 font-semibold mb-2 flex items-center gap-1.5">
                      <Wand2 className="h-3 w-3 text-brand-purple/70" /> أدوات إضافية
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <Button
                        variant="outline" size="sm"
                        onClick={handleGenerate}
                        disabled={generating}
                        className="h-8 text-[9px] font-semibold rounded-lg gap-1 border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-brand-purple hover:border-brand-purple/20 hub-btn"
                      >
                        {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                        {promptText ? 'إعادة البرومبت' : 'إنشاء برومبت'}
                      </Button>
                      <Button
                        variant={copied ? "default" : "outline"} size="sm"
                        onClick={handleCopy}
                        disabled={!promptText}
                        className={`h-8 text-[9px] font-semibold rounded-lg gap-1 hub-btn ${copied ? 'bg-emerald-500 text-white hub-success-pulse' : 'border-slate-200 text-slate-600 hover:bg-slate-50'} ${!promptText ? 'opacity-30' : ''}`}
                      >
                        {copied ? <CheckCircle2 className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                        {copied ? 'تم النسخ' : 'نسخ البرومبت'}
                      </Button>
                    </div>

                    {promptText && (
                      <div className="mt-2 p-2.5 bg-slate-900 rounded-xl max-h-[150px] overflow-y-auto scrollbar-thin">
                        <pre className="text-[9px] text-emerald-300 whitespace-pre-wrap leading-relaxed font-mono" dir="ltr">{promptText.slice(0, 600)}{promptText.length > 600 ? '...' : ''}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div> : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
