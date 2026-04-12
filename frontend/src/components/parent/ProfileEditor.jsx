import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Save, X, Heart, Eye, Wind, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';

const EMOJI_OPTIONS = ['👦', '👧', '🧒', '👨‍🎓', '👩‍🎓', '🦸‍♂️', '🦸‍♀️', '🧑‍💻', '🎨', '⚽', '🎵', '📚', '🌟', '🦋', '🚀', '🎯'];

const HEALTH_CONDITIONS = [
  { id: 'asthma', label_ar: 'الربو', label_en: 'Asthma', icon: Wind, color: 'bg-red-50 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700' },
  { id: 'weak_vision', label_ar: 'ضعف النظر', label_en: 'Weak Vision', icon: Eye, color: 'bg-blue-50 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700' },
  { id: 'allergy', label_ar: 'الحساسية', label_en: 'Allergies', icon: ShieldAlert, color: 'bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700' },
  { id: 'heart', label_ar: 'مشاكل القلب', label_en: 'Heart Issues', icon: Heart, color: 'bg-pink-50 text-pink-700 border-pink-300 dark:bg-pink-900/30 dark:text-pink-300 dark:border-pink-700' },
];

const BEHAVIORAL_ASPECTS = [
  { id: 'shyness', label_ar: 'الخجل', label_en: 'Shyness', icon: '🙈' },
  { id: 'hyperactivity', label_ar: 'فرط الحركة', label_en: 'Hyperactivity', icon: '⚡' },
  { id: 'concentration_difficulty', label_ar: 'صعوبة التركيز', label_en: 'Difficulty Concentrating', icon: '🎯' },
];

const FAMILY_OPTIONS = [
  { id: 'both_parents', label_ar: 'مع الوالدين', label_en: 'Both Parents' },
  { id: 'father_only', label_ar: 'مع الأب فقط', label_en: 'Father Only' },
  { id: 'mother_only', label_ar: 'مع الأم فقط', label_en: 'Mother Only' },
  { id: 'other', label_ar: 'طرف آخر', label_en: 'Other' },
];

const ProfileEditor = ({ profile, childId, onSave, onCancel }) => {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const [emoji, setEmoji] = useState(profile?.emoji || '👦');
  const [healthConditions, setHealthConditions] = useState(profile?.health_conditions || []);
  const [behavioralAspects, setBehavioralAspects] = useState(profile?.behavioral_aspects || []);
  const [familySituation, setFamilySituation] = useState(profile?.family_situation || '');
  const [saving, setSaving] = useState(false);

  const toggleArrayItem = (arr, setArr, item) => {
    setArr(prev => prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/parent-portal/child/${childId}/profile`, {
        emoji,
        health_conditions: healthConditions,
        behavioral_aspects: behavioralAspects,
        family_situation: familySituation,
      });
      toast.success(isRTL ? 'تم حفظ التعديلات بنجاح' : 'Changes saved successfully');
      onSave?.();
    } catch {
      toast.error(isRTL ? 'حدث خطأ أثناء الحفظ' : 'Error saving changes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {isRTL ? 'الرمز التعبيري' : 'Emoji Avatar'}
        </p>
        <div className="flex flex-wrap gap-2">
          {EMOJI_OPTIONS.map(e => (
            <button
              key={e}
              onClick={() => setEmoji(e)}
              className={`w-10 h-10 rounded-xl text-xl flex items-center justify-center transition-all ${
                emoji === e ? 'bg-indigo-100 dark:bg-indigo-900/40 ring-2 ring-indigo-500 scale-110' : 'bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {e}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {isRTL ? 'المشاكل الصحية' : 'Health Conditions'}
        </p>
        <div className="grid grid-cols-2 gap-2">
          {HEALTH_CONDITIONS.map(({ id, label_ar, label_en, icon: Icon, color }) => (
            <button
              key={id}
              onClick={() => toggleArrayItem(healthConditions, setHealthConditions, id)}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm transition-all border-2 ${
                healthConditions.includes(id)
                  ? color
                  : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-transparent hover:border-gray-200 dark:hover:border-gray-600'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{isRTL ? label_ar : label_en}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {isRTL ? 'سلوك يحتاج تحسين' : 'Behavioral Aspects'}
        </p>
        <p className="text-xs text-gray-400 mb-2">
          {isRTL ? 'اختياري — يساعد المعلم على فهم الطالب أكثر' : 'Optional — helps the teacher understand the student better'}
        </p>
        <div className="grid grid-cols-1 gap-2">
          {BEHAVIORAL_ASPECTS.map(({ id, label_ar, label_en, icon }) => (
            <button
              key={id}
              onClick={() => toggleArrayItem(behavioralAspects, setBehavioralAspects, id)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all border-2 ${
                behavioralAspects.includes(id)
                  ? 'bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700'
                  : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-transparent hover:border-gray-200 dark:hover:border-gray-600'
              }`}
            >
              <span className="text-lg">{icon}</span>
              <span>{isRTL ? label_ar : label_en}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {isRTL ? 'الوضع العائلي' : 'Family Situation'}
        </p>
        <p className="text-xs text-gray-400 mb-2">
          {isRTL ? 'اختياري — هل يعيش الطفل مع الوالدين؟' : 'Optional — does the child live with both parents?'}
        </p>
        <div className="grid grid-cols-2 gap-2">
          {FAMILY_OPTIONS.map(({ id, label_ar, label_en }) => (
            <button
              key={id}
              onClick={() => setFamilySituation(familySituation === id ? '' : id)}
              className={`px-3 py-2.5 rounded-xl text-sm transition-all border-2 ${
                familySituation === id
                  ? 'bg-indigo-50 text-indigo-700 border-indigo-300 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-700'
                  : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-transparent hover:border-gray-200 dark:hover:border-gray-600'
              }`}
            >
              {isRTL ? label_ar : label_en}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? (isRTL ? 'جارٍ الحفظ...' : 'Saving...') : (isRTL ? 'حفظ التعديلات' : 'Save Changes')}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default ProfileEditor;
