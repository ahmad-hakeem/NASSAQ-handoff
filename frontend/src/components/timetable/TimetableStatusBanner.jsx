/**
 * TimetableStatusBanner Component
 * شريط حالة الجدول المدرسي
 * 
 * يعرض الحالة التشغيلية الحالية للجدول ويتغير حسب حالة النظام
 */

import React from 'react';
import { Button } from '../../components/ui/button';
import { Progress } from '../../components/ui/progress';
import { Badge } from '../../components/ui/badge';
import { 
  AlertCircle, CheckCircle2, Clock, Loader2, FileText,
  AlertTriangle, XCircle, Eye, Send, Wand2, RefreshCw
} from 'lucide-react';
import { TimetableStatus } from './types';

const TimetableStatusBanner = ({
  status = TimetableStatus.NONE,
  versionName = '',
  generatedAt = '',
  publishedAt = '',
  generatedBy = '',
  qualityScore = 0,
  warningsCount = 0,
  conflictsCount = 0,
  message = '',
  progress = 0,
  progressMessage = '',
  onViewDiagnostics,
  onPublishDraft,
  onStartGeneration,
  onViewVersion
}) => {

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('ar-SA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  // === State A: No Timetable ===
  if (status === TimetableStatus.NONE) {
    return (
      <div 
        className="bg-gradient-to-r from-slate-50 to-gray-100 border border-slate-200 rounded-xl p-5"
        data-testid="status-banner-empty"
      >
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-slate-200 flex items-center justify-center">
            <FileText className="h-6 w-6 text-slate-500" />
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-slate-700 text-lg">لا توجد نسخة جدول مولدة حاليًا</h3>
            <p className="text-slate-500 mt-1 text-sm">
              يمكنك بدء التوليد باستخدام الذكاء الاصطناعي بعد التأكد من اكتمال الإعدادات
            </p>
          </div>
          {onStartGeneration && (
            <Button 
              onClick={onStartGeneration}
              className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700"
              data-testid="start-generation-btn"
            >
              <Wand2 className="h-4 w-4 ml-2" />
              ابدأ التوليد
            </Button>
          )}
        </div>
      </div>
    );
  }

  // === State B: Draft Exists ===
  if (status === TimetableStatus.DRAFT) {
    return (
      <div 
        className="bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-xl p-5"
        data-testid="status-banner-draft"
      >
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
            <Clock className="h-6 w-6 text-amber-600" />
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-amber-800 text-lg">توجد نسخة مسودة غير منشورة</h3>
              {versionName && (
                <Badge variant="outline" className="bg-amber-100 text-amber-700 border-amber-300">
                  {versionName}
                </Badge>
              )}
            </div>
            
            <div className="flex flex-wrap items-center gap-4 text-sm text-amber-700">
              {generatedAt && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  تاريخ التوليد: {formatDate(generatedAt)}
                </span>
              )}
              {generatedBy && (
                <span>بواسطة: {generatedBy}</span>
              )}
              {qualityScore > 0 && (
                <span className="flex items-center gap-1">
                  جودة: {Math.round(qualityScore)}%
                </span>
              )}
              {warningsCount > 0 && (
                <span className="flex items-center gap-1 text-amber-600">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {warningsCount} تحذير
                </span>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {onViewVersion && (
              <Button variant="outline" onClick={onViewVersion} className="border-amber-300 text-amber-700 hover:bg-amber-50">
                <Eye className="h-4 w-4 ml-2" />
                عرض النسخة
              </Button>
            )}
            {onPublishDraft && (
              <Button 
                onClick={onPublishDraft}
                className="bg-green-600 hover:bg-green-700 text-white"
                data-testid="publish-draft-btn"
              >
                <Send className="h-4 w-4 ml-2" />
                نشر النسخة
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // === State C: Published Exists ===
  if (status === TimetableStatus.PUBLISHED) {
    return (
      <div 
        className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-5"
        data-testid="status-banner-published"
      >
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-green-100 flex items-center justify-center">
            <CheckCircle2 className="h-6 w-6 text-green-600" />
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-green-800 text-lg">هذه هي النسخة المنشورة الحالية</h3>
              {versionName && (
                <Badge className="bg-green-100 text-green-700 border border-green-300">
                  {versionName}
                </Badge>
              )}
            </div>
            
            <div className="flex flex-wrap items-center gap-4 text-sm text-green-700">
              {publishedAt && (
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  تاريخ النشر: {formatDate(publishedAt)}
                </span>
              )}
              {qualityScore > 0 && (
                <span className="flex items-center gap-1">
                  جودة: {Math.round(qualityScore)}%
                </span>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {onStartGeneration && (
              <Button 
                variant="outline"
                onClick={onStartGeneration}
                className="border-violet-300 text-violet-700 hover:bg-violet-50"
                data-testid="create-new-draft-btn"
              >
                <Wand2 className="h-4 w-4 ml-2" />
                إنشاء مسودة جديدة
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // === State D: Generating ===
  if (status === TimetableStatus.GENERATING) {
    return (
      <div 
        className="bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200 rounded-xl p-5"
        data-testid="status-banner-generating"
      >
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-violet-100 flex items-center justify-center animate-pulse">
            <Loader2 className="h-6 w-6 text-violet-600 animate-spin" />
          </div>
          <div className="flex-1 space-y-3">
            <h3 className="font-bold text-violet-800 text-lg">يتم الآن معالجة الجدول بالذكاء الاصطناعي</h3>
            
            {progressMessage && (
              <p className="text-violet-600 text-sm">{progressMessage}</p>
            )}
            
            <Progress value={progress} className="h-2 [&>div]:bg-violet-600" />
            
            <p className="text-violet-500 text-xs">
              يرجى عدم إغلاق الصفحة أثناء المعالجة...
            </p>
          </div>
        </div>
      </div>
    );
  }

  // === State E: Failed ===
  if (status === TimetableStatus.FAILED) {
    return (
      <div 
        className="bg-gradient-to-r from-red-50 to-rose-50 border border-red-200 rounded-xl p-5"
        data-testid="status-banner-failed"
      >
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center">
            <XCircle className="h-6 w-6 text-red-600" />
          </div>
          <div className="flex-1 space-y-2">
            <h3 className="font-bold text-red-800 text-lg">فشل في معالجة الجدول</h3>
            {message && (
              <p className="text-red-600 text-sm">{message}</p>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {onViewDiagnostics && (
              <Button variant="outline" onClick={onViewDiagnostics} className="border-red-300 text-red-700 hover:bg-red-50">
                <AlertCircle className="h-4 w-4 ml-2" />
                عرض التشخيص
              </Button>
            )}
            {onStartGeneration && (
              <Button 
                onClick={onStartGeneration}
                className="bg-red-600 hover:bg-red-700 text-white"
                data-testid="retry-generation-btn"
              >
                <RefreshCw className="h-4 w-4 ml-2" />
                إعادة المحاولة
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // === Default / Unknown State ===
  return null;
};

export default TimetableStatusBanner;
