import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { getFormErrorMessage } from '@/shared/models/utils/apiError';
import { useCanViewInternalIds } from '@/shared/hooks/useCanViewInternalIds';
import { maskInternalId } from '@/shared/models/utils/internalId';
import {
  User, BookOpen, Edit, Save, X, Phone, Mail, Hash, Calendar,
  MapPin, Loader2, Award, Briefcase, Copy, Eye, EyeOff, History,
  AlertTriangle, CheckCircle, FileText
} from 'lucide-react';

export default function TeacherProfileDialog({ open, onClose, teacher, onRefresh }) {
  const { api } = useAuth();
  const canViewInternalIds = useCanViewInternalIds();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('info');
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editSection, setEditSection] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({});
  const [credForm, setCredForm] = useState({ new_email: '', new_password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [actionLoading, setActionLoading] = useState('');

  const fetchProfile = useCallback(async () => {
    if (!teacher?.id) return;
    setLoading(true);
    try {
      const res = await api.get(`/principal/teacher/${teacher.id}/full-profile`);
      setProfile(res.data?.profile);
    } catch (e) {
      setProfile(null);
      nassaqError(getFormErrorMessage(e, { t }) || (t('failedToLoadProfile')));
    } finally {
      setLoading(false);
    }
  }, [teacher?.id, api]);

  useEffect(() => {
    if (open && teacher?.id) {
      setActiveTab('info');
      setEditing(false);
      setEditSection(null);
      fetchProfile();
    }
  }, [open, teacher?.id, fetchProfile]);

  const handleSaveBasicInfo = async () => {
    setSaving(true);
    try {
      await api.put(`/principal/teacher/${teacher.id}/basic-info`, formData);
      toast.success(isRTL ? 'تم تحديث البيانات بنجاح' : 'Profile updated successfully');
      setEditing(false);
      setEditSection(null);
      fetchProfile();
      onRefresh?.();
    } catch (e) {
      nassaqError(getFormErrorMessage(e, { t }) || (t('updateFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveProfessional = async () => {
    setSaving(true);
    try {
      await api.put(`/principal/teacher/${teacher.id}/professional-info`, formData);
      toast.success(t('professionalInfoUpdated'));
      setEditing(false);
      setEditSection(null);
      fetchProfile();
      onRefresh?.();
    } catch (e) {
      nassaqError(getFormErrorMessage(e, { t }) || (t('updateFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCredentials = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/principal/teacher/${teacher.id}/credentials`, credForm);
      if (res.data?.account_created) {
        toast.success(t('loginAccountCreatedSuccessfully2'));
      } else {
        toast.success(t('credentialsUpdated'));
      }
      setCredForm({ new_email: '', new_password: '' });
      fetchProfile();
    } catch (e) {
      nassaqError(getFormErrorMessage(e, { t }) || (t('updateFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePassword = async () => {
    try {
      const res = await api.post('/principal/generate-password');
      setCredForm(p => ({ ...p, new_password: res.data.password }));
      toast.success(t('strongPasswordGenerated'));
    } catch (e) {
      console.error('Error generating password:', e);
      nassaqError(t('failedToGeneratePassword'));
    }
  };

  const handleStatusChange = async (newStatus) => {
    setActionLoading(newStatus);
    try {
      await api.put(`/principal/teacher/${teacher.id}/status`, { status: newStatus });
      const labels = { active: t('active'), suspended: isRTL ? 'معلق' : 'Suspended', closed: t('closed') };
      toast.success(`${t('statusChangedTo')}: ${labels[newStatus] || newStatus}`);
      if (newStatus === 'closed') {
        onRefresh?.();
        onClose?.();
      } else {
        fetchProfile();
        onRefresh?.();
      }
    } catch (e) {
      nassaqError(getFormErrorMessage(e, { t }) || (t('actionFailed')));
    } finally {
      setActionLoading('');
    }
  };

  const handleDelete = () => {
    nassaqConfirm(
      t('areYouSureYouWantToPermanentlyDeleteThisTeacherThi'),
      async () => {
        setActionLoading('delete');
        try {
          await api.delete(`/teachers/${teacher.id}`);
          toast.success(t('teacherDeletedSuccessfully'));
          onClose?.();
          onRefresh?.();
        } catch (e) {
          nassaqError(getFormErrorMessage(e, { t }) || (t('failedToDeleteTeacher')));
        } finally {
          setActionLoading('');
        }
      },
      { title: t('confirmPermanentDelete'), confirmText: t('yesDeletePermanently'), cancelText: t('cancel') }
    );
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${t('copied')} ${label}`);
  };

  const startEdit = (section) => {
    const p = profile;
    if (section === 'basic') {
      setFormData({ ...p?.basic_info, ...p?.contact_info });
    } else if (section === 'professional') {
      setFormData({ ...p?.professional_info });
    }
    setEditSection(section);
    setEditing(true);
  };

  if (!teacher) return null;

  const p = profile;
  const status = p?.operational_info?.status || teacher.status || 'active';
  const statusColors = {
    active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    suspended: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    inactive: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
    closed: 'bg-red-200 text-red-800 dark:bg-red-900/50 dark:text-red-300'
  };
  const statusLabels = { active: t('active'), suspended: isRTL ? 'معلق' : 'Suspended', inactive: t('inactive'), closed: t('closed') };
  const rankLabels = { teacher: t('teacher'), senior_teacher: t('seniorTeacher'), expert: t('expert'), department_head: t('departmentHead') };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto p-0">
        <div className="bg-gradient-to-r from-emerald-600 to-green-700 p-5 text-white rounded-t-lg">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center text-2xl font-bold">
              {(p?.basic_info?.full_name || teacher.full_name || '').charAt(0)}
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold">{p?.basic_info?.full_name || teacher.full_name}</h2>
              <p className="text-emerald-100 text-sm">{maskInternalId(p?.professional_info?.specialization, canViewInternalIds) || maskInternalId(teacher.specialization, canViewInternalIds) || (t('teacher'))}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge className={`text-[10px] ${statusColors[status]}`}>{statusLabels[status]}</Badge>
                <Badge className="text-[10px] bg-white/20 text-white border-0">{rankLabels[p?.professional_info?.teacher_rank] || teacher.rank || (t('teacher'))}</Badge>
              </div>
            </div>
          </div>
        </div>

        <div className="p-4">
          {loading ? (
            <LoadingState variant="section" />
          ) : (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid grid-cols-6 w-full mb-4">
                <TabsTrigger value="info" className="text-xs"><User className="h-3.5 w-3.5 me-1" />{t('profile')}</TabsTrigger>
                <TabsTrigger value="professional" className="text-xs"><Briefcase className="h-3.5 w-3.5 me-1" />{t('career')}</TabsTrigger>
                <TabsTrigger value="credentials" className="text-xs"><Key className="h-3.5 w-3.5 me-1" />{t('login2')}</TabsTrigger>
                <TabsTrigger value="assignments" className="text-xs"><BookOpen className="h-3.5 w-3.5 me-1" />{t('assign2')}</TabsTrigger>
                <TabsTrigger value="activity" className="text-xs"><History className="h-3.5 w-3.5 me-1" />{t('activity')}</TabsTrigger>
                <TabsTrigger value="actions" className="text-xs"><Settings2 className="h-3.5 w-3.5 me-1" />{t('actions')}</TabsTrigger>
              </TabsList>

              <TabsContent value="info" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold text-sm">{t('basicContactInfo')}</h3>
                  {!editing ? (
                    <Button size="sm" variant="outline" onClick={() => startEdit('basic')}><Edit className="h-3.5 w-3.5 me-1" />{t('edit')}</Button>
                  ) : editSection === 'basic' ? (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveBasicInfo} disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5 me-1" />}{t('save')}</Button>
                      <Button size="sm" variant="outline" onClick={() => { setEditing(false); setEditSection(null); }}><X className="h-3.5 w-3.5" /></Button>
                    </div>
                  ) : null}
                </div>
                {editing && editSection === 'basic' ? (
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { key: 'full_name', label: t('fullName'), icon: User },
                      { key: 'national_id', label: t('nationalId'), icon: Hash },
                      { key: 'phone', label: t('phone'), icon: Phone },
                      { key: 'email', label: t('email'), icon: Mail },
                      { key: 'nationality', label: t('nationality'), icon: MapPin },
                      { key: 'date_of_birth', label: t('dateOfBirth'), icon: Calendar },
                      { key: 'address', label: t('address'), icon: MapPin },
                      { key: 'city', label: t('city'), icon: MapPin },
                    ].map(({ key, label, icon: Icon }) => (
                      <div key={key} className="space-y-1">
                        <Label className="text-xs flex items-center gap-1"><Icon className="h-3 w-3" />{label}</Label>
                        <Input value={formData[key] || ''} onChange={(e) => setFormData(p => ({ ...p, [key]: e.target.value }))} className="h-8 text-sm" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {[
                      { label: t('name'), value: p?.basic_info?.full_name, icon: User },
                      { label: t('id'), value: p?.basic_info?.national_id, icon: Hash },
                      { label: t('phone'), value: p?.contact_info?.phone, icon: Phone },
                      { label: t('email'), value: p?.contact_info?.email || teacher.email, icon: Mail },
                      { label: t('nationality'), value: p?.basic_info?.nationality, icon: MapPin },
                      { label: t('gender'), value: p?.basic_info?.gender === 'male' ? (t('male')) : p?.basic_info?.gender === 'female' ? (t('female')) : '-', icon: User },
                      { label: t('address'), value: p?.contact_info?.address, icon: MapPin },
                      { label: t('city'), value: p?.contact_info?.city, icon: MapPin },
                    ].map(({ label, value, icon: Icon }, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <Icon className="h-3.5 w-3.5 mt-0.5 text-muted-foreground shrink-0" />
                        <div><span className="text-muted-foreground text-xs">{label}</span><p className="font-medium text-sm">{value || '-'}</p></div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="border-t pt-3">
                  <h4 className="font-semibold text-sm mb-2">{t('accountStatus')}</h4>
                  <div className="flex flex-wrap gap-2">
                    {status !== 'active' && (
                      <Button size="sm" variant="outline" className="text-green-600 border-green-300" onClick={() => handleStatusChange('active')} disabled={!!actionLoading}>
                        {actionLoading === 'active' ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <UserCheck className="h-3.5 w-3.5 me-1" />}{t('activate')}
                      </Button>
                    )}
                    {status === 'active' && (
                      <Button size="sm" variant="outline" className="text-amber-600 border-amber-300" onClick={() => handleStatusChange('suspended')} disabled={!!actionLoading}>
                        {actionLoading === 'suspended' ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <UserX className="h-3.5 w-3.5 me-1" />}{t('suspend')}
                      </Button>
                    )}
                    {status !== 'closed' && (
                      <Button size="sm" variant="outline" className="text-red-600 border-red-300" onClick={() => nassaqConfirm(t('areYouSureYouWantToCloseThisAccount'), () => handleStatusChange('closed'), { title: t('confirmClose'), confirmText: t('yesClose'), cancelText: t('cancel') })} disabled={!!actionLoading}>
                        {actionLoading === 'closed' ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <AlertTriangle className="h-3.5 w-3.5 me-1" />}{t('close')}
                      </Button>
                    )}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="professional" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold text-sm">{t('professionalInfo')}</h3>
                  {!editing ? (
                    <Button size="sm" variant="outline" onClick={() => startEdit('professional')}><Edit className="h-3.5 w-3.5 me-1" />{t('edit')}</Button>
                  ) : editSection === 'professional' ? (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveProfessional} disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5 me-1" />}{t('save')}</Button>
                      <Button size="sm" variant="outline" onClick={() => { setEditing(false); setEditSection(null); }}><X className="h-3.5 w-3.5" /></Button>
                    </div>
                  ) : null}
                </div>
                {editing && editSection === 'professional' ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">{t('specialization')}</Label>
                      <Input value={formData.specialization || ''} onChange={(e) => setFormData(p => ({ ...p, specialization: e.target.value }))} className="h-8 text-sm" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{t('degree')}</Label>
                      <Select value={formData.academic_degree || ''} onValueChange={(v) => setFormData(p => ({ ...p, academic_degree: v }))}>
                        <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="diploma">{t('diploma')}</SelectItem>
                          <SelectItem value="bachelor">{t('bachelors')}</SelectItem>
                          <SelectItem value="master">{t('masters')}</SelectItem>
                          <SelectItem value="doctorate">{t('doctorate')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{t('rank')}</Label>
                      <Select value={formData.teacher_rank || ''} onValueChange={(v) => setFormData(p => ({ ...p, teacher_rank: v }))}>
                        <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="teacher">{t('teacher')}</SelectItem>
                          <SelectItem value="senior_teacher">{t('seniorTeacher')}</SelectItem>
                          <SelectItem value="expert">{t('expert')}</SelectItem>
                          <SelectItem value="department_head">{t('departmentHead')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{t('experience')}</Label>
                      <Input type="number" value={formData.years_of_experience ?? ''} onChange={(e) => setFormData(p => ({ ...p, years_of_experience: parseInt(e.target.value) || 0 }))} className="h-8 text-sm" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{t('contract')}</Label>
                      <Select value={formData.contract_type || ''} onValueChange={(v) => setFormData(p => ({ ...p, contract_type: v }))}>
                        <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="permanent">{t('permanent')}</SelectItem>
                          <SelectItem value="contract">{t('contract2')}</SelectItem>
                          <SelectItem value="part_time">{t('parttime')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{t('employee')}</Label>
                      <Input value={formData.employee_number || ''} onChange={(e) => setFormData(p => ({ ...p, employee_number: e.target.value }))} className="h-8 text-sm" />
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {[
                      { label: t('specialization'), value: maskInternalId(p?.professional_info?.specialization, canViewInternalIds), icon: BookOpen },
                      { label: t('degree2'), value: p?.professional_info?.academic_degree, icon: Award },
                      { label: t('rank'), value: rankLabels[p?.professional_info?.teacher_rank] || p?.professional_info?.teacher_rank, icon: Shield },
                      { label: t('experience2'), value: p?.professional_info?.years_of_experience ? `${p.professional_info.years_of_experience} ${t('yrs')}` : '-', icon: Clock },
                      { label: t('contract3'), value: p?.professional_info?.contract_type, icon: FileText },
                      { label: t('employee'), value: p?.professional_info?.employee_number, icon: Hash },
                    ].map(({ label, value, icon: Icon }, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <Icon className="h-3.5 w-3.5 mt-0.5 text-muted-foreground shrink-0" />
                        <div><span className="text-muted-foreground text-xs">{label}</span><p className="font-medium text-sm">{value || '-'}</p></div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="border-t pt-3">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">{t('operational')}</h4>
                  <div className="grid grid-cols-3 gap-3">
                    <Card className="border-emerald-200/50"><CardContent className="p-3 text-center">
                      <p className="text-lg font-bold text-emerald-600">{p?.operational_info?.max_periods_per_week || '-'}</p>
                      <p className="text-[10px] text-muted-foreground">{t('periodswk')}</p>
                    </CardContent></Card>
                    <Card className="border-emerald-200/50"><CardContent className="p-3 text-center">
                      <p className="text-lg font-bold text-emerald-600">{p?.assignments?.length || 0}</p>
                      <p className="text-[10px] text-muted-foreground">{t('assignments')}</p>
                    </CardContent></Card>
                    <Card className="border-emerald-200/50"><CardContent className="p-3 text-center">
                      <p className="text-lg font-bold text-emerald-600">{p?.operational_info?.total_sessions || 0}</p>
                      <p className="text-[10px] text-muted-foreground">{t('sessions')}</p>
                    </CardContent></Card>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="credentials" className="space-y-4">
                <h3 className="font-semibold text-sm">{t('loginCredentials')}</h3>
                {!p?.user_account?.id ? (
                  <Card className="border-amber-200 bg-amber-50/50"><CardContent className="p-4 space-y-3">
                    <div className="flex items-center gap-2 text-amber-700">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span className="font-medium text-sm">{t('noLoginAccountCreatedYet')}</span>
                    </div>
                    <p className="text-xs text-amber-600">{t('thisTeacherOnlyHasAProfileRecordAndCannotLogInUnti')}</p>
                    <div className="border-t border-amber-200 pt-3 space-y-3">
                      <div className="space-y-1">
                        <Label className="text-xs">{t('email2')}</Label>
                        <Input type="email" value={credForm.new_email || teacher.email || ''} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" placeholder={t('accountEmail')} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">{t('password')}</Label>
                        <div className="flex gap-2">
                          <div className="relative flex-1">
                            <Input type={showPassword ? 'text' : 'password'} value={credForm.new_password} onChange={(e) => setCredForm(p => ({ ...p, new_password: e.target.value }))} className="h-8 text-sm pe-8" placeholder={t('newAccountPassword')} />
                            <Button size="icon" variant="ghost" className="h-6 w-6 absolute top-1 end-1" onClick={() => setShowPassword(!showPassword)}>
                              {showPassword ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                            </Button>
                          </div>
                          {credForm.new_password && (
                            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => copyToClipboard(credForm.new_password, t('password'))}>
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={handleGeneratePassword} className="text-amber-600 border-amber-300">
                          <Shield className="h-3.5 w-3.5 me-1" />{t('generatePassword')}
                        </Button>
                        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={handleSaveCredentials} disabled={saving || (!credForm.new_password)}>
                          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <UserCheck className="h-3.5 w-3.5 me-1" />}{t('createLoginAccount')}
                        </Button>
                      </div>
                    </div>
                  </CardContent></Card>
                ) : (
                <Card><CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{t('currentEmail')}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{p?.user_account?.email || teacher.email || '-'}</span>
                      {(p?.user_account?.email || teacher.email) && (
                        <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => copyToClipboard(p?.user_account?.email || teacher.email, t('email'))}>
                          <Copy className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="border-t pt-3 space-y-3">
                    <div className="space-y-1">
                      <Label className="text-xs">{t('newEmailOptional')}</Label>
                      <Input type="email" value={credForm.new_email} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" placeholder={t('enterNewEmail')} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{t('newPassword')}</Label>
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <Input type={showPassword ? 'text' : 'password'} value={credForm.new_password} onChange={(e) => setCredForm(p => ({ ...p, new_password: e.target.value }))} className="h-8 text-sm pe-8" />
                          <Button size="icon" variant="ghost" className="h-6 w-6 absolute top-1 end-1" onClick={() => setShowPassword(!showPassword)}>
                            {showPassword ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                          </Button>
                        </div>
                        {credForm.new_password && (
                          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => copyToClipboard(credForm.new_password, t('password'))}>
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={handleGeneratePassword} className="text-emerald-600">
                        <Shield className="h-3.5 w-3.5 me-1" />{t('generateViaHakim')}
                      </Button>
                      <Button size="sm" onClick={handleSaveCredentials} disabled={saving || (!credForm.new_email && !credForm.new_password)}>
                        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Save className="h-3.5 w-3.5 me-1" />}{t('save')}
                      </Button>
                    </div>
                  </div>
                </CardContent></Card>
                )}
              </TabsContent>

              <TabsContent value="assignments" className="space-y-4">
                <h3 className="font-semibold text-sm">{t('currentAssignments')}</h3>
                {p?.assignments?.length > 0 ? (
                  <div className="space-y-2">
                    {p.assignments.map((a, i) => (
                      <Card key={i} className="border-emerald-200/30">
                        <CardContent className="p-3 flex items-center justify-between">
                          <div>
                            <p className="font-medium text-sm">{a.class_name || maskInternalId(a.class_id, canViewInternalIds)}</p>
                            <p className="text-xs text-muted-foreground">{a.subject_name || maskInternalId(a.subject_id, canViewInternalIds)}</p>
                          </div>
                          <Badge variant="outline" className="text-[10px]">{a.periods_per_week || '-'} {t('periods')}</Badge>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    {t('noCurrentAssignments')}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="activity" className="space-y-4">
                <h3 className="font-semibold text-sm">{t('activityLog')}</h3>
                {p?.recent_activity?.length > 0 ? (
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {p.recent_activity.map((log, i) => (
                      <div key={i} className="flex items-start gap-3 p-2 rounded-lg bg-muted/30 text-sm">
                        <History className="h-3.5 w-3.5 mt-0.5 text-muted-foreground shrink-0" />
                        <div className="flex-1">
                          <p className="font-medium text-xs">{log.action}</p>
                          <p className="text-[10px] text-muted-foreground">{log.performed_at ? new Date(log.performed_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US') : ''}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    <History className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    {t('noActivityLog')}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="actions" className="space-y-4">
                <h3 className="font-semibold text-sm">{t('accountManagement')}</h3>
                <div className="grid grid-cols-2 gap-3">
                  {profile?.basic_info?.status !== 'active' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-green-200 hover:bg-green-50"
                      onClick={() => handleStatusChange('active')}
                      disabled={!!actionLoading}
                    >
                      <UserCheck className="h-4 w-4 me-2 text-green-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-green-700">{t('activateAccount')}</p>
                        <p className="text-xs text-muted-foreground">{t('reactivateTheTeacherAccount')}</p>
                      </div>
                      {actionLoading === 'status' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>
                  )}
                  {profile?.basic_info?.status !== 'suspended' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-yellow-200 hover:bg-yellow-50"
                      onClick={() => handleStatusChange('suspended')}
                      disabled={!!actionLoading}
                    >
                      <UserX className="h-4 w-4 me-2 text-yellow-600" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-yellow-700">{t('suspendAccount')}</p>
                        <p className="text-xs text-muted-foreground">{t('temporarilySuspendTheAccount2')}</p>
                      </div>
                      {actionLoading === 'status' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>
                  )}
                  {profile?.basic_info?.status !== 'closed' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-gray-200 hover:bg-gray-50"
                      onClick={() => handleStatusChange('closed')}
                      disabled={!!actionLoading}
                    >
                      <X className="h-4 w-4 me-2 text-gray-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-gray-700">{t('closeAccount')}</p>
                        <p className="text-xs text-muted-foreground">{t('permanentlyCloseTheAccount')}</p>
                      </div>
                      {actionLoading === 'status' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    className="justify-start h-auto py-3"
                    onClick={() => { setActiveTab('credentials'); }}
                    disabled={!!actionLoading}
                  >
                    <Key className="h-4 w-4 me-2 text-blue-500" />
                    <div className="text-start">
                      <p className="text-sm font-medium">{t('resetPassword')}</p>
                      <p className="text-xs text-muted-foreground">{t('generateANewPassword')}</p>
                    </div>
                  </Button>
                </div>
                <div className="border-t pt-4 mt-4">
                  <h3 className="font-semibold text-sm text-red-600 mb-3">{t('dangerZone')}</h3>
                  <Button
                    variant="outline"
                    className="justify-start h-auto py-3 border-red-200 hover:bg-red-50 w-full"
                    onClick={handleDelete}
                    disabled={!!actionLoading}
                  >
                    <Trash2 className="h-4 w-4 me-2 text-red-500" />
                    <div className="text-start">
                      <p className="text-sm font-medium text-red-600">{t('deleteTeacherPermanently')}</p>
                      <p className="text-xs text-muted-foreground">{t('thisActionCannotBeUndone')}</p>
                    </div>
                    {actionLoading === 'delete' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
