import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Award, Plus, Upload, X, User, GraduationCap, Building } from 'lucide-react';
import { toast } from 'sonner';

const TYPE_OPTIONS = [
  { id: 'academic', label: 'أكاديمي' },
  { id: 'sports', label: 'رياضي' },
  { id: 'arts', label: 'فني' },
  { id: 'behavior', label: 'سلوكي' },
  { id: 'other', label: 'أخرى' },
];

const SOURCE_CONFIG = {
  parent: { label: 'ولي الأمر', icon: User, color: 'bg-indigo-100 text-indigo-700' },
  teacher: { label: 'المعلم', icon: GraduationCap, color: 'bg-emerald-100 text-emerald-700' },
  admin: { label: 'الإدارة', icon: Building, color: 'bg-purple-100 text-purple-700' },
};

const AchievementsArchive = ({ childId }) => {
  const { api } = useAuth();
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [type, setType] = useState('academic');
  const [fileUrl, setFileUrl] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchAchievements = async () => {
    try {
      const res = await api.get(`/parent-portal/child/${childId}/achievements`);
      setAchievements(res.data?.achievements || []);
    } catch {
      setAchievements([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAchievements();
  }, [childId]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error('يرجى إدخال اسم الإنجاز');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/parent-portal/child/${childId}/achievements`, {
        name: name.trim(),
        type,
        file_url: fileUrl,
      });
      toast.success('تم إضافة الإنجاز بنجاح');
      setName('');
      setType('academic');
      setFileUrl('');
      setShowForm(false);
      fetchAchievements();
    } catch {
      toast.error('حدث خطأ أثناء الحفظ');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Award className="w-5 h-5 text-amber-600" />
          <h3 className="text-base font-bold text-gray-800">إنجازاتي</h3>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
        >
          {showForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          {showForm ? 'إلغاء' : 'إضافة إنجاز'}
        </button>
      </div>

      {showForm && (
        <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-3">
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="اسم الإنجاز"
            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <div className="flex flex-wrap gap-2">
            {TYPE_OPTIONS.map(opt => (
              <button
                key={opt.id}
                onClick={() => setType(opt.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  type === opt.id
                    ? 'bg-indigo-100 text-indigo-700 border border-indigo-300'
                    : 'bg-white text-gray-600 border border-gray-200 hover:border-indigo-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <input
            type="text"
            value={fileUrl}
            onChange={e => setFileUrl(e.target.value)}
            placeholder="رابط الملف المرفق (اختياري)"
            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            <Upload className="w-4 h-4" />
            {saving ? 'جارٍ الحفظ...' : 'حفظ الإنجاز'}
          </button>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : achievements.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <Award className="w-10 h-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">لا توجد إنجازات مسجلة بعد</p>
        </div>
      ) : (
        <div className="space-y-2">
          {achievements.map((ach, i) => {
            const sourceConf = SOURCE_CONFIG[ach.source] || SOURCE_CONFIG.parent;
            const SourceIcon = sourceConf.icon;
            return (
              <div key={ach.id || i} className="flex items-center gap-3 p-3 rounded-xl bg-white border border-gray-100 hover:border-indigo-100 transition-colors">
                <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                  <Award className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{ach.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${sourceConf.color}`}>
                      <SourceIcon className="w-3 h-3" />
                      {sourceConf.label}
                    </span>
                    <span className="text-xs text-gray-400">{ach.type}</span>
                  </div>
                </div>
                {ach.file_url && (
                  <a href={ach.file_url} target="_blank" rel="noreferrer" className="text-indigo-600 text-xs hover:underline">عرض</a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AchievementsArchive;
