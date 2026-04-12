import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Award, Star, TrendingUp, BookOpen, Lightbulb, FileText, AlertCircle, RefreshCw } from 'lucide-react';

const WeeklyStory = ({ data, loading, error, onRetry }) => {
  if (loading) {
    return (
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 animate-pulse">
        <div className="h-5 bg-gray-200 rounded w-32 mb-4" />
        <div className="h-40 bg-gray-100 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-red-100 text-center py-8">
        <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
        <p className="text-gray-700 text-sm font-medium mb-1">تعذر تحميل قصة الأسبوع</p>
        <p className="text-gray-400 text-xs mb-3">يرجى التحقق من الاتصال والمحاولة مرة أخرى</p>
        {onRetry && (
          <button onClick={onRetry} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" />
            إعادة المحاولة
          </button>
        )}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 text-center py-10">
        <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 text-sm font-medium">لا توجد بيانات هذا الأسبوع بعد</p>
        <p className="text-gray-400 text-xs mt-1">ستظهر قصة الأسبوع عند توفر بيانات كافية</p>
      </div>
    );
  }

  const {
    participation_count,
    positive_behaviors,
    acquired_skills,
    strong_subjects,
    weak_subjects,
    remedial_plans,
    daily_chart_data,
    weekly_tip,
  } = data;

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 space-y-5">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center">
          <BookOpen className="w-4 h-4" />
        </div>
        <h3 className="text-base font-bold text-gray-800">قصة الأسبوع</h3>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <StatBadge icon={Star} label="المشاركة" value={participation_count} color="indigo" />
        <StatBadge icon={Award} label="سلوك إيجابي" value={positive_behaviors} color="emerald" />
      </div>

      {acquired_skills?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">المهارات المكتسبة</p>
          <div className="flex flex-wrap gap-1.5">
            {acquired_skills.map((skill, i) => (
              <span key={i} className="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-medium">
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {strong_subjects?.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">تميّز في</p>
            <div className="space-y-1.5">
              {strong_subjects.map((s, i) => (
                <div key={i} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium">
                  <TrendingUp className="w-3 h-3" />
                  {s.subject}
                </div>
              ))}
            </div>
          </div>
        )}
        {weak_subjects?.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">يحتاج تحسين</p>
            <div className="space-y-1.5">
              {weak_subjects.map((s, i) => (
                <div key={i} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-50 text-amber-700 text-xs font-medium">
                  <Lightbulb className="w-3 h-3" />
                  {s.subject}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {remedial_plans?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">الخطط العلاجية</p>
          <div className="space-y-2">
            {remedial_plans.map((plan, i) => (
              <div key={plan.id || i} className="p-3 rounded-xl bg-orange-50 border border-orange-100">
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="w-3.5 h-3.5 text-orange-600" />
                  <span className="text-xs font-bold text-orange-800">{plan.title}</span>
                </div>
                {plan.description && (
                  <p className="text-xs text-orange-700 mr-5">{plan.description}</p>
                )}
                {plan.teacher_name && (
                  <p className="text-xs text-orange-500 mr-5 mt-1">المعلم: {plan.teacher_name}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {daily_chart_data?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">النشاط اليومي</p>
          <div className="h-48 w-full" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily_chart_data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={30} />
                <Tooltip contentStyle={{ fontSize: 12, direction: 'rtl' }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="participation" name="المشاركة" fill="#6366f1" radius={[4, 4, 0, 0]} />
                <Bar dataKey="positive_behavior" name="سلوك إيجابي" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {weekly_tip && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100">
          <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0 mt-0.5">
            <Lightbulb className="w-4 h-4" />
          </div>
          <div>
            <p className="text-xs font-bold text-indigo-800 mb-1">نصيحة الأسبوع</p>
            <p className="text-sm text-indigo-700">{weekly_tip}</p>
          </div>
        </div>
      )}
    </div>
  );
};

const StatBadge = ({ icon: Icon, label, value, color }) => {
  const colorClasses = {
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-100',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  };

  return (
    <div className={`flex items-center gap-3 p-3 rounded-xl border ${colorClasses[color] || colorClasses.indigo}`}>
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color === 'emerald' ? 'bg-emerald-100' : 'bg-indigo-100'}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-lg font-bold">{value || 0}</p>
        <p className="text-xs opacity-80">{label}</p>
      </div>
    </div>
  );
};

export default WeeklyStory;
