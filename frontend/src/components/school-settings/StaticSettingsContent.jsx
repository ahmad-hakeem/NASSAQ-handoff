import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  BookOpen, Layers, Award, ChevronRight, Lock,
  GraduationCap, Target, RefreshCw, CheckCircle2
} from 'lucide-react';

export function StaticSettingsContent({ hook, staticTabs }) {
  const {
    activeTab, setActiveTab,
    officialCurriculumStats, officialStages, officialTracks, officialRankLoads,
    stageCurriculums, loadingCurriculum, expandedStages, expandedTracks, expandedGrades,
    toggleStageExpand, toggleTrackExpand, toggleGradeExpand,
  } = hook;

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="w-full h-auto bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 mb-6 flex flex-row gap-0.5">
          {staticTabs.map((tab) => (
            <TabsTrigger
              key={tab.id}
              value={tab.id}
              className="flex-1 min-w-0 rounded-xl text-[10px] sm:text-xs py-2.5 px-1 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-md transition-all flex flex-col items-center gap-1 text-slate-500 hover:text-slate-700"
              data-testid={`tab-${tab.id}`}
            >
              <tab.icon className="h-3.5 w-3.5 sm:h-4 sm:w-4 flex-shrink-0" />
              <span className="truncate w-full text-center leading-tight">{tab.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="curriculum" className="space-y-6">
          <Card className="bg-white shadow-sm border-emerald-200">
            <CardHeader className="bg-emerald-50">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-500 flex items-center justify-center"><BookOpen className="h-6 w-6 text-white" /></div>
                <div>
                  <CardTitle className="text-xl text-emerald-800">المنهج الدراسي الرسمي</CardTitle>
                  <CardDescription className="text-emerald-600">بيانات وزارة التعليم السعودية</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              {officialCurriculumStats && (
                <div className="grid grid-cols-3 md:grid-cols-6 gap-4 mb-6">
                  {[
                    { label: 'مرحلة', value: officialCurriculumStats.stages, color: 'emerald' },
                    { label: 'مسار', value: officialCurriculumStats.tracks, color: 'blue' },
                    { label: 'صف', value: officialCurriculumStats.grades, color: 'violet' },
                    { label: 'مادة', value: officialCurriculumStats.subjects, color: 'amber' },
                    { label: 'توزيع', value: officialCurriculumStats.grade_subject_mappings, color: 'rose' },
                    { label: 'رتبة معلم', value: officialCurriculumStats.teacher_rank_loads, color: 'cyan' }
                  ].map((stat, idx) => (
                    <div key={idx} className={`text-center p-4 bg-${stat.color}-50 rounded-xl border border-${stat.color}-200`}>
                      <p className={`text-2xl font-bold text-${stat.color}-700`}>{stat.value}</p>
                      <p className={`text-xs text-${stat.color}-600`}>{stat.label}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="stages" className="space-y-6">
          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2"><Layers className="h-5 w-5 text-emerald-600" />المراحل الدراسية ({officialStages.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-3 gap-4">
                {officialStages.map((stage) => (
                  <div key={stage.id} className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
                    <p className="font-bold text-emerald-800">{stage.name_ar}</p>
                    <p className="text-sm text-emerald-600">{stage.name_en}</p>
                    <p className="text-xs text-emerald-500 mt-2">{stage.grades_count} صفوف</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2"><ChevronRight className="h-5 w-5 text-blue-600" />المسارات التعليمية ({officialTracks.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-4 gap-3">
                {officialTracks.map((track) => (
                  <div key={track.id} className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <p className="font-medium text-blue-800 text-sm">{track.name_ar}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rank-loads" className="space-y-6">
          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2"><Award className="h-5 w-5 text-violet-600" />النصاب الرسمي للمعلمين حسب الرتب ({officialRankLoads.length})</CardTitle>
              <CardDescription>عدد الحصص الأسبوعية المطلوبة لكل رتبة</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-4 gap-4">
                {officialRankLoads.map((rank) => (
                  <div key={rank.id} className="p-4 bg-violet-50 rounded-xl border border-violet-200 text-center">
                    <p className="font-bold text-violet-800">{rank.rank_name_ar}</p>
                    <p className="text-3xl font-bold text-violet-600 mt-2">{rank.weekly_periods}</p>
                    <p className="text-xs text-violet-500">حصة/أسبوع</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="subject-distribution" className="space-y-6">
          <Card className="bg-white shadow-sm border-rose-100">
            <CardHeader className="bg-rose-50/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-rose-500 flex items-center justify-center"><Target className="h-6 w-6 text-white" /></div>
                  <div>
                    <CardTitle className="text-xl text-rose-800">توزيع المواد الرسمي</CardTitle>
                    <CardDescription className="text-rose-600">الخطة الدراسية المعتمدة من وزارة التعليم</CardDescription>
                  </div>
                </div>
                <Badge variant="outline" className="bg-rose-100 text-rose-700 border-rose-300"><Lock className="h-3 w-3 ml-1" />للقراءة فقط</Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-200">
                {officialStages.map((stage) => (
                  <div key={stage.id} className="bg-white">
                    <button
                      onClick={() => toggleStageExpand(stage.id)}
                      className={`w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors ${expandedStages[stage.id] ? 'bg-slate-50' : ''}`}
                      data-testid={`stage-expand-${stage.id}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${expandedStages[stage.id] ? 'bg-emerald-500 text-white' : 'bg-emerald-100 text-emerald-600'}`}>
                          <GraduationCap className="h-5 w-5" />
                        </div>
                        <div className="text-right">
                          <p className="font-bold text-slate-800">{stage.name_ar}</p>
                          <p className="text-xs text-slate-500">{stage.grades_count} صفوف</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {loadingCurriculum[stage.id] && <RefreshCw className="h-4 w-4 animate-spin text-slate-400" />}
                        <ChevronRight className={`h-5 w-5 text-slate-400 transition-transform ${expandedStages[stage.id] ? 'rotate-90' : ''}`} />
                      </div>
                    </button>

                    {expandedStages[stage.id] && stageCurriculums[stage.id] && (
                      <div className="pr-6 pb-4">
                        {stageCurriculums[stage.id].tracks?.map((track) => (
                          <div key={track.id} className="mr-4 mt-2 border-r-2 border-blue-200">
                            <button onClick={() => toggleTrackExpand(track.id)} className="w-full flex items-center justify-between p-3 hover:bg-blue-50 rounded-lg transition-colors mr-2" data-testid={`track-expand-${track.id}`}>
                              <div className="flex items-center gap-2">
                                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${expandedTracks[track.id] ? 'bg-blue-500 text-white' : 'bg-blue-100 text-blue-600'}`}><Layers className="h-4 w-4" /></div>
                                <div className="text-right">
                                  <p className="font-medium text-slate-700">{track.name_ar}</p>
                                  <p className="text-xs text-slate-500">{track.grades_count} صف</p>
                                </div>
                              </div>
                              <ChevronRight className={`h-4 w-4 text-slate-400 transition-transform ${expandedTracks[track.id] ? 'rotate-90' : ''}`} />
                            </button>

                            {expandedTracks[track.id] && track.grades?.map((grade) => (
                              <div key={grade.id} className="mr-8 mt-2 border-r-2 border-violet-200">
                                <button onClick={() => toggleGradeExpand(grade.id)} className="w-full flex items-center justify-between p-3 hover:bg-violet-50 rounded-lg transition-colors mr-2" data-testid={`grade-expand-${grade.id}`}>
                                  <div className="flex items-center gap-2">
                                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${expandedGrades[grade.id] ? 'bg-violet-500 text-white' : 'bg-violet-100 text-violet-600'}`}><BookOpen className="h-4 w-4" /></div>
                                    <div className="text-right">
                                      <p className="font-medium text-slate-700 text-sm">{grade.name_ar}</p>
                                      <p className="text-xs text-slate-500">{grade.subjects_count} مادة | {grade.total_annual_periods} حصة سنوياً</p>
                                    </div>
                                  </div>
                                  <ChevronRight className={`h-4 w-4 text-slate-400 transition-transform ${expandedGrades[grade.id] ? 'rotate-90' : ''}`} />
                                </button>

                                {expandedGrades[grade.id] && (
                                  <div className="mr-8 mt-2 mb-4 bg-white rounded-lg border border-slate-200 overflow-hidden">
                                    <table className="w-full text-sm">
                                      <thead className="bg-slate-100">
                                        <tr>
                                          <th className="text-right p-3 font-medium text-slate-700">#</th>
                                          <th className="text-right p-3 font-medium text-slate-700">المادة</th>
                                          <th className="text-center p-3 font-medium text-slate-700">الحصص السنوية</th>
                                          <th className="text-center p-3 font-medium text-slate-700">الحصص الأسبوعية</th>
                                          <th className="text-center p-3 font-medium text-slate-700">النوع</th>
                                          <th className="text-center p-3 font-medium text-slate-700">الحالة</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-slate-100">
                                        {grade.subjects?.map((subj, idx) => (
                                          <tr key={subj.id || idx} className="hover:bg-slate-50">
                                            <td className="p-3 text-slate-500">{idx + 1}</td>
                                            <td className="p-3">
                                              <p className="font-medium text-slate-800">{subj.subject_name_ar}</p>
                                              <p className="text-xs text-slate-400">{subj.subject_name_en}</p>
                                            </td>
                                            <td className="p-3 text-center"><span className="font-bold text-emerald-700">{subj.annual_periods}</span></td>
                                            <td className="p-3 text-center">
                                              <span className="font-bold text-blue-700">
                                                {(() => {
                                                  const weekly = subj.weekly_periods ?? subj.weekly_sessions ?? (subj.annual_periods ? Math.round((subj.annual_periods / 36) * 10) / 10 : null) ?? (subj.annual_sessions ? Math.round((subj.annual_sessions / 36) * 10) / 10 : '—');
                                                  return typeof weekly === 'number' ? weekly.toFixed(1) : weekly;
                                                })()}
                                              </span>
                                            </td>
                                            <td className="p-3 text-center">
                                              <Badge variant="outline" className={subj.period_type === 'class_period' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-amber-50 text-amber-700 border-amber-200'}>
                                                {subj.period_type === 'class_period' ? 'حصة صفية' : 'فترة لاصفية'}
                                              </Badge>
                                            </td>
                                            <td className="p-3 text-center">
                                              <Badge variant="outline" className="bg-slate-100 text-slate-600 border-slate-200"><Lock className="h-3 w-3 ml-1" />رسمي</Badge>
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                    <div className="bg-slate-50 p-3 flex justify-around text-sm border-t">
                                      <div className="text-center"><p className="font-bold text-emerald-700">{grade.subjects?.length || 0}</p><p className="text-xs text-slate-500">مادة</p></div>
                                      <div className="text-center"><p className="font-bold text-blue-700">{grade.total_annual_periods}</p><p className="text-xs text-slate-500">حصة سنوية</p></div>
                                      <div className="text-center"><p className="font-bold text-violet-700">{grade.subjects?.filter(s => s.period_type === 'class_period').length || 0}</p><p className="text-xs text-slate-500">حصة صفية</p></div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
