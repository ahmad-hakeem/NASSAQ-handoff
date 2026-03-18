import React, { useState, useEffect, useRef } from 'react';
import {
  Database, Users, BookOpen, Shield, AlertTriangle,
  LayoutGrid, ClipboardCheck, Sparkles, CheckCircle2,
  XCircle, Loader2, Clock, ArrowLeft
} from 'lucide-react';
import HakimCharacter from './HakimCharacter';

const GENERATION_STEPS = [
  {
    id: 'read_data',
    title: 'قراءة بيانات المدرسة',
    description: 'تحميل بيانات الفصول والحصص والأوقات',
    icon: Database,
    hakimMessage: 'أقوم الآن بقراءة بيانات المدرسة الحالية وجميع الإعدادات...',
    duration: 1800,
  },
  {
    id: 'review_teachers',
    title: 'مراجعة المعلمين والفصول',
    description: 'التحقق من بيانات المعلمين وتوزيعهم على الفصول',
    icon: Users,
    hakimMessage: 'أراجع بيانات المعلمين والفصول الدراسية وأتأكد من اكتمالها...',
    duration: 2000,
  },
  {
    id: 'verify_assignments',
    title: 'التحقق من الإسنادات',
    description: 'مطابقة إسنادات المعلمين بالمواد والفصول',
    icon: BookOpen,
    hakimMessage: 'أتحقق من إسنادات المعلمين والمواد وأتأكد من عدم وجود نقص...',
    duration: 2200,
  },
  {
    id: 'check_constraints',
    title: 'التحقق من القيود الإلزامية',
    description: 'مراجعة جميع القيود والشروط الأساسية',
    icon: Shield,
    hakimMessage: 'أراجع القيود الأساسية لمنع أي تعارض في الجدول النهائي...',
    duration: 2000,
  },
  {
    id: 'resolve_conflicts',
    title: 'معالجة التعارضات',
    description: 'كشف ومعالجة أي تعارضات محتملة',
    icon: AlertTriangle,
    hakimMessage: 'أبحث عن أي تعارضات محتملة وأعمل على حلها تلقائياً...',
    duration: 2500,
  },
  {
    id: 'distribute_sessions',
    title: 'توزيع الحصص',
    description: 'توزيع الحصص بشكل متوازن على أيام الأسبوع',
    icon: LayoutGrid,
    hakimMessage: 'أعمل الآن على توزيع الحصص بشكل متوازن ومنظم على جميع الأيام...',
    duration: 3000,
  },
  {
    id: 'review_result',
    title: 'مراجعة النتيجة النهائية',
    description: 'فحص جودة الجدول والتأكد من خلوه من الأخطاء',
    icon: ClipboardCheck,
    hakimMessage: 'أوشكت على الانتهاء! أراجع الآن النتيجة النهائية وجودة التوزيع...',
    duration: 1500,
  },
  {
    id: 'prepare_display',
    title: 'تجهيز الجدول للعرض',
    description: 'حفظ النتائج وتجهيز الجدول للمراجعة',
    icon: Sparkles,
    hakimMessage: 'أجهز الآن النسخة النهائية من الجدول ليكون جاهزاً للمراجعة!',
    duration: 1200,
  },
];

const StepStatus = {
  PENDING: 'pending',
  ACTIVE: 'active',
  COMPLETED: 'completed',
  FAILED: 'failed',
};

const TimetableGenerationJourney = ({
  isVisible,
  status,
  errorMessage,
  onRetry,
  onClose,
  apiCompleted,
  apiFailed,
}) => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [stepStatuses, setStepStatuses] = useState(
    GENERATION_STEPS.map(() => StepStatus.PENDING)
  );
  const [overallProgress, setOverallProgress] = useState(0);
  const [hakimText, setHakimText] = useState(GENERATION_STEPS[0].hakimMessage);
  const [showCompletionBurst, setShowCompletionBurst] = useState(false);
  const timerRef = useRef(null);
  const completedRef = useRef(false);
  const stepsContainerRef = useRef(null);

  useEffect(() => {
    if (!isVisible) {
      setCurrentStepIndex(0);
      setStepStatuses(GENERATION_STEPS.map(() => StepStatus.PENDING));
      setOverallProgress(0);
      setHakimText(GENERATION_STEPS[0].hakimMessage);
      setShowCompletionBurst(false);
      completedRef.current = false;
      return;
    }

    setStepStatuses(prev => {
      const next = [...prev];
      next[0] = StepStatus.ACTIVE;
      return next;
    });
    setHakimText(GENERATION_STEPS[0].hakimMessage);
  }, [isVisible]);

  useEffect(() => {
    if (!isVisible) return;

    if (apiFailed) {
      completedRef.current = false;
      setStepStatuses(prev => {
        const next = [...prev];
        next[currentStepIndex] = StepStatus.FAILED;
        return next;
      });
      setHakimText(
        errorMessage
          ? `واجهت مشكلة في هذه الخطوة: ${errorMessage}`
          : 'واجهت مشكلة غير متوقعة. يمكنك المحاولة مرة أخرى.'
      );
      return;
    }

    if (apiCompleted && !completedRef.current) {
      completedRef.current = true;
      const completeRemaining = () => {
        setStepStatuses(GENERATION_STEPS.map(() => StepStatus.COMPLETED));
        setOverallProgress(100);
        setCurrentStepIndex(GENERATION_STEPS.length - 1);
        setHakimText('ممتاز! تم إنشاء الجدول الدراسي بنجاح وبدون أي مشاكل! 🎉');
        setShowCompletionBurst(true);
      };

      if (currentStepIndex >= GENERATION_STEPS.length - 2) {
        completeRemaining();
      } else {
        const remaining = GENERATION_STEPS.length - currentStepIndex - 1;
        let idx = currentStepIndex;
        const fastForward = setInterval(() => {
          idx++;
          if (idx >= GENERATION_STEPS.length) {
            clearInterval(fastForward);
            completeRemaining();
            return;
          }
          setStepStatuses(prev => {
            const next = [...prev];
            for (let i = 0; i < idx; i++) next[i] = StepStatus.COMPLETED;
            next[idx] = StepStatus.ACTIVE;
            return next;
          });
          setCurrentStepIndex(idx);
          setHakimText(GENERATION_STEPS[idx].hakimMessage);
          setOverallProgress(Math.round(((idx + 1) / GENERATION_STEPS.length) * 100));
        }, 250);
        return () => clearInterval(fastForward);
      }
      return;
    }

    if (completedRef.current || currentStepIndex >= GENERATION_STEPS.length) return;

    const step = GENERATION_STEPS[currentStepIndex];
    timerRef.current = setTimeout(() => {
      if (apiCompleted || apiFailed || completedRef.current) return;

      const nextIndex = currentStepIndex + 1;
      if (nextIndex < GENERATION_STEPS.length) {
        setStepStatuses(prev => {
          const next = [...prev];
          next[currentStepIndex] = StepStatus.COMPLETED;
          next[nextIndex] = StepStatus.ACTIVE;
          return next;
        });
        setCurrentStepIndex(nextIndex);
        setHakimText(GENERATION_STEPS[nextIndex].hakimMessage);
        setOverallProgress(Math.round(((nextIndex) / GENERATION_STEPS.length) * 100));
      } else {
        if (!apiCompleted) {
          setHakimText('أقوم بالمعالجة النهائية... لحظات قليلة فقط ⏳');
        }
      }
    }, step.duration);

    return () => clearTimeout(timerRef.current);
  }, [isVisible, currentStepIndex, apiCompleted, apiFailed, errorMessage]);

  useEffect(() => {
    if (stepsContainerRef.current && currentStepIndex > 2) {
      const stepEl = stepsContainerRef.current.children[currentStepIndex];
      if (stepEl) {
        stepEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [currentStepIndex]);

  if (!isVisible) return null;

  const allCompleted = stepStatuses.every(s => s === StepStatus.COMPLETED);
  const hasFailed = stepStatuses.some(s => s === StepStatus.FAILED);

  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/50 backdrop-blur-sm" dir="rtl">
      <div
        className="relative bg-white rounded-3xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden animate-in zoom-in-95 fade-in duration-500"
        style={{ maxHeight: '90vh' }}
      >
        <div className="absolute -top-1 -left-1 -right-1 h-2 rounded-t-3xl bg-gradient-to-l from-violet-500 via-purple-500 to-indigo-500" />

        <div className={`px-6 pt-6 pb-5 transition-all duration-700 ${allCompleted ? 'bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-600' : 'bg-gradient-to-l from-[#1a1f4e] via-[#252b6e] to-[#2d3594]'}`}>
          {allCompleted ? (
            <div className="flex flex-col items-center text-center py-4">
              <div className="relative mb-4">
                <div className="absolute -inset-6 rounded-full bg-white/20 blur-xl animate-pulse" />
                <div className="relative w-56 h-56 rounded-full overflow-hidden border-4 border-white/40 shadow-2xl bg-gradient-to-br from-emerald-50 to-cyan-50 p-3">
                  <img src="/hakim-poses/congratulating-student.png" alt="حكيم" className="hakim-img w-full h-full object-contain drop-shadow-lg" style={{ animation: 'hakimCelebrateHero 1.5s ease-in-out infinite' }} />
                </div>
                <div className="absolute -top-2 -right-2 w-10 h-10 rounded-full bg-yellow-400 flex items-center justify-center shadow-lg animate-bounce text-xl">🎉</div>
                <div className="absolute -bottom-1 -left-2 w-8 h-8 rounded-full bg-emerald-300 flex items-center justify-center shadow-lg animate-bounce text-lg" style={{ animationDelay: '0.3s' }}>⭐</div>
              </div>
              <h2 className="text-2xl font-bold text-white font-cairo mb-2">تم إنشاء الجدول بنجاح! 🎉</h2>
              <div className="relative bg-white/15 backdrop-blur-sm border border-white/20 rounded-2xl px-5 py-3 max-w-sm">
                <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 rotate-45 bg-white/15 border-t border-l border-white/20" />
                <p className="text-white/90 text-sm font-tajawal leading-relaxed">{hakimText}</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <div className="relative flex-shrink-0">
                <HakimCharacter
                  state={hasFailed ? 'error' : 'generating'}
                  size="lg"
                  showMessage={false}
                />
                {!hasFailed && (
                  <div className="absolute -bottom-1 -left-1 w-5 h-5 rounded-full bg-violet-400 flex items-center justify-center animate-ping opacity-40" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-lg font-bold text-white font-cairo">
                  {hasFailed ? 'واجهت مشكلة أثناء الإنشاء' : 'حكيم يعمل على إنشاء الجدول...'}
                </h2>
                <div
                  className={`relative mt-2 rounded-xl px-4 py-3 text-sm font-tajawal leading-relaxed transition-all duration-500 ${
                    hasFailed
                      ? 'bg-red-500/20 border border-red-400/30 text-red-200'
                      : 'bg-white/10 border border-white/15 text-white/90'
                  }`}
                >
                  <div className="absolute -top-1.5 right-6 w-3 h-3 rotate-45 border-t border-r border-inherit bg-inherit" />
                  {hakimText}
                </div>
              </div>
            </div>
          )}
          <style>{`@keyframes hakimCelebrateHero { 0%, 100% { transform: scale(1) rotate(0deg); } 15% { transform: scale(1.1) rotate(-5deg); } 30% { transform: scale(1.05) rotate(5deg); } 45% { transform: scale(1.08) rotate(-3deg); } 60% { transform: scale(1.03) rotate(2deg); } 80% { transform: scale(1.06) rotate(-1deg); } }`}</style>
        </div>

        <div className="px-6 pt-4 pb-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-500">التقدم الكلي</span>
            <span className="text-xs font-bold text-violet-600">{overallProgress}%</span>
          </div>
          <div className="w-full h-2.5 rounded-full bg-gray-100 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${
                hasFailed
                  ? 'bg-gradient-to-l from-red-500 to-rose-500'
                  : allCompleted
                  ? 'bg-gradient-to-l from-emerald-500 to-teal-500'
                  : 'bg-gradient-to-l from-violet-500 via-purple-500 to-indigo-500'
              }`}
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>

        <div
          ref={stepsContainerRef}
          className="px-6 py-4 space-y-1 overflow-y-auto"
          style={{ maxHeight: 'calc(90vh - 300px)' }}
        >
          {GENERATION_STEPS.map((step, index) => {
            const stepStatus = stepStatuses[index];
            const Icon = step.icon;
            const isActive = stepStatus === StepStatus.ACTIVE;
            const isCompleted = stepStatus === StepStatus.COMPLETED;
            const isFailed = stepStatus === StepStatus.FAILED;
            const isPending = stepStatus === StepStatus.PENDING;

            return (
              <div
                key={step.id}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-500 ${
                  isActive
                    ? 'bg-gradient-to-l from-violet-50 to-purple-50 border border-violet-200 shadow-sm scale-[1.02]'
                    : isCompleted
                    ? 'bg-emerald-50/50 border border-emerald-100'
                    : isFailed
                    ? 'bg-red-50 border border-red-200 shadow-sm'
                    : 'bg-gray-50/50 border border-transparent'
                }`}
              >
                <div className="relative flex-shrink-0">
                  {isActive && (
                    <div className="absolute inset-0 rounded-xl bg-violet-400 animate-ping opacity-20" style={{ width: 40, height: 40 }} />
                  )}
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-500 ${
                      isCompleted
                        ? 'bg-gradient-to-br from-emerald-400 to-teal-500 shadow-md shadow-emerald-200'
                        : isActive
                        ? 'bg-gradient-to-br from-violet-500 to-purple-600 shadow-md shadow-violet-200'
                        : isFailed
                        ? 'bg-gradient-to-br from-red-400 to-rose-500 shadow-md shadow-red-200'
                        : 'bg-gray-200'
                    }`}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="h-5 w-5 text-white" />
                    ) : isActive ? (
                      <Loader2 className="h-5 w-5 text-white animate-spin" />
                    ) : isFailed ? (
                      <XCircle className="h-5 w-5 text-white" />
                    ) : (
                      <Icon className="h-5 w-5 text-gray-400" />
                    )}
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-bold transition-colors duration-300 ${
                        isCompleted
                          ? 'text-emerald-700'
                          : isActive
                          ? 'text-violet-800'
                          : isFailed
                          ? 'text-red-700'
                          : 'text-gray-400'
                      }`}
                    >
                      {step.title}
                    </span>
                    {isCompleted && (
                      <span className="text-[10px] bg-emerald-100 text-emerald-600 px-1.5 py-0.5 rounded-full font-bold">تم</span>
                    )}
                    {isFailed && (
                      <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-bold">فشل</span>
                    )}
                  </div>
                  <p
                    className={`text-xs mt-0.5 transition-colors duration-300 ${
                      isCompleted
                        ? 'text-emerald-500'
                        : isActive
                        ? 'text-violet-500'
                        : isFailed
                        ? 'text-red-500'
                        : 'text-gray-300'
                    }`}
                  >
                    {step.description}
                  </p>
                </div>

                <div className="flex-shrink-0">
                  {isCompleted && <CheckCircle2 className="h-5 w-5 text-emerald-400" />}
                  {isActive && (
                    <div className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-300 animate-pulse" style={{ animationDelay: '0.15s' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-200 animate-pulse" style={{ animationDelay: '0.3s' }} />
                    </div>
                  )}
                  {isFailed && <XCircle className="h-5 w-5 text-red-400" />}
                </div>
              </div>
            );
          })}
        </div>

        <div className="px-6 pb-5 pt-2">
          {hasFailed && (
            <div className="flex items-center gap-3">
              <button
                onClick={onRetry}
                className="flex-1 flex items-center justify-center gap-2 bg-gradient-to-l from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white font-bold py-3 rounded-xl transition-all shadow-lg hover:shadow-xl"
              >
                <ArrowLeft className="h-4 w-4 rotate-180" />
                إعادة المحاولة
              </button>
              <button
                onClick={onClose}
                className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-600 font-bold rounded-xl transition-all"
              >
                إغلاق
              </button>
            </div>
          )}
          {!hasFailed && !allCompleted && (
            <div className="flex items-center justify-center gap-2 text-gray-400 text-sm">
              <Clock className="h-4 w-4" />
              <span className="font-tajawal">يرجى الانتظار حتى اكتمال جميع المراحل...</span>
            </div>
          )}
          {allCompleted && showCompletionBurst && (
            <div className="flex items-center justify-center gap-2">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="w-2 h-2 rounded-full bg-emerald-300 animate-pulse" style={{ animationDelay: '0.2s' }} />
                <span className="w-2 h-2 rounded-full bg-emerald-200 animate-pulse" style={{ animationDelay: '0.4s' }} />
                <span className="text-sm text-emerald-600 font-tajawal font-bold ms-2">
                  جاري الانتقال لعرض الجدول...
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TimetableGenerationJourney;
