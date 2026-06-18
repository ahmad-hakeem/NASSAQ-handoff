import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { AlertTriangle, User, X, Check, Loader2, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { getApiErrorMessage } from '../utils/apiError';

const GENERIC_NAMES_AR = new Set([
  'مدير المنصة', 'مدير المنصة الرئيسي', 'مدير مدرسة', 'مدير النظام', 'مدير',
  'معلم', 'طالب', 'ولي أمر', 'ولي الأمر', 'مستخدم', 'مستخدم جديد',
  'مستخدم تجريبي', 'موقع', 'ناظر', 'وكيل', 'مشرف', 'مشرف عام',
  'إدارة', 'حساب تجريبي', 'حساب اختبار', 'حساب جديد', 'مسؤول',
  'مسؤول النظام', 'موظف', 'فني', 'دعم فني', 'خدمة العملاء',
]);

const GENERIC_NAMES_EN = new Set([
  'platform admin', 'school admin', 'admin', 'administrator', 'teacher',
  'student', 'parent', 'user', 'new user', 'test user', 'test', 'demo',
  'demo user', 'website', 'manager', 'principal', 'super admin',
  'system admin', 'system', 'support', 'technical support', 'operations',
  'operations manager', 'staff', 'employee', 'account', 'default',
  'nassaq', 'nassaq admin', 'school manager',
]);

const GENERIC_PATTERNS = [
  /^user\s*\d*$/i,
  /^admin\s*\d*$/i,
  /^test\s*\d*$/i,
  /^demo\s*\d*$/i,
  /^مستخدم\s*\d*$/,
  /^مدير\s*\d*$/,
  /^حساب\s*\d*$/,
];

export function isGenericName(name) {
  if (!name || !name.trim()) return true;
  const cleaned = name.trim();
  if (cleaned.length < 3) return true;
  const lower = cleaned.toLowerCase();
  if (GENERIC_NAMES_EN.has(lower)) return true;
  if (GENERIC_NAMES_AR.has(cleaned)) return true;
  for (const p of GENERIC_PATTERNS) {
    if (p.test(lower)) return true;
  }
  if (/^[\d\s]+$/.test(cleaned)) return true;
  if (/^(.)\1+$/.test(cleaned)) return true;
  return false;
}

// Mirror of the backend `_FORMULA_INJECTION_CHARS` rule in
// engines/name_validation.py — a real personal name never begins with a
// spreadsheet-formula metacharacter. Mirroring it here gives instant inline
// feedback instead of a server round-trip, but the backend remains the
// single source of truth (it re-validates on every save).
const FORMULA_INJECTION_CHARS = new Set(['=', '+', '-', '@', '\t', '\r']);

function validateNewName(name) {
  if (!name || !name.trim()) return 'الاسم الشخصي مطلوب';
  const cleaned = name.trim();
  if (cleaned.length < 3) return 'الاسم قصير جداً — يجب أن يكون 3 أحرف على الأقل';
  if (FORMULA_INJECTION_CHARS.has(cleaned[0])) return 'الاسم يحتوي على رمز غير مسموح به';
  if (isGenericName(cleaned)) return 'يجب استخدام اسمك الشخصي الحقيقي بدلاً من اسم عام أو وظيفي';
  if (/^[\d\s]+$/.test(cleaned)) return 'الاسم يجب أن يحتوي على أحرف';
  return '';
}

function NameUpdateModal({ currentName, onClose, onSuccess }) {
  const { api } = useAuth();
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

  const handleSave = async () => {
    const err = validateNewName(name);
    if (err) { setError(err); return; }
    setSaving(true);
    setError('');
    try {
      // Use the app's configured `api` client (from AuthContext) rather than a
      // raw axios call: it attaches the bearer token, refreshes-and-retries on
      // an expired access token (401), retries transient blips, and normalizes
      // the backend `{success:false,error:{message}}` envelope so a clear Arabic
      // reason is surfaced inline. The raw call bypassed all of this, which made
      // a save after the token aged out fail silently with a generic error.
      await api.put('/users/me/profile', { full_name: name.trim() });
      toast.success('تم تحديث اسمك بنجاح');
      onSuccess(name.trim());
    } catch (e) {
      const detail = getApiErrorMessage(e);
      setError(typeof detail === 'string' ? detail : 'فشل في حفظ الاسم — حاول مرة أخرى');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); handleSave(); }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm" dir="rtl">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-300">
        <div className="bg-gradient-to-l from-amber-500 to-orange-500 p-5 text-white">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/20 rounded-xl">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold">تحديث اسم الحساب مطلوب</h2>
              <p className="text-sm text-white/80">يجب تحديث اسمك الشخصي قبل المتابعة</p>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3.5">
            <p className="text-sm text-amber-800 leading-relaxed">
              حسابك يستخدم الاسم <span className="font-bold text-amber-900">"{currentName}"</span> وهو اسم عام/وظيفي.
              يجب تحديثه ليكون اسمك الشخصي الحقيقي لتحسين الوضوح والمساءلة داخل النظام.
            </p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
              الاسم الشخصي الحقيقي
            </label>
            <Input
              ref={inputRef}
              value={name}
              onChange={(e) => { setName(e.target.value); setError(''); }}
              onKeyDown={handleKeyDown}
              placeholder="مثال: أحمد زلط، Sarah Ali"
              className="text-right h-11 text-base"
              dir="rtl"
            />
            {error && (
              <p className="text-xs text-red-500 mt-1.5 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                {error}
              </p>
            )}
          </div>

          <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
            <p className="text-[11px] text-slate-500 font-medium mb-1.5">أمثلة على أسماء مقبولة:</p>
            <div className="flex flex-wrap gap-1.5">
              {['أحمد زلط', 'Ahmed Hakim', 'سارة علي', 'Mohammed Hassan'].map(ex => (
                <span key={ex} className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">{ex}</span>
              ))}
            </div>
            <p className="text-[11px] text-slate-500 font-medium mt-2 mb-1.5">أمثلة على أسماء مرفوضة:</p>
            <div className="flex flex-wrap gap-1.5">
              {['Platform Admin', 'مدير المنصة', 'Teacher', 'Student'].map(ex => (
                <span key={ex} className="text-[10px] px-2 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200 line-through">{ex}</span>
              ))}
            </div>
          </div>

          <Button
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="w-full h-11 bg-brand-navy hover:bg-brand-navy/90 text-white font-semibold rounded-xl gap-2"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            تحديث اسمي الآن
          </Button>
        </div>
      </div>
    </div>
  );
}

function NameWarningBanner({ currentName, onOpenModal }) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div className="sticky top-0 z-[100] bg-gradient-to-l from-amber-500 to-orange-500 text-white shadow-lg" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <p className="text-sm font-medium truncate">
            <span className="hidden sm:inline">يجب تحديث اسم حسابك ليكون اسمك الشخصي الحقيقي بدلاً من </span>
            <span className="sm:hidden">حدّث اسمك بدلاً من </span>
            <span className="font-bold">"{currentName}"</span>
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            onClick={onOpenModal}
            size="sm"
            className="bg-white text-amber-700 hover:bg-white/90 font-semibold text-xs h-7 px-3 rounded-lg gap-1"
          >
            <User className="h-3 w-3" />
            تحديث اسمي
          </Button>
          <button
            onClick={() => setDismissed(true)}
            className="p-1 rounded hover:bg-white/20 transition-colors"
            title="إخفاء مؤقتاً"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function GenericNameGuard({ children }) {
  const { user, refreshUser, updateUser } = useAuth();
  const location = useLocation();
  const [showModal, setShowModal] = useState(false);
  const [hasShownModal, setHasShownModal] = useState(false);

  const hasGeneric = user?.has_generic_name === true;

  const isExemptPage = ['/login', '/register', '/change-password', '/', '/registration-confirmation'].some(
    p => location.pathname === p || location.pathname.startsWith('/register')
  );

  useEffect(() => {
    if (hasGeneric && !hasShownModal && !isExemptPage) {
      const timer = setTimeout(() => {
        setShowModal(true);
        setHasShownModal(true);
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [hasGeneric, hasShownModal, isExemptPage]);

  const handleSuccess = async (newName) => {
    setShowModal(false);
    updateUser({ full_name: newName, has_generic_name: false });
    await refreshUser();
  };

  if (!user || isExemptPage) return children;

  return (
    <>
      {hasGeneric && <NameWarningBanner currentName={user.full_name} onOpenModal={() => setShowModal(true)} />}
      {showModal && (
        <NameUpdateModal
          currentName={user.full_name}
          onClose={() => setShowModal(false)}
          onSuccess={handleSuccess}
        />
      )}
      {children}
    </>
  );
}
