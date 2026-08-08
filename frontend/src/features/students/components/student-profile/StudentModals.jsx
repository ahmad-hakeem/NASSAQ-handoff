import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/shared/components/ui/radio-group';
import { Badge } from '@/shared/components/ui/badge';
import { Switch } from '@/shared/components/ui/switch';
import {
  User, Edit, Save, Loader2, Download, Heart, FileText,
  Stethoscope, Rocket, Medal, Trophy, GraduationCap,
  Sparkles, BarChart3, ClipboardList, ScrollText, CheckSquare,
  Droplet, AlertTriangle
} from 'lucide-react';

import { useTranslation } from '@/shared/contexts/ThemeContext';
export function EditProfileModal({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, editProfileOpen, setEditProfileOpen, student,
    formData, setFormData, saving, handleSave, classes,
  } = hook;

  return (
    <Dialog open={editProfileOpen} onOpenChange={(open) => { setEditProfileOpen(open); if (!open) setFormData({ ...student }); }}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Edit className="h-5 w-5 text-brand-turquoise" />
            {t('editStudentProfile')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-6 py-2">
          <div>
            <h4 className="font-semibold text-sm font-cairo flex items-center gap-2 mb-4">
              <User className="h-4 w-4 text-brand-turquoise" />
              {t('personalInformation')}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('fullName')}</Label>
                <Input value={formData.full_name || ''} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('nationalId')}</Label>
                <Input value={formData.national_id || ''} onChange={(e) => setFormData({ ...formData, national_id: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('email2')}</Label>
                <Input value={formData.email || ''} onChange={(e) => setFormData({ ...formData, email: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('phone2')}</Label>
                <Input value={formData.phone || ''} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('gender')}</Label>
                <Select value={formData.gender || ''} onValueChange={(v) => setFormData({ ...formData, gender: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="male">{t('male')}</SelectItem>
                    <SelectItem value="female">{t('female')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('dateOfBirth')}</Label>
                <Input type="date" value={formData.date_of_birth || ''} onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('grade')}</Label>
                <Input value={formData.grade || ''} onChange={(e) => setFormData({ ...formData, grade: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('class')}</Label>
                <Select value={formData.class_id || ''} onValueChange={(v) => setFormData({ ...formData, class_id: v })}>
                  <SelectTrigger><SelectValue placeholder={isRTL ? 'اختر الفصل' : 'Select Class'} /></SelectTrigger>
                  <SelectContent>
                    {classes.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="border-t pt-4">
            <h4 className="font-semibold text-sm font-cairo flex items-center gap-2 mb-4">
              <Heart className="h-4 w-4 text-rose-500" />
              {isRTL ? 'بيانات ولي الأمر' : 'Guardian Information'}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('guardianName')}</Label>
                <Input value={formData.parent_name || ''} onChange={(e) => setFormData({ ...formData, parent_name: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('relationship')}</Label>
                <Select value={formData.parent_relationship || ''} onValueChange={(v) => setFormData({ ...formData, parent_relationship: v })}>
                  <SelectTrigger><SelectValue placeholder={t('select')} /></SelectTrigger>
                  <SelectContent>
                    {Object.entries({ father: t('father'), mother: t('mother'), guardian: isRTL ? 'ولي أمر' : 'Guardian', brother: t('brother'), sister: t('sister'), uncle: t('uncle'), other: t('other') }).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('guardianPhone')}</Label>
                <Input value={formData.parent_phone || ''} onChange={(e) => setFormData({ ...formData, parent_phone: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-cairo">{t('guardianEmail')}</Label>
                <Input type="email" value={formData.parent_email || ''} onChange={(e) => setFormData({ ...formData, parent_email: e.target.value })} />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button variant="outline" onClick={() => setEditProfileOpen(false)} className="font-cairo">{t('cancel')}</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-brand-navy hover:bg-brand-navy/90 text-white font-cairo gap-1.5">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t('saveChanges')}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function HealthModal({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, healthModalOpen, setHealthModalOpen, student,
    healthForm, setHealthForm, savingHealth, handleSaveHealth,
  } = hook;

  const hasHealth = student?.health_info && Object.keys(student.health_info).length > 0;
  const setField = (k, v) => setHealthForm({ ...healthForm, [k]: v });
  const bloodTypes = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

  const ToggleRow = ({ field, detailField, label, placeholder, icon: Icon }) => (
    <div className="rounded-lg border p-3 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs font-cairo flex items-center gap-2">
          {Icon && <Icon className="h-3.5 w-3.5 text-rose-500" strokeWidth={1.5} aria-hidden="true" />}
          {label}
        </Label>
        <Switch checked={!!healthForm[field]} onCheckedChange={(v) => setField(field, v)} />
      </div>
      {healthForm[field] && (
        <Textarea
          value={healthForm[detailField] || ''}
          onChange={(e) => setField(detailField, e.target.value)}
          className="rounded-lg resize-none" rows={2} placeholder={placeholder}
        />
      )}
    </div>
  );

  return (
    <Dialog open={healthModalOpen} onOpenChange={setHealthModalOpen}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Stethoscope className="h-5 w-5 text-rose-500" strokeWidth={1.5} aria-hidden="true" />
            {hasHealth ? t('editHealthNotes') : t('addHealthNotes')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label className="text-xs font-cairo flex items-center gap-2">
              <Droplet className="h-3.5 w-3.5 text-rose-500" strokeWidth={1.5} aria-hidden="true" />
              {t('bloodType')}
            </Label>
            <Select value={healthForm.blood_type || ''} onValueChange={(v) => setField('blood_type', v)}>
              <SelectTrigger><SelectValue placeholder={t('select')} /></SelectTrigger>
              <SelectContent>
                {bloodTypes.map(bt => <SelectItem key={bt} value={bt}>{bt}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <ToggleRow field="has_chronic_conditions" detailField="chronic_conditions" label={t('chronicConditions')} placeholder={t('chronicConditions')} />
          <ToggleRow field="has_allergies" detailField="allergies" label={t('allergies')} placeholder={t('allergies')} />
          <ToggleRow field="has_disabilities" detailField="disabilities" label={t('disabilities')} placeholder={t('disabilities')} />

          <div className="space-y-1.5">
            <Label className="text-xs font-cairo">{t('currentMedications')}</Label>
            <Textarea value={healthForm.current_medications || ''} onChange={(e) => setField('current_medications', e.target.value)} className="rounded-lg resize-none" rows={2} placeholder={t('currentMedications')} />
          </div>

          <ToggleRow field="requires_special_care" detailField="special_care_notes" label={t('requiresSpecialCare')} placeholder={t('specialCareNotes')} icon={AlertTriangle} />

          <div className="space-y-1.5">
            <Label className="text-xs font-cairo flex items-center gap-2">
              <Heart className="h-3.5 w-3.5 text-red-500" strokeWidth={1.5} aria-hidden="true" />
              {t('emergencyMedicalNotes')}
            </Label>
            <Textarea value={healthForm.emergency_medical_notes || ''} onChange={(e) => setField('emergency_medical_notes', e.target.value)} className="rounded-lg resize-none" rows={2} placeholder={t('emergencyMedicalNotes')} />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button variant="outline" onClick={() => setHealthModalOpen(false)} className="font-cairo">{t('cancel')}</Button>
            <Button onClick={handleSaveHealth} disabled={savingHealth} className="bg-brand-navy hover:bg-brand-navy/90 text-white font-cairo gap-1.5">
              {savingHealth ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t('saveChanges')}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function BehaviourModal({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, behaviourModalOpen, setBehaviourModalOpen,
    editingBehaviour, behaviourForm, setBehaviourForm,
    behaviourTypes, savingBehaviour, handleSaveBehaviour,
  } = hook;

  return (
    <Dialog open={behaviourModalOpen} onOpenChange={setBehaviourModalOpen}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo">{editingBehaviour ? (t('editBehaviorRecord')) : (t('addBehaviorRecord'))}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <Label className="font-cairo text-sm">{t('behaviorType')}</Label>
            <Select value={behaviourForm.behaviour_type_id} onValueChange={v => {
              const bt = behaviourTypes.find(bt => bt.id === v);
              setBehaviourForm(prev => ({
                ...prev,
                behaviour_type_id: v,
                title: isRTL ? (bt?.name_ar || prev.title) : (bt?.name_en || bt?.name_ar || prev.title),
                category: bt?.category || prev.category,
              }));
            }}>
              <SelectTrigger className="mt-1"><SelectValue placeholder={t('selectType')} /></SelectTrigger>
              <SelectContent>
                {behaviourTypes.length === 0 ? (
                  <div className="px-3 py-4 text-center text-sm text-muted-foreground font-cairo">{t('noBehaviorTypesAvailable')}</div>
                ) : (
                  behaviourTypes.map(bt => {
                    const pts = bt.default_points ?? bt.points;
                    return (
                      <SelectItem key={bt.id} value={bt.id}>
                        <span className="font-cairo">{bt.name_ar || bt.name_en}</span>
                        {pts != null && <span className={`mr-2 text-xs ${pts > 0 ? 'text-green-600' : pts < 0 ? 'text-red-600' : ''}`}> ({pts > 0 ? '+' : ''}{pts})</span>}
                      </SelectItem>
                    );
                  })
                )}
              </SelectContent>
            </Select>
            {behaviourTypes.length === 0 && (
              <p className="mt-1 text-xs text-muted-foreground font-cairo">{t('noBehaviorTypesAvailable')}</p>
            )}
          </div>
          <div>
            <Label className="font-cairo text-sm">{t('category')}</Label>
            <Select value={behaviourForm.category} onValueChange={v => setBehaviourForm(prev => ({ ...prev, category: v }))}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="positive"><span className="font-cairo text-green-600">{t('positive')}</span></SelectItem>
                <SelectItem value="negative"><span className="font-cairo text-red-600">{t('negative')}</span></SelectItem>
                <SelectItem value="neutral"><span className="font-cairo text-gray-500">{t('neutral')}</span></SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="font-cairo text-sm">{isRTL ? 'العنوان' : 'Title'}</Label>
            <Input value={behaviourForm.title} onChange={e => setBehaviourForm(prev => ({ ...prev, title: e.target.value }))} className="mt-1 font-cairo" placeholder={t('behaviorTitle')} />
          </div>
          <div>
            <Label className="font-cairo text-sm">{t('description')}</Label>
            <Textarea value={behaviourForm.description} onChange={e => setBehaviourForm(prev => ({ ...prev, description: e.target.value }))} className="mt-1 font-cairo" rows={3} placeholder={t('additionalDetails')} />
          </div>
          <div>
            <Label className="font-cairo text-sm">{t('incidentDate')}</Label>
            <Input type="date" value={behaviourForm.incident_date} onChange={e => setBehaviourForm(prev => ({ ...prev, incident_date: e.target.value }))} className="mt-1" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setBehaviourModalOpen(false)} className="font-cairo">{t('cancel')}</Button>
            <Button onClick={handleSaveBehaviour} disabled={savingBehaviour} className="bg-brand-navy hover:bg-brand-navy/90 text-white font-cairo gap-1">
              {savingBehaviour ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {editingBehaviour ? (isRTL ? 'تحديث' : 'Update') : (t('save'))}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ExportPlanModal({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, exportModalOpen, setExportModalOpen,
    remedialPlan, enrichmentPlan,
    exportPlanType, setExportPlanType,
    exportFormat, setExportFormat,
    exportingPlan, handleExportPlan,
  } = hook;

  return (
    <Dialog open={exportModalOpen} onOpenChange={setExportModalOpen}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Download className="h-5 w-5 text-brand-navy" />
            {t('exportPlan')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-5 pt-2">
          <div className="space-y-2">
            <Label className="text-sm font-medium font-cairo">{t('planType')}</Label>
            <RadioGroup value={exportPlanType} onValueChange={setExportPlanType} className="space-y-2">
              {remedialPlan && (
                <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'remedial' ? 'border-rose-300 bg-rose-50/50 dark:border-rose-700 dark:bg-rose-950/20' : 'border-border hover:border-rose-200'}`}>
                  <RadioGroupItem value="remedial" />
                  <Stethoscope className="h-4 w-4 text-rose-500 flex-shrink-0" />
                  <span className="text-sm font-medium">{t('remedialPlan')}</span>
                </label>
              )}
              {enrichmentPlan && (
                <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'enrichment' ? 'border-emerald-300 bg-emerald-50/50 dark:border-emerald-700 dark:bg-emerald-950/20' : 'border-border hover:border-emerald-200'}`}>
                  <RadioGroupItem value="enrichment" />
                  <Rocket className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                  <span className="text-sm font-medium">{t('enrichmentPlan')}</span>
                </label>
              )}
              {remedialPlan && enrichmentPlan && (
                <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'both' ? 'border-brand-navy/30 bg-brand-navy/5 dark:border-brand-navy/50 dark:bg-brand-navy/10' : 'border-border hover:border-brand-navy/20'}`}>
                  <RadioGroupItem value="both" />
                  <FileText className="h-4 w-4 text-brand-navy flex-shrink-0" />
                  <span className="text-sm font-medium">{t('bothPlans')}</span>
                </label>
              )}
            </RadioGroup>
          </div>

          <div className="space-y-2">
            <Label className="text-sm font-medium font-cairo">{t('fileFormat')}</Label>
            <RadioGroup value={exportFormat} onValueChange={setExportFormat} className="grid grid-cols-2 gap-2">
              <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'pdf' ? 'border-red-300 bg-red-50/50 dark:border-red-700 dark:bg-red-950/20 ring-1 ring-red-200 dark:ring-red-800' : 'border-border hover:border-red-200'}`}>
                <RadioGroupItem value="pdf" className="sr-only" />
                <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <span className="text-red-600 dark:text-red-400 font-bold text-xs">PDF</span>
                </div>
                <span className="text-xs font-medium">{t('pdfFile')}</span>
              </label>
              <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'docx' ? 'border-blue-300 bg-blue-50/50 dark:border-blue-700 dark:bg-blue-950/20 ring-1 ring-blue-200 dark:ring-blue-800' : 'border-border hover:border-blue-200'}`}>
                <RadioGroupItem value="docx" className="sr-only" />
                <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                  <span className="text-blue-600 dark:text-blue-400 font-bold text-xs">DOCX</span>
                </div>
                <span className="text-xs font-medium">{t('wordFile')}</span>
              </label>
            </RadioGroup>
          </div>

          <Button className="w-full gap-2 bg-brand-navy hover:bg-brand-navy/90 text-white" onClick={() => handleExportPlan(exportPlanType, exportFormat)} disabled={exportingPlan}>
            {exportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {t('download')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ActivityModal({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, activityModalOpen, setActivityModalOpen,
    editingActivity, activityForm, setActivityForm,
    savingActivity, handleSaveActivity, ACTIVITY_TYPE_OPTIONS,
  } = hook;

  return (
    <Dialog open={activityModalOpen} onOpenChange={setActivityModalOpen}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Medal className="h-5 w-5 text-brand-navy" />
            {editingActivity ? (t('editActivity')) : (t('addActivity'))}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <Label className="font-cairo text-sm">{t('activityName')} *</Label>
            <Input value={activityForm.name} onChange={e => setActivityForm(prev => ({ ...prev, name: e.target.value }))} className="mt-1 font-cairo" placeholder={t('egMathCompetition')} />
          </div>
          <div>
            <Label className="font-cairo text-sm">{t('activityType')}</Label>
            <Select value={activityForm.activity_type} onValueChange={v => setActivityForm(prev => ({ ...prev, activity_type: v }))}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                {ACTIVITY_TYPE_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}><span className="font-cairo">{opt.icon} {isRTL ? opt.ar : opt.en}</span></SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="font-cairo text-sm">{t('date')}</Label>
              <Input type="date" value={activityForm.date} onChange={e => setActivityForm(prev => ({ ...prev, date: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="font-cairo text-sm">{t('rolePosition')}</Label>
              <Input value={activityForm.role} onChange={e => setActivityForm(prev => ({ ...prev, role: e.target.value }))} className="mt-1 font-cairo" placeholder={t('egParticipant')} />
            </div>
          </div>
          <div>
            <Label className="font-cairo text-sm">{t('description2')}</Label>
            <Textarea value={activityForm.description} onChange={e => setActivityForm(prev => ({ ...prev, description: e.target.value }))} className="mt-1 font-cairo" rows={2} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setActivityModalOpen(false)} className="font-cairo">{t('cancel')}</Button>
            <Button onClick={handleSaveActivity} disabled={savingActivity} className="bg-brand-navy hover:bg-brand-navy/90 text-white font-cairo gap-1.5">
              {savingActivity ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t('save')}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function CertificateModal({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, certificateModalOpen, setCertificateModalOpen,
    editingCertificate, certificateForm, setCertificateForm,
    savingCertificate, handleSaveCertificate,
  } = hook;

  return (
    <Dialog open={certificateModalOpen} onOpenChange={setCertificateModalOpen}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Trophy className="h-5 w-5 text-amber-500" />
            {editingCertificate ? (t('editCertificate')) : (t('addCertificateAward'))}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <Label className="font-cairo text-sm">{isRTL ? 'العنوان' : 'Title'} *</Label>
            <Input value={certificateForm.title} onChange={e => setCertificateForm(prev => ({ ...prev, title: e.target.value }))} className="mt-1 font-cairo" placeholder={t('egExcellenceAward')} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="font-cairo text-sm">{t('date')}</Label>
              <Input type="date" value={certificateForm.date} onChange={e => setCertificateForm(prev => ({ ...prev, date: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="font-cairo text-sm">{t('issuingBody')}</Label>
              <Input value={certificateForm.issuing_body} onChange={e => setCertificateForm(prev => ({ ...prev, issuing_body: e.target.value }))} className="mt-1 font-cairo" placeholder={t('egMinistryOfEducation')} />
            </div>
          </div>
          <div>
            <Label className="font-cairo text-sm">{t('description2')}</Label>
            <Textarea value={certificateForm.description} onChange={e => setCertificateForm(prev => ({ ...prev, description: e.target.value }))} className="mt-1 font-cairo" rows={2} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setCertificateModalOpen(false)} className="font-cairo">{t('cancel')}</Button>
            <Button onClick={handleSaveCertificate} disabled={savingCertificate} className="bg-amber-500 hover:bg-amber-600 text-white font-cairo gap-1.5">
              {savingCertificate ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t('save')}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function FullProfileExportModal({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, profileExportModalOpen, setProfileExportModalOpen,
    profileExportSections, profileExportFormat, setProfileExportFormat,
    exportingProfile, handleExportFullProfile, toggleProfileSection,
  } = hook;

  const sections = [
    { key: 'personal', icon: User, label_ar: 'المعلومات الشخصية وولي الأمر', label_en: 'Personal & Guardian Info' },
    { key: 'academic', icon: BarChart3, label_ar: 'الأداء الأكاديمي', label_en: 'Academic Performance' },
    { key: 'talents', icon: Sparkles, label_ar: 'المواهب والمهارات', label_en: 'Talents & Skills' },
    { key: 'behaviour', icon: Heart, label_ar: 'السلوك', label_en: 'Behavior Record' },
    { key: 'activities', icon: Medal, label_ar: 'الأنشطة والإنجازات', label_en: 'Activities & Achievements' },
    { key: 'plans', icon: ClipboardList, label_ar: 'الخطط العلاجية / الإثرائية', label_en: 'Plans (Remedial / Enrichment)' },
    { key: 'longitudinal', icon: ScrollText, label_ar: 'السجل التراكمي', label_en: 'Longitudinal Summary' },
  ];

  return (
    <Dialog open={profileExportModalOpen} onOpenChange={setProfileExportModalOpen}>
      <DialogContent className="sm:max-w-lg" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Download className="h-5 w-5 text-brand-navy" />
            {t('exportFullProfile')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-5 pt-2">
          <div className="space-y-2">
            <Label className="text-sm font-medium font-cairo">{t('selectSectionsToInclude')}</Label>
            <div className="space-y-2">
              {sections.map(sec => {
                const Icon = sec.icon;
                const checked = profileExportSections.includes(sec.key);
                return (
                  <label key={sec.key} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${checked ? 'border-brand-navy/30 bg-brand-navy/5 dark:border-brand-navy/50 dark:bg-brand-navy/10' : 'border-border hover:border-brand-navy/20'}`} onClick={() => toggleProfileSection(sec.key)}>
                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${checked ? 'bg-brand-navy border-brand-navy' : 'border-gray-300 dark:border-gray-600'}`}>
                      {checked && <CheckSquare className="h-3.5 w-3.5 text-white" />}
                    </div>
                    <Icon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="text-sm font-medium font-cairo">{isRTL ? sec.label_ar : sec.label_en}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-sm font-medium font-cairo">{t('fileFormat')}</Label>
            <RadioGroup value={profileExportFormat} onValueChange={setProfileExportFormat} className="grid grid-cols-2 gap-2">
              <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${profileExportFormat === 'pdf' ? 'border-red-300 bg-red-50/50 dark:border-red-700 dark:bg-red-950/20 ring-1 ring-red-200 dark:ring-red-800' : 'border-border hover:border-red-200'}`}>
                <RadioGroupItem value="pdf" className="sr-only" />
                <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <span className="text-red-600 dark:text-red-400 font-bold text-xs">PDF</span>
                </div>
                <span className="text-xs font-medium">{t('pdfFile')}</span>
              </label>
              <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${profileExportFormat === 'docx' ? 'border-blue-300 bg-blue-50/50 dark:border-blue-700 dark:bg-blue-950/20 ring-1 ring-blue-200 dark:ring-blue-800' : 'border-border hover:border-blue-200'}`}>
                <RadioGroupItem value="docx" className="sr-only" />
                <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                  <span className="text-blue-600 dark:text-blue-400 font-bold text-xs">DOCX</span>
                </div>
                <span className="text-xs font-medium">{t('wordFile')}</span>
              </label>
            </RadioGroup>
          </div>

          <Button
            className="w-full gap-2 bg-brand-navy hover:bg-brand-navy/90 text-white"
            onClick={handleExportFullProfile}
            disabled={exportingProfile || profileExportSections.length === 0}
          >
            {exportingProfile ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {t('generateDownload')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
