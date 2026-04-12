import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import {
  Award, Star, TrendingUp, TrendingDown, BookOpen, Lightbulb,
  FileText, AlertCircle, RefreshCw, Calendar, Sparkles, GraduationCap
} from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

const WeeklyStory = ({ data, loading, error, onRetry }) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 animate-pulse">
        <div className="h-5 bg-gray-200 rounded w-32 mb-4" />
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="h-20 bg-gray-100 rounded-xl" />
          <div className="h-20 bg-gray-100 rounded-xl" />
        </div>
        <div className="h-40 bg-gray-100 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-red-100 text-center py-8">
        <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
        <p className="text-gray-700 text-sm font-medium mb-1">{t('failedToLoadWeeklyStory')}</p>
        <p className="text-gray-400 text-xs mb-3">{t('checkConnectionAndRetry')}</p>
        {onRetry && (
          <button onClick={onRetry} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" />
            {t('retry')}
          </button>
        )}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 text-center py-10">
        <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 text-sm font-medium">{t('noWeeklyDataYet')}</p>
        <p className="text-gray-400 text-xs mt-1">{t('weeklyStoryWillAppearWhenDataAvailable')}</p>
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
    week_start,
    week_end,
  } = data;

  const formatDateShort = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('ar-SA', { month: 'short', day: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const hasActivityData = participation_count > 0 || positive_behaviors > 0;
  const hasSubjectData = (strong_subjects?.length > 0) || (weak_subjects?.length > 0);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 p-4 border-b border-purple-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-purple-100 text-purple-600 flex items-center justify-center">
              <BookOpen className="w-4.5 h-4.5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-gray-800">{t('weeklyStory')}</h3>
              {(week_start || week_end) && (
                <p className="text-[10px] text-gray-400 mt-0.5 flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDateShort(week_start)} — {formatDateShort(week_end)}
                </p>
              )}
            </div>
          </div>
          <span className="text-[10px] text-purple-500 bg-purple-100 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
            <RefreshCw className="w-2.5 h-2.5" />
            {t('weeklyRefresh')}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <StatBadge
            icon={Star}
            label={t('classParticipation')}
            value={participation_count}
            color="indigo"
          />
          <StatBadge
            icon={Award}
            label={t('positiveBehavior')}
            value={positive_behaviors}
            color="emerald"
          />
        </div>

        {acquired_skills?.length > 0 && (
          <div>
            <SectionLabel icon={Sparkles} label={t('acquiredSkills')} />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {acquired_skills.map((skill, i) => (
                <span key={i} className="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-medium border border-blue-100">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {hasSubjectData && (
          <div className="grid grid-cols-2 gap-3">
            {strong_subjects?.length > 0 && (
              <div>
                <SectionLabel icon={TrendingUp} label={t('excelledIn')} color="emerald" />
                <div className="space-y-1.5 mt-2">
                  {strong_subjects.map((s, i) => (
                    <div key={i} className="flex items-center justify-between px-2.5 py-2 rounded-lg bg-emerald-50 border border-emerald-100">
                      <div className="flex items-center gap-1.5 text-emerald-700 text-xs font-medium">
                        <GraduationCap className="w-3 h-3" />
                        {s.subject}
                      </div>
                      <span className="text-[10px] font-bold text-emerald-600">{s.average}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {weak_subjects?.length > 0 && (
              <div>
                <SectionLabel icon={TrendingDown} label={t('needsImprovement')} color="amber" />
                <div className="space-y-1.5 mt-2">
                  {weak_subjects.map((s, i) => (
                    <div key={i} className="flex items-center justify-between px-2.5 py-2 rounded-lg bg-amber-50 border border-amber-100">
                      <div className="flex items-center gap-1.5 text-amber-700 text-xs font-medium">
                        <Lightbulb className="w-3 h-3" />
                        {s.subject}
                      </div>
                      <span className="text-[10px] font-bold text-amber-600">{s.average}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {remedial_plans?.length > 0 && (
          <div>
            <SectionLabel icon={FileText} label={t('teacherRemedialPlans')} color="orange" />
            <div className="space-y-2 mt-2">
              {remedial_plans.map((plan, i) => (
                <div key={plan.id || i} className="p-3 rounded-xl bg-orange-50 border border-orange-100">
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="w-3.5 h-3.5 text-orange-600 shrink-0" />
                    <span className="text-xs font-bold text-orange-800">{plan.title}</span>
                  </div>
                  {plan.description && (
                    <p className="text-xs text-orange-700 ms-5 leading-relaxed">{plan.description}</p>
                  )}
                  {(plan.subject || plan.teacher_name) && (
                    <div className="flex items-center gap-3 ms-5 mt-1.5">
                      {plan.subject && (
                        <span className="text-[10px] text-orange-500 bg-orange-100 px-2 py-0.5 rounded-full">
                          {plan.subject}
                        </span>
                      )}
                      {plan.teacher_name && (
                        <span className="text-[10px] text-orange-500">
                          {t('theTeacher')}: {plan.teacher_name}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {daily_chart_data?.length > 0 && hasActivityData && (
          <div>
            <SectionLabel icon={Star} label={t('dailyActivity')} />
            <div className="h-48 w-full mt-2" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={daily_chart_data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} width={25} />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      direction: 'rtl',
                      borderRadius: '12px',
                      border: 'none',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, direction: 'rtl' }} />
                  <Bar dataKey="participation" name={t('classParticipation')} fill="#6366f1" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="positive_behavior" name={t('positiveBehavior')} fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {daily_chart_data?.length > 0 && hasActivityData && (
          <div className="flex items-center gap-4 justify-center">
            <ActivityDot color="bg-indigo-500" label={t('classParticipation')} />
            <ActivityDot color="bg-emerald-500" label={t('positiveBehavior')} />
            {daily_chart_data.some(d => d.participation > 3) && (
              <ActivityDot color="bg-purple-500" label={t('highActivity')} />
            )}
          </div>
        )}

        {weekly_tip && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100">
            <div className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
              <Lightbulb className="w-4.5 h-4.5" />
            </div>
            <div>
              <p className="text-xs font-bold text-indigo-800 mb-1">{t('weeklyTip')}</p>
              <p className="text-sm text-indigo-700 leading-relaxed">{weekly_tip}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const SectionLabel = ({ icon: Icon, label, color = 'gray' }) => {
  const colorMap = {
    gray: 'text-gray-500',
    emerald: 'text-emerald-600',
    amber: 'text-amber-600',
    orange: 'text-orange-600',
  };
  return (
    <div className={`flex items-center gap-1.5 text-xs font-semibold ${colorMap[color] || colorMap.gray}`}>
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
};

const StatBadge = ({ icon: Icon, label, value, color }) => {
  const colorClasses = {
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-100',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  };

  return (
    <div className={`flex items-center gap-3 p-3.5 rounded-xl border ${colorClasses[color] || colorClasses.indigo}`}>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
        color === 'emerald' ? 'bg-emerald-100' : 'bg-indigo-100'
      }`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xl font-bold">{value || 0}</p>
        <p className="text-[11px] opacity-80">{label}</p>
      </div>
    </div>
  );
};

const ActivityDot = ({ color, label }) => (
  <div className="flex items-center gap-1.5">
    <div className={`w-2 h-2 rounded-full ${color}`} />
    <span className="text-[10px] text-gray-500">{label}</span>
  </div>
);

export default WeeklyStory;
