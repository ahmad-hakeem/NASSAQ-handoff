import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Save, X, Heart, Eye, Wind, ShieldAlert, Zap, Target } from 'lucide-react';
import { toast } from 'sonner';

const EMOJI_OPTIONS = ['👦', '👧', '🧒', '👨‍🎓', '👩‍🎓', '🦸‍♂️', '🦸‍♀️', '🧑‍💻', '🎨', '⚽', '🎵', '📚', '🌟', '🦋', '🚀', '🎯'];

const HEALTH_CONDITIONS = [
  { id: 'asthma', label: 'الربو', icon: Wind },
  { id: 'weak_vision', label: 'ضعف النظر', icon: Eye },
  { id: 'allergy', label: 'الحساسية', icon: ShieldAlert },
  { id: 'heart', label: 'مشاكل القلب', icon: Heart },
];

const BEHAVIORAL_ASPECTS = [
  { id: 'shyness', label: 'الخجل', icon: '🙈' },
  { id: 'hyperactivity', label: 'فرط الحركة', icon: '⚡' },
  { id: 'concentration_difficulty', label: 'صعوبة التركيز', icon: '🎯' },
];

const FAMILY_OPTIONS = [
  { id: 'both_parents', label: 'مع الوالدين' },
  { id: 'father_only', label: 'مع الأب فقط' },
  { id: 'mother_only', label: 'مع الأم فقط' },
  { id: 'other', label: 'طرف آخر' },
];

const ProfileEditor = ({ profile, childId, onSave, onCancel }) => {
  const { api } = useAuth();
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
      toast.success('تم حفظ التعديلات بنجاح');
      onSave?.();
    } catch {
      toast.error('حدث خطأ أثناء الحفظ');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">الرمز التعبيري</p>
        <div className="flex flex-wrap gap-2">
          {EMOJI_OPTIONS.map(e => (
            <button
              key={e}
              onClick={() => setEmoji(e)}
              className={`w-10 h-10 rounded-xl text-xl flex items-center justify-center transition-all ${
                emoji === e ? 'bg-indigo-100 ring-2 ring-indigo-500 scale-110' : 'bg-gray-50 hover:bg-gray-100'
              }`}
            >
              {e}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">المشاكل الصحية</p>
        <div className="grid grid-cols-2 gap-2">
          {HEALTH_CONDITIONS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => toggleArrayItem(healthConditions, setHealthConditions, id)}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm transition-all ${
                healthConditions.includes(id)
                  ? 'bg-red-50 text-red-700 border-2 border-red-300'
                  : 'bg-gray-50 text-gray-600 border-2 border-transparent hover:border-gray-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 mb-1">سلوك يحتاج تحسين</p>
        <p className="text-xs text-gray-400 mb-2">اختياري — يساعد المعلم على فهم الطالب أكثر</p>
        <div className="grid grid-cols-1 gap-2">
          {BEHAVIORAL_ASPECTS.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => toggleArrayItem(behavioralAspects, setBehavioralAspects, id)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                behavioralAspects.includes(id)
                  ? 'bg-amber-50 text-amber-700 border-2 border-amber-300'
                  : 'bg-gray-50 text-gray-600 border-2 border-transparent hover:border-gray-200'
              }`}
            >
              <span className="text-lg">{icon}</span>
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 mb-1">الوضع العائلي</p>
        <p className="text-xs text-gray-400 mb-2">اختياري — هل يعيش الطفل مع الوالدين؟</p>
        <div className="grid grid-cols-2 gap-2">
          {FAMILY_OPTIONS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setFamilySituation(id)}
              className={`px-3 py-2.5 rounded-xl text-sm transition-all ${
                familySituation === id
                  ? 'bg-indigo-50 text-indigo-700 border-2 border-indigo-300'
                  : 'bg-gray-50 text-gray-600 border-2 border-transparent hover:border-gray-200'
              }`}
            >
              {label}
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
          {saving ? 'جارٍ الحفظ...' : 'حفظ التعديلات'}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2.5 rounded-xl border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default ProfileEditor;
