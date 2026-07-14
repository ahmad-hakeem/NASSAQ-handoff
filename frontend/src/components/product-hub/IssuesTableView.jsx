import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { LoadingState } from '../ui/LoadingState';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';
import {
  STATUS_CONFIG, PRIORITY_CONFIG, EmptyState,
} from './index';
import IssuePanel from './IssuePanel';
import { getApiErrorMessage } from '../../utils/apiError';
import {
  CheckCircle2, Bug, ChevronLeft, ChevronRight,
  Minimize2, Loader2, Trash2, Pencil, Hash, XCircle,
} from 'lucide-react';

const TEAMS_LIST = ["Frontend", "Backend", "DevOps", "Design", "QA", "Product"];

function BulkActionBar({ selectedIds, onClearSelection, onBulkEdit, onBulkDelete }) {
  const count = selectedIds.length;
  if (count === 0) return null;

  return (
    <div className="sticky top-0 z-30 bg-brand-navy/95 backdrop-blur-sm text-white rounded-xl px-4 py-3 flex items-center justify-between gap-3 shadow-lg border border-brand-navy/50" dir="rtl">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-white/15 flex items-center justify-center">
            <CheckCircle2 className="h-4 w-4" />
          </div>
          <span className="text-sm font-bold">{count} تحدي محدد</span>
        </div>
        <Button
          variant="ghost" size="sm"
          onClick={onClearSelection}
          className="text-white/70 hover:text-white hover:bg-white/10 text-xs h-7 gap-1"
        >
          <XCircle className="h-3.5 w-3.5" /> إلغاء التحديد
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={onBulkEdit}
          className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white text-xs h-8 gap-1.5 rounded-lg"
        >
          <Pencil className="h-3.5 w-3.5" /> تعديل جماعي
        </Button>
        <Button
          size="sm"
          onClick={onBulkDelete}
          className="bg-red-500 hover:bg-red-600 text-white text-xs h-8 gap-1.5 rounded-lg"
        >
          <Trash2 className="h-3.5 w-3.5" /> حذف
        </Button>
      </div>
    </div>
  );
}

function BulkEditModal({ open, onClose, selectedCount, onSubmit }) {
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [team, setTeam] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const hasChanges = status || priority || team;

  const handleSubmit = async () => {
    if (!hasChanges) return;
    setSubmitting(true);
    try {
      await onSubmit({ status: status || undefined, priority: priority || undefined, assigned_team: team || undefined });
      setStatus(''); setPriority(''); setTeam('');
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden" onClick={e => e.stopPropagation()} dir="rtl">
        <div className="px-5 py-4 border-b border-slate-100 bg-gradient-to-l from-brand-turquoise/5 to-transparent">
          <h3 className="text-base font-bold text-brand-navy flex items-center gap-2">
            <Pencil className="h-4 w-4 text-brand-turquoise" />
            تعديل جماعي — {selectedCount} تحدي
          </h3>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">الحالة</label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="h-9 rounded-lg text-xs"><SelectValue placeholder="بدون تغيير" /></SelectTrigger>
              <SelectContent>
                {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                  <SelectItem key={key} value={key} className="text-xs">{cfg.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">الأولوية</label>
            <Select value={priority} onValueChange={setPriority}>
              <SelectTrigger className="h-9 rounded-lg text-xs"><SelectValue placeholder="بدون تغيير" /></SelectTrigger>
              <SelectContent>
                {Object.entries(PRIORITY_CONFIG).map(([key, cfg]) => (
                  <SelectItem key={key} value={key} className="text-xs">{cfg.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600 mb-1.5 block">الفريق</label>
            <Select value={team} onValueChange={setTeam}>
              <SelectTrigger className="h-9 rounded-lg text-xs"><SelectValue placeholder="بدون تغيير" /></SelectTrigger>
              <SelectContent>
                {TEAMS_LIST.map(t => (
                  <SelectItem key={t} value={t} className="text-xs">{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-end gap-2 bg-slate-50/50">
          <Button variant="ghost" size="sm" onClick={onClose} className="text-xs h-8 rounded-lg">إلغاء</Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!hasChanges || submitting}
            className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white text-xs h-8 gap-1.5 rounded-lg"
          >
            {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            تطبيق التعديلات
          </Button>
        </div>
      </div>
    </div>
  );
}

function BulkDeleteModal({ open, onClose, selectedCount, onConfirm }) {
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden" onClick={e => e.stopPropagation()} dir="rtl">
        <div className="px-5 py-4 border-b border-red-100 bg-gradient-to-l from-red-50 to-transparent">
          <h3 className="text-base font-bold text-red-700 flex items-center gap-2">
            <Trash2 className="h-4 w-4 text-red-500" />
            تأكيد الحذف
          </h3>
        </div>
        <div className="p-5">
          <p className="text-sm text-slate-700 leading-relaxed">
            هل أنت متأكد من حذف <span className="font-bold text-red-600">{selectedCount}</span> تحدي؟
          </p>
          <p className="text-xs text-slate-400 mt-2">لا يمكن التراجع عن هذا الإجراء.</p>
        </div>
        <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-end gap-2 bg-slate-50/50">
          <Button variant="ghost" size="sm" onClick={onClose} className="text-xs h-8 rounded-lg">إلغاء</Button>
          <Button
            size="sm"
            onClick={handleConfirm}
            disabled={submitting}
            className="bg-red-500 hover:bg-red-600 text-white text-xs h-8 gap-1.5 rounded-lg"
          >
            {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            نعم، احذف {selectedCount} تحدي
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function IssuesTableView({ issues, loading, total, page, totalPages, onPageChange, navigate, highlightId, isMainAdmin, onRefresh }) {
  const { user, api } = useAuth();
  const isAdmin = user?.role === 'platform_admin';
  const [expandedId, setExpandedId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [showBulkEdit, setShowBulkEdit] = useState(false);
  const [showBulkDelete, setShowBulkDelete] = useState(false);

  const handleToggleExpand = useCallback((issueId) => {
    setExpandedId(prev => prev === issueId ? null : issueId);
  }, []);

  const toggleSelect = useCallback((issueId) => {
    setSelectedIds(prev => prev.includes(issueId) ? prev.filter(id => id !== issueId) : [...prev, issueId]);
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedIds(prev => prev.length === issues.length ? [] : issues.map(i => i.id));
  }, [issues]);

  const clearSelection = useCallback(() => setSelectedIds([]), []);

  useEffect(() => {
    setSelectedIds([]);
  }, [page, issues]);

  const handleUndoAction = useCallback(async (actionId) => {
    try {
      const res = await api.post(`/product-hub/action-history/${actionId}/undo`);
      toast.success(`تم التراجع — استعادة ${res.data.restored_count} تحدي`);
      if (onRefresh) onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail ?? getApiErrorMessage(err);
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في التراجع'));
    }
  }, [api, onRefresh]);

  const handleBulkEdit = useCallback(async (fields) => {
    const validIds = selectedIds.filter(id => id != null && id !== '');
    if (validIds.length === 0) {
      toast.error('لا توجد تحديات صالحة للتعديل');
      return;
    }
    try {
      const res = await api.post('/product-hub/issues/bulk-update', {
        issue_ids: validIds,
        ...fields,
      });
      const actionId = res.data.action_id;
      toast.success(`تم تحديث ${res.data.modified_count} تحدي`, {
        action: actionId ? { label: 'تراجع', onClick: () => handleUndoAction(actionId) } : undefined,
        duration: 8000,
      });
      setSelectedIds([]);
      if (onRefresh) onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail ?? getApiErrorMessage(err);
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في التعديل الجماعي'));
      throw err;
    }
  }, [selectedIds, onRefresh, handleUndoAction]);

  const handleBulkDelete = useCallback(async () => {
    const validIds = selectedIds.filter(id => id != null && id !== '');
    if (validIds.length === 0) {
      toast.error('لا توجد تحديات صالحة للحذف');
      return;
    }
    try {
      const res = await api.post('/product-hub/issues/bulk-delete', {
        issue_ids: validIds,
      });
      const actionId = res.data.action_id;
      toast.success(`تم حذف ${res.data.deleted_count} تحدي`, {
        action: actionId ? { label: 'تراجع', onClick: () => handleUndoAction(actionId) } : undefined,
        duration: 8000,
      });
      setSelectedIds([]);
      if (onRefresh) onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail ?? getApiErrorMessage(err);
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في الحذف الجماعي'));
      throw err;
    }
  }, [selectedIds, onRefresh, handleUndoAction]);

  if (loading) {
    return (
      <LoadingState variant="section" label="جاري التحميل..." />
    );
  }

  if (issues.length === 0) {
    return (
      <Card className="border rounded-xl">
        <CardContent>
          <EmptyState icon={Bug} title="لا توجد تحديات" description="لم يتم العثور على تحديات تطابق معايير البحث" />
        </CardContent>
      </Card>
    );
  }

  const allSelected = selectedIds.length === issues.length && issues.length > 0;

  return (
    <div className="space-y-4">
      {isMainAdmin && (
        <BulkActionBar
          selectedIds={selectedIds}
          onClearSelection={clearSelection}
          onBulkEdit={() => setShowBulkEdit(true)}
          onBulkDelete={() => setShowBulkDelete(true)}
        />
      )}

      {isMainAdmin && (
        <div className="flex items-center justify-between" dir="rtl">
          <label className="flex items-center gap-2 cursor-pointer select-none group">
            <div
              onClick={toggleSelectAll}
              className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all cursor-pointer ${
                allSelected
                  ? 'bg-brand-turquoise border-brand-turquoise text-white'
                  : 'border-slate-300 hover:border-brand-turquoise/50 bg-white'
              }`}
            >
              {allSelected && <CheckCircle2 className="h-3.5 w-3.5" />}
            </div>
            <span className="text-xs text-slate-500 font-medium group-hover:text-brand-navy">تحديد الكل</span>
          </label>
          <div className="flex items-center gap-2">
            {expandedId && (
              <Button
                variant="ghost" size="sm"
                onClick={() => setExpandedId(null)}
                className="text-xs text-slate-400 hover:text-brand-navy gap-1.5 h-7 rounded-lg"
              >
                <Minimize2 className="h-3 w-3" /> طي الكل
              </Button>
            )}
            <Button
              variant="ghost" size="sm"
              onClick={async () => {
                try {
                  await api.post('/product-hub/issues/resequence');
                  toast.success('تم إعادة ترقيم التحديات بنجاح');
                  onRefresh?.();
                } catch (e) {
                  toast.error('فشل في إعادة الترقيم');
                }
              }}
              className="text-xs text-slate-400 hover:text-brand-navy gap-1.5 h-7 rounded-lg"
            >
              <Hash className="h-3 w-3" /> إعادة ترقيم
            </Button>
          </div>
        </div>
      )}

      {!isMainAdmin && expandedId && (
        <div className="flex justify-end">
          <Button
            variant="ghost" size="sm"
            onClick={() => setExpandedId(null)}
            className="text-xs text-slate-400 hover:text-brand-navy gap-1.5 h-7 rounded-lg"
          >
            <Minimize2 className="h-3 w-3" /> طي الكل
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {issues.map(issue => {
          const isSelected = selectedIds.includes(issue.id);
          return (
            <div key={issue.id} className={isSelected ? 'ring-2 ring-brand-turquoise/40 rounded-2xl' : ''}>
              <IssuePanel
                issue={issue}
                navigate={navigate}
                isHighlighted={highlightId === issue.id}
                isMainAdmin={isMainAdmin}
                isAdmin={isAdmin}
                userId={user?.id}
                onRefresh={onRefresh}
                isExpanded={expandedId === issue.id}
                onToggleExpand={handleToggleExpand}
                isSelected={isSelected}
                onToggleSelect={toggleSelect}
              />
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-3 pt-4 pb-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(p => p - 1)} className="rounded-xl h-9 w-9 p-0 border-slate-200">
            <ChevronRight className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2 px-4 py-1.5 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-xs text-slate-500 font-medium">
              صفحة <span className="font-bold text-brand-navy">{page}</span> من <span className="font-bold text-brand-navy">{totalPages}</span>
            </span>
            <span className="text-[10px] text-slate-400">({total} تحدي)</span>
          </div>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(p => p + 1)} className="rounded-xl h-9 w-9 p-0 border-slate-200">
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      )}

      {isMainAdmin && (
        <>
          <BulkEditModal
            open={showBulkEdit}
            onClose={() => setShowBulkEdit(false)}
            selectedCount={selectedIds.length}
            onSubmit={handleBulkEdit}
          />
          <BulkDeleteModal
            open={showBulkDelete}
            onClose={() => setShowBulkDelete(false)}
            selectedCount={selectedIds.length}
            onConfirm={handleBulkDelete}
          />
        </>
      )}
    </div>
  );
}
