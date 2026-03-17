import React from 'react';
import { Button } from '../../components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip';
import { 
  Wand2, Send, Settings, Printer, Download,
  Loader2, AlertCircle
} from 'lucide-react';

const TimetableActionBar = ({
  canGenerate = false,
  canPublish = false,
  isGenerating = false,
  hasDraftVersion = false,
  hasPublishedVersion = false,
  disabledReason = '',
  onGenerateClick,
  onPublishClick,
  onGoToSettingsClick,
  onPrintClick,
  onExportClick
}) => {

  return (
    <div 
      className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white rounded-xl border border-gray-200 shadow-sm"
      data-testid="timetable-action-bar"
    >
      <div className="flex items-center gap-2">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button 
                variant="outline" 
                size="sm"
                onClick={onGoToSettingsClick}
                className="gap-2"
                data-testid="go-to-settings-btn"
              >
                <Settings className="h-4 w-4" />
                إعدادات المدرسة
              </Button>
            </TooltipTrigger>
            <TooltipContent>الانتقال لإعدادات المدرسة</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {(hasDraftVersion || hasPublishedVersion) && (
          <>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onPrintClick}
                    className="gap-2"
                    data-testid="print-timetable-btn"
                  >
                    <Printer className="h-4 w-4" />
                    طباعة
                  </Button>
                </TooltipTrigger>
                <TooltipContent>طباعة الجدول</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onExportClick}
                    className="gap-2"
                    data-testid="export-timetable-btn"
                  >
                    <Download className="h-4 w-4" />
                    تصدير
                  </Button>
                </TooltipTrigger>
                <TooltipContent>تصدير الجدول كملف Excel</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        {canPublish && hasDraftVersion && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button 
                  size="sm"
                  onClick={onPublishClick}
                  disabled={isGenerating}
                  className="gap-2 bg-green-600 hover:bg-green-700 text-white"
                  data-testid="publish-version-btn"
                >
                  <Send className="h-4 w-4" />
                  نشر النسخة
                </Button>
              </TooltipTrigger>
              <TooltipContent>نشر النسخة الحالية للمستخدمين</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <Button 
                  onClick={onGenerateClick}
                  disabled={!canGenerate || isGenerating}
                  className={`gap-2 px-6 py-2 shadow-lg transition-all ${
                    canGenerate && !isGenerating
                      ? 'bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 hover:shadow-xl hover:scale-[1.02]'
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  }`}
                  data-testid="ai-generate-btn"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      جاري المعالجة...
                    </>
                  ) : (
                    <>
                      <Wand2 className="h-5 w-5" />
                      معالجة الجدول بالذكاء الاصطناعي
                    </>
                  )}
                </Button>
              </div>
            </TooltipTrigger>
            {!canGenerate && disabledReason && (
              <TooltipContent className="max-w-xs bg-red-50 text-red-700 border-red-200">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <span>{disabledReason}</span>
                </div>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
};

export default TimetableActionBar;
