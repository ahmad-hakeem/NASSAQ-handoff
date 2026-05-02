/**
 * FilledCell — خانة المعلم في مصفوفة الجدول الذكية.
 *
 * استُخرج هذا المكوّن من SchedulePageNew.jsx ليُختبر بمعزل عن بقية الصفحة
 * (التي تسحب Sidebar والمصادقة وعشرات الـmodals). يحافظ المكوّن على نفس
 * السلوك الأصلي بالضبط: أربع حالات (عادية، شاغرة، مُستبدلة، بديل) مع
 * طبقة "نُقل إلى" برتقالية فوق الحالة العادية وtooltip للحالات الخاصة.
 *
 * عند توفر unavailability_id على الخانة المنقولة نلفّها بـPopover يعرض
 * الموقع البديل وزر "تم الاطلاع" — يستدعي onAcknowledgeRelocation الذي
 * يحدّث شارة الإشعارات في الصفحة الأم.
 */
import React from 'react';
import { AlertTriangle, Repeat, CheckCheck, MapPin, Check } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import { Button } from '../ui/button';

export default function FilledCell({ cell, onClick, onAcknowledgeRelocation }) {
  // ── علم نقل الفصل ──────────────────────────────────────────────────────
  // الإدارة وسمَت فصل هذه الحصة بأنه غير متوفر وحدّدت موقعاً بديلاً.
  // نُلوّن الخانة العادية بصبغة تحذير برتقالية ونعرض نص "نُقل إلى: …".
  // للحالات الخاصة (شاغرة/مُستبدلة/بديل) نُبقي على لونها الأصلي ونكتفي
  // بإلحاق التلميح في الـtooltip حتى لا نخفي معلومة الاستبدال أو الشغور.
  const relocated = !!cell?.is_relocated && !!cell?.alternative_location;
  const relocationTip = relocated ? `نُقل إلى: ${cell.alternative_location}` : '';
  // معلومات تأكيد الاستلام: نعرض زر "تم الاطلاع" للمستلمين فقط، ونُبدّله إلى
  // حالة "تم الاطلاع" بلون أخضر بعد النقر — متوافق مع نمط استلام التعاميم.
  const canAck = relocated && !!cell?.unavailability_id && !!cell?.viewer_is_recipient;
  const alreadyAcked = !!cell?.acknowledged_by_viewer;

  // cell.is_vacant => حصة شاغرة (معلمها غائب) — تفتح نافذة المرشحين عند الضغط
  if (cell?.is_vacant) {
    const baseTitle = 'اضغط لاختيار بديل من جدول الانتظار';
    return (
      <button
        type="button"
        onClick={onClick}
        title={relocated ? `${baseTitle} • ${relocationTip}` : baseTitle}
        className="w-full h-full flex flex-col items-center justify-center text-[10px] font-semibold leading-tight px-1
                   bg-red-50 hover:bg-red-100 text-red-600 transition-colors"
      >
        <span className="font-bold">شاغرة</span>
        <span className="text-[9px] opacity-75 truncate max-w-full">{cell.class_name}</span>
      </button>
    );
  }
  // cell.is_substituted => الخانة الأصلية للمعلم الغائب بعد إسناد بديل
  if (cell?.is_substituted) {
    const subTitle = `بديل: ${cell.substitute_teacher_name || ''}`;
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-emerald-50/70 text-emerald-700"
        title={relocated ? `${subTitle} • ${relocationTip}` : subTitle}
      >
        <span className="font-semibold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          بديل: {cell.substitute_teacher_name || '—'}
        </span>
      </div>
    );
  }
  // cell.is_substitute => الخانة المضافة لصف المعلم البديل
  if (cell?.is_substitute) {
    const subTitle = `بديل عن ${cell.original_teacher_name || ''}`;
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-violet-50/70 text-violet-700 relative"
        title={relocated ? `${subTitle} • ${relocationTip}` : subTitle}
      >
        <Repeat className="absolute top-0.5 right-0.5 h-2.5 w-2.5 opacity-60" />
        <span className="font-semibold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          {cell.subject_name || ''}
        </span>
      </div>
    );
  }
  // الخانة العادية — هنا نطبّق صبغة "نُقل إلى" بشكل واضح إذا وُجدت.
  // عند توفر unavailability_id نلفّ الخلية بـPopover يعرض الموقع البديل
  // وزر "تم الاطلاع" الذي يستدعي endpoint التأكيد ويحدِّث شارة الإشعارات.
  if (relocated) {
    const cellBody = (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-orange-50 hover:bg-orange-100 text-orange-700 relative cursor-pointer"
        title={`${cell?.subject_name ? cell.subject_name + ' • ' : ''}${relocationTip}`}
        data-testid="cell-relocated"
      >
        <AlertTriangle className="absolute top-0.5 right-0.5 h-2.5 w-2.5 text-orange-500" />
        {alreadyAcked && (
          <CheckCheck className="absolute top-0.5 left-0.5 h-2.5 w-2.5 text-emerald-600" />
        )}
        <span className="font-semibold truncate max-w-full">{cell?.class_name || '—'}</span>
        <span className="text-[9px] font-semibold truncate max-w-full">
          نُقل إلى: {cell.alternative_location}
        </span>
      </div>
    );
    if (!cell?.unavailability_id) {
      return cellBody;
    }
    return (
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="w-full h-full p-0 m-0 bg-transparent border-0"
            data-testid="cell-relocated-trigger"
          >
            {cellBody}
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="center"
          side="bottom"
          className="w-64 text-right"
          dir="rtl"
          data-testid="cell-relocated-popover"
        >
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-orange-700">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-bold font-cairo">تم نقل الفصل</span>
            </div>
            <div className="text-xs text-slate-600">
              <span className="font-semibold">{cell?.class_name || '—'}</span>
              {cell?.subject_name ? <span> • {cell.subject_name}</span> : null}
            </div>
            <div className="flex items-start gap-1.5 text-sm bg-orange-50 border border-orange-200 rounded-md px-2 py-1.5">
              <MapPin className="h-3.5 w-3.5 text-orange-600 mt-0.5 shrink-0" />
              <div>
                <div className="text-[11px] text-orange-600">الموقع البديل</div>
                <div className="font-semibold text-orange-800">{cell.alternative_location}</div>
              </div>
            </div>
            {canAck ? (
              <Button
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!alreadyAcked && onAcknowledgeRelocation) {
                    onAcknowledgeRelocation(cell);
                  }
                }}
                disabled={alreadyAcked}
                className={`w-full h-8 gap-1.5 ${alreadyAcked
                  ? 'bg-emerald-600 hover:bg-emerald-600 text-white'
                  : 'bg-orange-600 hover:bg-orange-700 text-white'}`}
                data-testid="cell-relocation-ack"
              >
                {alreadyAcked ? (
                  <>
                    <CheckCheck className="h-3.5 w-3.5" />
                    تم الاطلاع
                  </>
                ) : (
                  <>
                    <Check className="h-3.5 w-3.5" />
                    تم الاطلاع
                  </>
                )}
              </Button>
            ) : (
              <p className="text-[11px] text-slate-500">
                {alreadyAcked
                  ? 'لقد سجّلت اطلاعك على هذا النقل سابقاً.'
                  : 'هذا الإشعار لمعلومات الجدول فقط.'}
              </p>
            )}
          </div>
        </PopoverContent>
      </Popover>
    );
  }
  return (
    <div
      className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1 text-blue-600/80"
      title={cell?.subject_name || ''}
    >
      <span className="font-semibold">{cell?.class_name || '—'}</span>
      {cell?.subject_name && (
        <span className="text-[9px] text-slate-400 truncate max-w-full">{cell.subject_name}</span>
      )}
    </div>
  );
}
