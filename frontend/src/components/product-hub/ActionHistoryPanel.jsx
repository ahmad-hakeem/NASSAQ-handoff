import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '../ui/button';
import { toast } from 'sonner';
import {
  STATUS_CONFIG, PRIORITY_CONFIG,
} from './index';
import {
  Users, Activity, Timer,
  RefreshCw, Layers, Loader2, Trash2, Pencil, History, Undo2, X,
} from 'lucide-react';

const ACTION_TYPE_LABELS = {
  bulk_edit: { label: 'تعديل جماعي', icon: Pencil, color: 'text-brand-turquoise', bg: 'bg-brand-turquoise/10' },
  bulk_delete: { label: 'حذف جماعي', icon: Trash2, color: 'text-red-500', bg: 'bg-red-50' },
  status_change: { label: 'تغيير الحالة', icon: Activity, color: 'text-blue-500', bg: 'bg-blue-50' },
  assignment_change: { label: 'تغيير التعيين', icon: Users, color: 'text-violet-500', bg: 'bg-violet-50' },
};

const ACTION_STATUS_LABELS = {
  active: { label: 'نشط', color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  expired: { label: 'منتهي', color: 'text-slate-400', bg: 'bg-slate-50', border: 'border-slate-200' },
  undone: { label: 'تم التراجع', color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200' },
};

export default function ActionHistoryPanel({ open, onClose, onRefresh, api }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [undoing, setUndoing] = useState(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/product-hub/action-history');
      setRecords(res.data.records || []);
    } catch {
      toast.error('فشل في تحميل سجل العمليات');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchHistory();
  }, [open, fetchHistory]);

  const handleUndo = async (actionId) => {
    setUndoing(actionId);
    try {
      const res = await api.post(`/product-hub/action-history/${actionId}/undo`);
      toast.success(`تم التراجع — استعادة ${res.data.restored_count} تحدي`);
      fetchHistory();
      if (onRefresh) onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في التراجع'));
    } finally {
      setUndoing(null);
    }
  };

  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return '';
    const diff = Date.now() - new Date(timestamp).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'الآن';
    if (mins < 60) return `منذ ${mins} دقيقة`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `منذ ${hours} ساعة`;
    const days = Math.floor(hours / 24);
    return `منذ ${days} يوم`;
  };

  const getExpiryRemaining = (expiry) => {
    if (!expiry) return '';
    const diff = new Date(expiry).getTime() - Date.now();
    if (diff <= 0) return 'منتهي';
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins} دقيقة متبقية`;
    return `${Math.floor(mins / 60)} ساعة متبقية`;
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg bg-white shadow-2xl flex flex-col h-full"
        onClick={e => e.stopPropagation()}
        dir="rtl"
      >
        <div className="px-5 py-4 border-b border-slate-100 bg-gradient-to-l from-brand-navy/5 to-transparent flex items-center justify-between flex-shrink-0">
          <h3 className="text-base font-bold text-brand-navy flex items-center gap-2">
            <History className="h-4 w-4 text-brand-turquoise" />
            سجل العمليات
          </h3>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={fetchHistory} className="h-7 w-7 p-0 text-slate-400 hover:text-brand-navy">
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose} className="h-7 w-7 p-0 text-slate-400 hover:text-brand-navy">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            <div className="flex justify-center items-center py-16">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" />
                <span className="text-xs text-slate-400">جاري التحميل...</span>
              </div>
            </div>
          ) : records.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <History className="h-10 w-10 text-slate-200 mb-3" />
              <p className="text-sm text-slate-400 font-medium">لا توجد عمليات سابقة</p>
              <p className="text-xs text-slate-300 mt-1">ستظهر هنا جميع العمليات الجماعية</p>
            </div>
          ) : (
            records.map((record) => {
              const typeCfg = ACTION_TYPE_LABELS[record.action_type] || ACTION_TYPE_LABELS.bulk_edit;
              const statusCfg = ACTION_STATUS_LABELS[record.status] || ACTION_STATUS_LABELS.expired;
              const TypeIcon = typeCfg.icon;
              const isUndoable = record.is_undoable && record.status === 'active';

              const changedFields = [];
              if (record.after_state?.status) changedFields.push(`الحالة → ${STATUS_CONFIG[record.after_state.status]?.label || record.after_state.status}`);
              if (record.after_state?.priority) changedFields.push(`الأولوية → ${PRIORITY_CONFIG[record.after_state.priority]?.label || record.after_state.priority}`);
              if (record.after_state?.assigned_team) changedFields.push(`الفريق → ${record.after_state.assigned_team}`);
              if (record.after_state?.is_deleted) changedFields.push('حذف');

              return (
                <div key={record.action_id} className={`rounded-xl border p-4 transition-all hover:shadow-sm ${isUndoable ? 'border-slate-200 bg-white' : 'border-slate-100 bg-slate-50/50'}`}>
                  <div className="flex items-start justify-between gap-3 mb-2.5">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-8 h-8 rounded-lg ${typeCfg.bg} flex items-center justify-center flex-shrink-0`}>
                        <TypeIcon className={`h-4 w-4 ${typeCfg.color}`} />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-brand-navy">{typeCfg.label}</p>
                        <p className="text-[10px] text-slate-400">{formatTimeAgo(record.timestamp)}</p>
                      </div>
                    </div>
                    <div className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusCfg.bg} ${statusCfg.color} ${statusCfg.border}`}>
                      {statusCfg.label}
                    </div>
                  </div>

                  <div className="space-y-1.5 mb-3">
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <Users className="h-3 w-3 text-slate-400" />
                      <span>{record.performed_by_name || record.performed_by}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <Layers className="h-3 w-3 text-slate-400" />
                      <span>{record.affected_count} تحدي</span>
                    </div>
                    {changedFields.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {changedFields.map((f, i) => (
                          <span key={i} className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md">{f}</span>
                        ))}
                      </div>
                    )}
                    {record.status === 'undone' && (
                      <div className="flex items-center gap-2 text-xs text-amber-600">
                        <Undo2 className="h-3 w-3" />
                        <span>تم التراجع بواسطة {record.undone_by} — استعادة {record.restored_count} تحدي</span>
                      </div>
                    )}
                  </div>

                  {isUndoable && (
                    <div className="flex items-center justify-between pt-2.5 border-t border-slate-100">
                      <span className="text-[10px] text-slate-400 flex items-center gap-1">
                        <Timer className="h-3 w-3" />
                        {getExpiryRemaining(record.undo_expiry)}
                      </span>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleUndo(record.action_id)}
                        disabled={undoing === record.action_id}
                        className="h-7 text-xs gap-1.5 rounded-lg border-amber-200 text-amber-700 hover:bg-amber-50 hover:border-amber-300"
                      >
                        {undoing === record.action_id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Undo2 className="h-3 w-3" />}
                        تراجع
                      </Button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
