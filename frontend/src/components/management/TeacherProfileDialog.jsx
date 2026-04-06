import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { toast } from 'sonner';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import {
  User, BookOpen, Shield, Edit, Save, X, Phone, Mail, Hash, Calendar,
  MapPin, Key, UserX, UserCheck, Loader2, Award, Clock, Briefcase,
  Copy, Eye, EyeOff, History, AlertTriangle, CheckCircle, FileText,
  Trash2, Settings2
} from 'lucide-react';

export default function TeacherProfileDialog({ open, onClose, teacher, onRefresh }) {
  const { api } = useAuth();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();
  const { isRTL } = useTheme();
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
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل تحميل الملف الشخصي' : 'Failed to load profile'));
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
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل التحديث' : 'Update failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveProfessional = async () => {
    setSaving(true);
    try {
      await api.put(`/principal/teacher/${teacher.id}/professional-info`, formData);
      toast.success(isRTL ? 'تم تحديث البيانات المهنية' : 'Professional info updated');
      setEditing(false);
      setEditSection(null);
      fetchProfile();
      onRefresh?.();
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل التحديث' : 'Update failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCredentials = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/principal/teacher/${teacher.id}/credentials`, credForm);
      if (res.data?.account_created) {
        toast.success(isRTL ? 'تم إنشاء حساب دخول للمعلم بنجاح' : 'Login account created successfully');
      } else {
        toast.success(isRTL ? 'تم تحديث بيانات الدخول' : 'Credentials updated');
      }
      setCredForm({ new_email: '', new_password: '' });
      fetchProfile();
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل التحديث' : 'Update failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePassword = async () => {
    try {
      const res = await api.post('/principal/generate-password');
      setCredForm(p => ({ ...p, new_password: res.data.password }));
      toast.success(isRTL ? 'تم توليد كلمة مرور قوية' : 'Strong password generated');
    } catch (e) {
      console.error('Error generating password:', e);
      nassaqError(isRTL ? 'فشل توليد كلمة المرور' : 'Failed to generate password');
    }
  };

  const handleStatusChange = async (newStatus) => {
    setActionLoading(newStatus);
    try {
      await api.put(`/principal/teacher/${teacher.id}/status`, { status: newStatus });
      const labels = { active: isRTL ? 'نشط' : 'Active', suspended: isRTL ? 'معلق' : 'Suspended', closed: isRTL ? 'مغلق' : 'Closed' };
      toast.success(`${isRTL ? 'تم تغيير الحالة إلى' : 'Status changed to'}: ${labels[newStatus] || newStatus}`);
      if (newStatus === 'closed') {
        onRefresh?.();
        onClose?.();
      } else {
        fetchProfile();
        onRefresh?.();
      }
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشلت العملية' : 'Action failed'));
    } finally {
      setActionLoading('');
    }
  };

  const handleDelete = () => {
    nassaqConfirm(
      isRTL ? 'هل أنت متأكد من حذف هذا المعلم نهائياً؟ لا يمكن التراجع عن هذا الإجراء.' : 'Are you sure you want to permanently delete this teacher? This action cannot be undone.',
      async () => {
        setActionLoading('delete');
        try {
          await api.delete(`/teachers/${teacher.id}`);
          toast.success(isRTL ? 'تم حذف المعلم بنجاح' : 'Teacher deleted successfully');
          onClose?.();
          onRefresh?.();
        } catch (e) {
          nassaqError(e.response?.data?.detail || (isRTL ? 'فشل حذف المعلم' : 'Failed to delete teacher'));
        } finally {
          setActionLoading('');
        }
      },
      { title: isRTL ? 'تأكيد الحذف النهائي' : 'Confirm Permanent Delete', confirmText: isRTL ? 'نعم، احذف نهائياً' : 'Yes, Delete Permanently', cancelText: isRTL ? 'إلغاء' : 'Cancel' }
    );
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${isRTL ? 'تم نسخ' : 'Copied'} ${label}`);
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
  const statusLabels = { active: isRTL ? 'نشط' : 'Active', suspended: isRTL ? 'معلق' : 'Suspended', inactive: isRTL ? 'غير نشط' : 'Inactive', closed: isRTL ? 'مغلق' : 'Closed' };
  const rankLabels = { teacher: isRTL ? 'معلم' : 'Teacher', senior_teacher: isRTL ? 'معلم أول' : 'Senior Teacher', expert: isRTL ? 'معلم خبير' : 'Expert', department_head: isRTL ? 'رئيس قسم' : 'Department Head' };

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
              <p className="text-emerald-100 text-sm">{p?.professional_info?.specialization || teacher.specialization || (isRTL ? 'معلم' : 'Teacher')}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge className={`text-[10px] ${statusColors[status]}`}>{statusLabels[status]}</Badge>
                <Badge className="text-[10px] bg-white/20 text-white border-0">{rankLabels[p?.professional_info?.teacher_rank] || teacher.rank || (isRTL ? 'معلم' : 'Teacher')}</Badge>
              </div>
            </div>
          </div>
        </div>

        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-emerald-600" /></div>
          ) : (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid grid-cols-6 w-full mb-4">
                <TabsTrigger value="info" className="text-xs"><User className="h-3.5 w-3.5 me-1" />{isRTL ? 'الملف' : 'Profile'}</TabsTrigger>
                <TabsTrigger value="professional" className="text-xs"><Briefcase className="h-3.5 w-3.5 me-1" />{isRTL ? 'المهني' : 'Career'}</TabsTrigger>
                <TabsTrigger value="credentials" className="text-xs"><Key className="h-3.5 w-3.5 me-1" />{isRTL ? 'الدخول' : 'Login'}</TabsTrigger>
                <TabsTrigger value="assignments" className="text-xs"><BookOpen className="h-3.5 w-3.5 me-1" />{isRTL ? 'الإسنادات' : 'Assign'}</TabsTrigger>
                <TabsTrigger value="activity" className="text-xs"><History className="h-3.5 w-3.5 me-1" />{isRTL ? 'النشاط' : 'Activity'}</TabsTrigger>
                <TabsTrigger value="actions" className="text-xs"><Settings2 className="h-3.5 w-3.5 me-1" />{isRTL ? 'إجراءات' : 'Actions'}</TabsTrigger>
              </TabsList>

              <TabsContent value="info" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold text-sm">{isRTL ? 'البيانات الأساسية والتواصل' : 'Basic & Contact Info'}</h3>
                  {!editing ? (
                    <Button size="sm" variant="outline" onClick={() => startEdit('basic')}><Edit className="h-3.5 w-3.5 me-1" />{isRTL ? 'تعديل' : 'Edit'}</Button>
                  ) : editSection === 'basic' ? (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveBasicInfo} disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5 me-1" />}{isRTL ? 'حفظ' : 'Save'}</Button>
                      <Button size="sm" variant="outline" onClick={() => { setEditing(false); setEditSection(null); }}><X className="h-3.5 w-3.5" /></Button>
                    </div>
                  ) : null}
                </div>
                {editing && editSection === 'basic' ? (
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { key: 'full_name', label: isRTL ? 'الاسم الكامل' : 'Full Name', icon: User },
                      { key: 'national_id', label: isRTL ? 'رقم الهوية' : 'National ID', icon: Hash },
                      { key: 'phone', label: isRTL ? 'الجوال' : 'Phone', icon: Phone },
                      { key: 'email', label: isRTL ? 'البريد' : 'Email', icon: Mail },
                      { key: 'nationality', label: isRTL ? 'الجنسية' : 'Nationality', icon: MapPin },
                      { key: 'date_of_birth', label: isRTL ? 'تاريخ الميلاد' : 'Date of Birth', icon: Calendar },
                      { key: 'address', label: isRTL ? 'العنوان' : 'Address', icon: MapPin },
                      { key: 'city', label: isRTL ? 'المدينة' : 'City', icon: MapPin },
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
                      { label: isRTL ? 'الاسم' : 'Name', value: p?.basic_info?.full_name, icon: User },
                      { label: isRTL ? 'الهوية' : 'ID', value: p?.basic_info?.national_id, icon: Hash },
                      { label: isRTL ? 'الجوال' : 'Phone', value: p?.contact_info?.phone, icon: Phone },
                      { label: isRTL ? 'البريد' : 'Email', value: p?.contact_info?.email || teacher.email, icon: Mail },
                      { label: isRTL ? 'الجنسية' : 'Nationality', value: p?.basic_info?.nationality, icon: MapPin },
                      { label: isRTL ? 'الجنس' : 'Gender', value: p?.basic_info?.gender === 'male' ? (isRTL ? 'ذكر' : 'Male') : p?.basic_info?.gender === 'female' ? (isRTL ? 'أنثى' : 'Female') : '-', icon: User },
                      { label: isRTL ? 'العنوان' : 'Address', value: p?.contact_info?.address, icon: MapPin },
                      { label: isRTL ? 'المدينة' : 'City', value: p?.contact_info?.city, icon: MapPin },
                    ].map(({ label, value, icon: Icon }, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <Icon className="h-3.5 w-3.5 mt-0.5 text-muted-foreground shrink-0" />
                        <div><span className="text-muted-foreground text-xs">{label}</span><p className="font-medium text-sm">{value || '-'}</p></div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="border-t pt-3">
                  <h4 className="font-semibold text-sm mb-2">{isRTL ? 'حالة الحساب' : 'Account Status'}</h4>
                  <div className="flex flex-wrap gap-2">
                    {status !== 'active' && (
                      <Button size="sm" variant="outline" className="text-green-600 border-green-300" onClick={() => handleStatusChange('active')} disabled={!!actionLoading}>
                        {actionLoading === 'active' ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <UserCheck className="h-3.5 w-3.5 me-1" />}{isRTL ? 'تفعيل' : 'Activate'}
                      </Button>
                    )}
                    {status === 'active' && (
                      <Button size="sm" variant="outline" className="text-amber-600 border-amber-300" onClick={() => handleStatusChange('suspended')} disabled={!!actionLoading}>
                        {actionLoading === 'suspended' ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <UserX className="h-3.5 w-3.5 me-1" />}{isRTL ? 'تعليق' : 'Suspend'}
                      </Button>
                    )}
                    {status !== 'closed' && (
                      <Button size="sm" variant="outline" className="text-red-600 border-red-300" onClick={() => nassaqConfirm(isRTL ? 'هل أنت متأكد من إغلاق الحساب؟' : 'Are you sure you want to close this account?', () => handleStatusChange('closed'), { title: isRTL ? 'تأكيد الإغلاق' : 'Confirm Close', confirmText: isRTL ? 'نعم، أغلق' : 'Yes, Close', cancelText: isRTL ? 'إلغاء' : 'Cancel' })} disabled={!!actionLoading}>
                        {actionLoading === 'closed' ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <AlertTriangle className="h-3.5 w-3.5 me-1" />}{isRTL ? 'إغلاق' : 'Close'}
                      </Button>
                    )}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="professional" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold text-sm">{isRTL ? 'البيانات المهنية' : 'Professional Info'}</h3>
                  {!editing ? (
                    <Button size="sm" variant="outline" onClick={() => startEdit('professional')}><Edit className="h-3.5 w-3.5 me-1" />{isRTL ? 'تعديل' : 'Edit'}</Button>
                  ) : editSection === 'professional' ? (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveProfessional} disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5 me-1" />}{isRTL ? 'حفظ' : 'Save'}</Button>
                      <Button size="sm" variant="outline" onClick={() => { setEditing(false); setEditSection(null); }}><X className="h-3.5 w-3.5" /></Button>
                    </div>
                  ) : null}
                </div>
                {editing && editSection === 'professional' ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'التخصص' : 'Specialization'}</Label>
                      <Input value={formData.specialization || ''} onChange={(e) => setFormData(p => ({ ...p, specialization: e.target.value }))} className="h-8 text-sm" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'الدرجة العلمية' : 'Degree'}</Label>
                      <Select value={formData.academic_degree || ''} onValueChange={(v) => setFormData(p => ({ ...p, academic_degree: v }))}>
                        <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="diploma">{isRTL ? 'دبلوم' : 'Diploma'}</SelectItem>
                          <SelectItem value="bachelor">{isRTL ? 'بكالوريوس' : "Bachelor's"}</SelectItem>
                          <SelectItem value="master">{isRTL ? 'ماجستير' : "Master's"}</SelectItem>
                          <SelectItem value="doctorate">{isRTL ? 'دكتوراه' : 'Doctorate'}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'الرتبة' : 'Rank'}</Label>
                      <Select value={formData.teacher_rank || ''} onValueChange={(v) => setFormData(p => ({ ...p, teacher_rank: v }))}>
                        <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="teacher">{isRTL ? 'معلم' : 'Teacher'}</SelectItem>
                          <SelectItem value="senior_teacher">{isRTL ? 'معلم أول' : 'Senior Teacher'}</SelectItem>
                          <SelectItem value="expert">{isRTL ? 'معلم خبير' : 'Expert'}</SelectItem>
                          <SelectItem value="department_head">{isRTL ? 'رئيس قسم' : 'Department Head'}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'سنوات الخبرة' : 'Experience'}</Label>
                      <Input type="number" value={formData.years_of_experience ?? ''} onChange={(e) => setFormData(p => ({ ...p, years_of_experience: parseInt(e.target.value) || 0 }))} className="h-8 text-sm" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'نوع العقد' : 'Contract'}</Label>
                      <Select value={formData.contract_type || ''} onValueChange={(v) => setFormData(p => ({ ...p, contract_type: v }))}>
                        <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="permanent">{isRTL ? 'دائم' : 'Permanent'}</SelectItem>
                          <SelectItem value="contract">{isRTL ? 'متعاقد' : 'Contract'}</SelectItem>
                          <SelectItem value="part_time">{isRTL ? 'دوام جزئي' : 'Part-time'}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'رقم الموظف' : 'Employee #'}</Label>
                      <Input value={formData.employee_number || ''} onChange={(e) => setFormData(p => ({ ...p, employee_number: e.target.value }))} className="h-8 text-sm" />
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {[
                      { label: isRTL ? 'التخصص' : 'Specialization', value: p?.professional_info?.specialization, icon: BookOpen },
                      { label: isRTL ? 'الدرجة' : 'Degree', value: p?.professional_info?.academic_degree, icon: Award },
                      { label: isRTL ? 'الرتبة' : 'Rank', value: rankLabels[p?.professional_info?.teacher_rank] || p?.professional_info?.teacher_rank, icon: Shield },
                      { label: isRTL ? 'الخبرة' : 'Experience', value: p?.professional_info?.years_of_experience ? `${p.professional_info.years_of_experience} ${isRTL ? 'سنة' : 'yrs'}` : '-', icon: Clock },
                      { label: isRTL ? 'العقد' : 'Contract', value: p?.professional_info?.contract_type, icon: FileText },
                      { label: isRTL ? 'رقم الموظف' : 'Employee #', value: p?.professional_info?.employee_number, icon: Hash },
                    ].map(({ label, value, icon: Icon }, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <Icon className="h-3.5 w-3.5 mt-0.5 text-muted-foreground shrink-0" />
                        <div><span className="text-muted-foreground text-xs">{label}</span><p className="font-medium text-sm">{value || '-'}</p></div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="border-t pt-3">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">{isRTL ? 'البيانات التشغيلية' : 'Operational'}</h4>
                  <div className="grid grid-cols-3 gap-3">
                    <Card className="border-emerald-200/50"><CardContent className="p-3 text-center">
                      <p className="text-lg font-bold text-emerald-600">{p?.operational_info?.max_periods_per_week || '-'}</p>
                      <p className="text-[10px] text-muted-foreground">{isRTL ? 'حصة/أسبوع' : 'Periods/wk'}</p>
                    </CardContent></Card>
                    <Card className="border-emerald-200/50"><CardContent className="p-3 text-center">
                      <p className="text-lg font-bold text-emerald-600">{p?.assignments?.length || 0}</p>
                      <p className="text-[10px] text-muted-foreground">{isRTL ? 'إسنادات' : 'Assignments'}</p>
                    </CardContent></Card>
                    <Card className="border-emerald-200/50"><CardContent className="p-3 text-center">
                      <p className="text-lg font-bold text-emerald-600">{p?.operational_info?.total_sessions || 0}</p>
                      <p className="text-[10px] text-muted-foreground">{isRTL ? 'حصص مسجلة' : 'Sessions'}</p>
                    </CardContent></Card>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="credentials" className="space-y-4">
                <h3 className="font-semibold text-sm">{isRTL ? 'إدارة بيانات الدخول' : 'Login Credentials'}</h3>
                {!p?.user_account?.id ? (
                  <Card className="border-amber-200 bg-amber-50/50"><CardContent className="p-4 space-y-3">
                    <div className="flex items-center gap-2 text-amber-700">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span className="font-medium text-sm">{isRTL ? 'لم يتم إنشاء حساب دخول بعد' : 'No login account created yet'}</span>
                    </div>
                    <p className="text-xs text-amber-600">{isRTL ? 'هذا المعلم لديه ملف تعريفي فقط ولا يمكنه تسجيل الدخول حتى يتم إنشاء حساب له.' : 'This teacher only has a profile record and cannot log in until an account is created.'}</p>
                    <div className="border-t border-amber-200 pt-3 space-y-3">
                      <div className="space-y-1">
                        <Label className="text-xs">{isRTL ? 'البريد الإلكتروني' : 'Email'}</Label>
                        <Input type="email" value={credForm.new_email || teacher.email || ''} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" placeholder={isRTL ? 'البريد الإلكتروني للحساب' : 'Account email'} />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">{isRTL ? 'كلمة المرور' : 'Password'}</Label>
                        <div className="flex gap-2">
                          <div className="relative flex-1">
                            <Input type={showPassword ? 'text' : 'password'} value={credForm.new_password} onChange={(e) => setCredForm(p => ({ ...p, new_password: e.target.value }))} className="h-8 text-sm pe-8" placeholder={isRTL ? 'كلمة مرور الحساب الجديد' : 'New account password'} />
                            <Button size="icon" variant="ghost" className="h-6 w-6 absolute top-1 end-1" onClick={() => setShowPassword(!showPassword)}>
                              {showPassword ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                            </Button>
                          </div>
                          {credForm.new_password && (
                            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => copyToClipboard(credForm.new_password, isRTL ? 'كلمة المرور' : 'Password')}>
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={handleGeneratePassword} className="text-amber-600 border-amber-300">
                          <Shield className="h-3.5 w-3.5 me-1" />{isRTL ? 'توليد كلمة مرور' : 'Generate Password'}
                        </Button>
                        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={handleSaveCredentials} disabled={saving || (!credForm.new_password)}>
                          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <UserCheck className="h-3.5 w-3.5 me-1" />}{isRTL ? 'إنشاء حساب دخول' : 'Create Login Account'}
                        </Button>
                      </div>
                    </div>
                  </CardContent></Card>
                ) : (
                <Card><CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{isRTL ? 'البريد الحالي' : 'Current Email'}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{p?.user_account?.email || teacher.email || '-'}</span>
                      {(p?.user_account?.email || teacher.email) && (
                        <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => copyToClipboard(p?.user_account?.email || teacher.email, isRTL ? 'البريد' : 'Email')}>
                          <Copy className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="border-t pt-3 space-y-3">
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'البريد الجديد (اختياري)' : 'New Email (optional)'}</Label>
                      <Input type="email" value={credForm.new_email} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" placeholder={isRTL ? 'أدخل البريد الجديد' : 'Enter new email'} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'كلمة المرور الجديدة' : 'New Password'}</Label>
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <Input type={showPassword ? 'text' : 'password'} value={credForm.new_password} onChange={(e) => setCredForm(p => ({ ...p, new_password: e.target.value }))} className="h-8 text-sm pe-8" />
                          <Button size="icon" variant="ghost" className="h-6 w-6 absolute top-1 end-1" onClick={() => setShowPassword(!showPassword)}>
                            {showPassword ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                          </Button>
                        </div>
                        {credForm.new_password && (
                          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => copyToClipboard(credForm.new_password, isRTL ? 'كلمة المرور' : 'Password')}>
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={handleGeneratePassword} className="text-emerald-600">
                        <Shield className="h-3.5 w-3.5 me-1" />{isRTL ? 'توليد عبر حكيم' : 'Generate via Hakim'}
                      </Button>
                      <Button size="sm" onClick={handleSaveCredentials} disabled={saving || (!credForm.new_email && !credForm.new_password)}>
                        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Save className="h-3.5 w-3.5 me-1" />}{isRTL ? 'حفظ' : 'Save'}
                      </Button>
                    </div>
                  </div>
                </CardContent></Card>
                )}
              </TabsContent>

              <TabsContent value="assignments" className="space-y-4">
                <h3 className="font-semibold text-sm">{isRTL ? 'الإسنادات الحالية' : 'Current Assignments'}</h3>
                {p?.assignments?.length > 0 ? (
                  <div className="space-y-2">
                    {p.assignments.map((a, i) => (
                      <Card key={i} className="border-emerald-200/30">
                        <CardContent className="p-3 flex items-center justify-between">
                          <div>
                            <p className="font-medium text-sm">{a.class_name || a.class_id}</p>
                            <p className="text-xs text-muted-foreground">{a.subject_name || a.subject_id}</p>
                          </div>
                          <Badge variant="outline" className="text-[10px]">{a.periods_per_week || '-'} {isRTL ? 'حصة' : 'periods'}</Badge>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    {isRTL ? 'لا توجد إسنادات حالية' : 'No current assignments'}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="activity" className="space-y-4">
                <h3 className="font-semibold text-sm">{isRTL ? 'سجل النشاط' : 'Activity Log'}</h3>
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
                    {isRTL ? 'لا يوجد سجل نشاط' : 'No activity log'}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="actions" className="space-y-4">
                <h3 className="font-semibold text-sm">{isRTL ? 'إدارة الحساب' : 'Account Management'}</h3>
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
                        <p className="text-sm font-medium text-green-700">{isRTL ? 'تفعيل الحساب' : 'Activate Account'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'إعادة تفعيل حساب المعلم' : 'Re-activate the teacher account'}</p>
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
                        <p className="text-sm font-medium text-yellow-700">{isRTL ? 'تعليق الحساب' : 'Suspend Account'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'تعليق مؤقت لحساب المعلم' : 'Temporarily suspend the account'}</p>
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
                        <p className="text-sm font-medium text-gray-700">{isRTL ? 'إغلاق الحساب' : 'Close Account'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'إغلاق الحساب بشكل دائم' : 'Permanently close the account'}</p>
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
                      <p className="text-sm font-medium">{isRTL ? 'إعادة تعيين كلمة المرور' : 'Reset Password'}</p>
                      <p className="text-xs text-muted-foreground">{isRTL ? 'إنشاء كلمة مرور جديدة' : 'Generate a new password'}</p>
                    </div>
                  </Button>
                </div>
                <div className="border-t pt-4 mt-4">
                  <h3 className="font-semibold text-sm text-red-600 mb-3">{isRTL ? 'منطقة الخطر' : 'Danger Zone'}</h3>
                  <Button
                    variant="outline"
                    className="justify-start h-auto py-3 border-red-200 hover:bg-red-50 w-full"
                    onClick={handleDelete}
                    disabled={!!actionLoading}
                  >
                    <Trash2 className="h-4 w-4 me-2 text-red-500" />
                    <div className="text-start">
                      <p className="text-sm font-medium text-red-600">{isRTL ? 'حذف المعلم نهائياً' : 'Delete Teacher Permanently'}</p>
                      <p className="text-xs text-muted-foreground">{isRTL ? 'لا يمكن التراجع عن هذا الإجراء' : 'This action cannot be undone'}</p>
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
