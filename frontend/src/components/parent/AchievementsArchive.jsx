import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Award, Plus, Upload, X, User, GraduationCap, Building, FileText, Paperclip, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const TYPE_OPTIONS = [
  { id: 'academic', label_ar: 'أكاديمي', label_en: 'Academic', icon: '📚' },
  { id: 'sports', label_ar: 'رياضي', label_en: 'Sports', icon: '⚽' },
  { id: 'arts', label_ar: 'فني', label_en: 'Arts', icon: '🎨' },
  { id: 'behavior', label_ar: 'سلوكي', label_en: 'Behavior', icon: '⭐' },
  { id: 'other', label_ar: 'أخرى', label_en: 'Other', icon: '📌' },
];

const SOURCE_CONFIG = {
  parent: { label_ar: 'ولي الأمر', label_en: 'Parent', icon: User, color: 'bg-indigo-100 text-indigo-700' },
  teacher: { label_ar: 'المعلم', label_en: 'Teacher', icon: GraduationCap, color: 'bg-emerald-100 text-emerald-700' },
  admin: { label_ar: 'الإدارة', label_en: 'Admin', icon: Building, color: 'bg-purple-100 text-purple-700' },
};

const AchievementsArchive = ({ childId }) => {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [type, setType] = useState('academic');
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const fileInputRef = useRef(null);

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

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.size > 5 * 1024 * 1024) {
        toast.error(isRTL ? 'حجم الملف يجب أن يكون أقل من 5 ميجابايت' : 'File size must be less than 5MB');
        return;
      }
      setFile(selectedFile);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error(isRTL ? 'يرجى إدخال اسم الإنجاز' : 'Please enter achievement name');
      return;
    }
    setSaving(true);
    try {
      if (file) {
        const formData = new FormData();
        formData.append('name', name.trim());
        formData.append('type', type);
        formData.append('file', file);
        await api.post(`/parent-portal/child/${childId}/achievements/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } else {
        await api.post(`/parent-portal/child/${childId}/achievements`, {
          name: name.trim(),
          type,
        });
      }
      toast.success(isRTL ? 'تم إضافة الإنجاز بنجاح' : 'Achievement added successfully');
      setName('');
      setType('academic');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setShowForm(false);
      fetchAchievements();
    } catch {
      toast.error(isRTL ? 'حدث خطأ أثناء الحفظ' : 'Error saving achievement');
    } finally {
      setSaving(false);
    }
  };

  const getTypeLabel = (typeId) => {
    const opt = TYPE_OPTIONS.find(o => o.id === typeId);
    if (!opt) return typeId;
    return `${opt.icon} ${isRTL ? opt.label_ar : opt.label_en}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Award className="w-5 h-5 text-amber-600" />
          <h3 className="text-base font-bold text-gray-800 dark:text-gray-200">
            {isRTL ? 'إنجازاتي' : 'My Achievements'}
          </h3>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
        >
          {showForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
          {showForm ? (isRTL ? 'إلغاء' : 'Cancel') : (isRTL ? 'إضافة إنجاز' : 'Add Achievement')}
        </button>
      </div>

      {showForm && (
        <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 space-y-3">
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={isRTL ? 'اسم الإنجاز' : 'Achievement name'}
            className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <div className="flex flex-wrap gap-2">
            {TYPE_OPTIONS.map(opt => (
              <button
                key={opt.id}
                onClick={() => setType(opt.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  type === opt.id
                    ? 'bg-indigo-100 text-indigo-700 border border-indigo-300 dark:bg-indigo-900/40 dark:text-indigo-300 dark:border-indigo-600'
                    : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-600 hover:border-indigo-200'
                }`}
              >
                <span>{opt.icon}</span>
                {isRTL ? opt.label_ar : opt.label_en}
              </button>
            ))}
          </div>

          <div
            onClick={() => fileInputRef.current?.click()}
            className={`flex items-center gap-3 px-3 py-3 rounded-lg border-2 border-dashed cursor-pointer transition-all ${
              file
                ? 'border-indigo-300 bg-indigo-50 dark:bg-indigo-900/20 dark:border-indigo-600'
                : 'border-gray-200 dark:border-gray-600 hover:border-indigo-200 bg-white dark:bg-gray-900'
            }`}
          >
            {file ? (
              <>
                <FileText className="w-5 h-5 text-indigo-600" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-indigo-700 dark:text-indigo-300 truncate">{file.name}</p>
                  <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setFile(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}
                  className="p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"
                >
                  <X className="w-3.5 h-3.5 text-gray-500" />
                </button>
              </>
            ) : (
              <>
                <Paperclip className="w-5 h-5 text-gray-400" />
                <p className="text-sm text-gray-400">
                  {isRTL ? 'إرفاق ملف (اختياري) — أقل من 5 ميجابايت' : 'Attach file (optional) — under 5MB'}
                </p>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              accept="image/*,.pdf,.doc,.docx"
              className="hidden"
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={saving}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {saving ? (isRTL ? 'جارٍ الحفظ...' : 'Saving...') : (isRTL ? 'حفظ الإنجاز' : 'Save Achievement')}
          </button>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : achievements.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <Award className="w-10 h-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">{isRTL ? 'لا توجد إنجازات مسجلة بعد' : 'No achievements recorded yet'}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {achievements.map((ach, i) => {
            const sourceConf = SOURCE_CONFIG[ach.source] || SOURCE_CONFIG.parent;
            const SourceIcon = sourceConf.icon;
            const hasFile = ach.file_data || ach.file_url;
            return (
              <div key={ach.id || i} className="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 hover:border-indigo-100 dark:hover:border-indigo-800 transition-colors">
                <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-900/30 text-amber-600 flex items-center justify-center flex-shrink-0">
                  <Award className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{ach.name}</p>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] ${sourceConf.color}`}>
                      <SourceIcon className="w-3 h-3" />
                      {isRTL ? sourceConf.label_ar : sourceConf.label_en}
                    </span>
                    <span className="text-[10px] text-gray-400">{getTypeLabel(ach.type)}</span>
                    {ach.file_name && (
                      <span className="inline-flex items-center gap-0.5 text-[10px] text-gray-400">
                        <Paperclip className="w-2.5 h-2.5" />
                        {ach.file_name}
                      </span>
                    )}
                  </div>
                </div>
                {hasFile && (
                  <a
                    href={ach.file_data || ach.file_url}
                    target="_blank"
                    rel="noreferrer"
                    download={ach.file_name || undefined}
                    className="text-indigo-600 dark:text-indigo-400 text-xs hover:underline flex-shrink-0"
                  >
                    {isRTL ? 'عرض' : 'View'}
                  </a>
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
