import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { toast } from 'sonner';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import {
  User, Edit, Save, X, Phone, Mail, Hash, Calendar, MapPin,
  Key, UserX, UserCheck, Loader2, Copy, Eye, EyeOff, History,
  AlertTriangle, Heart, GraduationCap, Shield, MessageSquare, Send, Bell,
  Trash2, Settings2
} from 'lucide-react';

export default function ParentProfileDialog({ open, onClose, parent, onRefresh }) {
  const { api } = useAuth();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();
  const { isRTL } = useTheme();
  const [activeTab, setActiveTab] = useState('info');
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({});
  const [credForm, setCredForm] = useState({ new_email: '', new_password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const [messageForm, setMessageForm] = useState({ subject: '', body: '', message_type: 'general' });
  const [sendingMessage, setSendingMessage] = useState(false);

  const fetchProfile = useCallback(async () => {
    if (!parent?.id) return;
    setLoading(true);
    try {
      const res = await api.get(`/principal/parent/${parent.id}/full-profile`);
      setProfile(res.data?.profile);
    } catch (e) {
      setProfile(null);
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل تحميل الملف الشخصي' : 'Failed to load profile'));
    } finally {
      setLoading(false);
    }
  }, [parent?.id, api]);

  useEffect(() => {
    if (open && parent?.id) {
      setActiveTab('info');
      setEditing(false);
      fetchProfile();
    }
  }, [open, parent?.id, fetchProfile]);

  const handleSaveBasicInfo = async () => {
    setSaving(true);
    try {
      await api.put(`/principal/parent/${parent.id}/basic-info`, formData);
      toast.success(isRTL ? 'تم تحديث البيانات بنجاح' : 'Profile updated');
      setEditing(false);
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
      const res = await api.put(`/principal/parent/${parent.id}/credentials`, credForm);
      if (res.data?.account_created) {
        toast.success(isRTL ? 'تم إنشاء حساب دخول لولي الأمر بنجاح' : 'Login account created successfully');
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
    } catch {
      nassaqError(isRTL ? 'فشل التوليد' : 'Generation failed');
    }
  };

  const handleStatusChange = async (newStatus) => {
    setActionLoading(newStatus);
    try {
      await api.put(`/principal/parent/${parent.id}/status`, { status: newStatus });
      toast.success(isRTL ? 'تم تغيير الحالة بنجاح' : 'Status updated');
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
      isRTL ? 'هل أنت متأكد من حذف ولي الأمر نهائياً؟ لا يمكن التراجع عن هذا الإجراء.' : 'Are you sure you want to permanently delete this parent? This action cannot be undone.',
      async () => {
        setActionLoading('delete');
        try {
          await api.delete(`/parents/${parent.id}`);
          toast.success(isRTL ? 'تم حذف ولي الأمر بنجاح' : 'Parent deleted successfully');
          onClose?.();
          onRefresh?.();
        } catch (e) {
          nassaqError(e.response?.data?.detail || (isRTL ? 'فشل حذف ولي الأمر' : 'Failed to delete parent'));
        } finally {
          setActionLoading('');
        }
      },
      { title: isRTL ? 'تأكيد الحذف النهائي' : 'Confirm Permanent Delete', confirmText: isRTL ? 'نعم، احذف نهائياً' : 'Yes, Delete Permanently', cancelText: isRTL ? 'إلغاء' : 'Cancel' }
    );
  };

  const handleSendMessage = async () => {
    if (!messageForm.body.trim()) return;
    setSendingMessage(true);
    try {
      await api.post(`/principal/parent/${parent.id}/send-message`, messageForm);
      toast.success(isRTL ? 'تم إرسال الرسالة بنجاح' : 'Message sent');
      setMessageForm({ subject: '', body: '', message_type: 'general' });
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل الإرسال' : 'Send failed'));
    } finally {
      setSendingMessage(false);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${isRTL ? 'تم نسخ' : 'Copied'} ${label}`);
  };

  const startEdit = () => {
    setFormData({ ...profile?.basic_info, ...profile?.contact_info });
    setEditing(true);
  };

  if (!parent) return null;

  const p = profile;
  const status = p?.user_account?.status || 'active';
  const statusColors = {
    active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    suspended: 'bg-red-100 text-red-700',
    closed: 'bg-red-200 text-red-800'
  };
  const statusLabels = { active: isRTL ? 'نشط' : 'Active', suspended: isRTL ? 'معلق' : 'Suspended', inactive: isRTL ? 'غير نشط' : 'Inactive', closed: isRTL ? 'مغلق' : 'Closed' };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto p-0">
        <div className="bg-gradient-to-r from-amber-500 to-orange-600 p-5 text-white rounded-t-lg">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center text-2xl font-bold">
              {(p?.basic_info?.full_name || parent.full_name || '').charAt(0)}
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold">{p?.basic_info?.full_name || parent.full_name}</h2>
              <p className="text-amber-100 text-sm">{parent.relationship || (isRTL ? 'ولي أمر' : 'Parent/Guardian')}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge className={`text-[10px] ${statusColors[status] || statusColors.active}`}>{statusLabels[status]}</Badge>
                <Badge className="text-[10px] bg-white/20 text-white border-0">
                  <Heart className="h-2.5 w-2.5 me-1" />{p?.children?.length || parent.children_count || 0} {isRTL ? 'أبناء' : 'children'}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-amber-600" /></div>
          ) : (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid grid-cols-6 w-full mb-4">
                <TabsTrigger value="info" className="text-xs"><User className="h-3.5 w-3.5 me-1" />{isRTL ? 'الملف' : 'Profile'}</TabsTrigger>
                <TabsTrigger value="children" className="text-xs"><Heart className="h-3.5 w-3.5 me-1" />{isRTL ? 'الأبناء' : 'Children'}</TabsTrigger>
                <TabsTrigger value="credentials" className="text-xs"><Key className="h-3.5 w-3.5 me-1" />{isRTL ? 'الدخول' : 'Login'}</TabsTrigger>
                <TabsTrigger value="communication" className="text-xs"><MessageSquare className="h-3.5 w-3.5 me-1" />{isRTL ? 'تواصل' : 'Contact'}</TabsTrigger>
                <TabsTrigger value="activity" className="text-xs"><History className="h-3.5 w-3.5 me-1" />{isRTL ? 'النشاط' : 'Activity'}</TabsTrigger>
                <TabsTrigger value="actions" className="text-xs"><Settings2 className="h-3.5 w-3.5 me-1" />{isRTL ? 'إجراءات' : 'Actions'}</TabsTrigger>
              </TabsList>

              <TabsContent value="info" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold text-sm">{isRTL ? 'البيانات الأساسية والتواصل' : 'Basic & Contact Info'}</h3>
                  {!editing ? (
                    <Button size="sm" variant="outline" onClick={startEdit}><Edit className="h-3.5 w-3.5 me-1" />{isRTL ? 'تعديل' : 'Edit'}</Button>
                  ) : (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveBasicInfo} disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5 me-1" />}{isRTL ? 'حفظ' : 'Save'}</Button>
                      <Button size="sm" variant="outline" onClick={() => setEditing(false)}><X className="h-3.5 w-3.5" /></Button>
                    </div>
                  )}
                </div>
                {editing ? (
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { key: 'full_name', label: isRTL ? 'الاسم الكامل' : 'Full Name', icon: User },
                      { key: 'national_id', label: isRTL ? 'رقم الهوية' : 'National ID', icon: Hash },
                      { key: 'phone', label: isRTL ? 'الجوال' : 'Phone', icon: Phone },
                      { key: 'alt_phone', label: isRTL ? 'جوال بديل' : 'Alt Phone', icon: Phone },
                      { key: 'email', label: isRTL ? 'البريد' : 'Email', icon: Mail },
                      { key: 'address', label: isRTL ? 'العنوان' : 'Address', icon: MapPin },
                      { key: 'city', label: isRTL ? 'المدينة' : 'City', icon: MapPin },
                      { key: 'country', label: isRTL ? 'الدولة' : 'Country', icon: MapPin },
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
                      { label: isRTL ? 'جوال بديل' : 'Alt Phone', value: p?.contact_info?.alt_phone, icon: Phone },
                      { label: isRTL ? 'البريد' : 'Email', value: p?.contact_info?.email || parent.email, icon: Mail },
                      { label: isRTL ? 'العنوان' : 'Address', value: p?.contact_info?.address, icon: MapPin },
                      { label: isRTL ? 'المدينة' : 'City', value: p?.contact_info?.city, icon: MapPin },
                      { label: isRTL ? 'الدولة' : 'Country', value: p?.contact_info?.country, icon: MapPin },
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

              <TabsContent value="children" className="space-y-4">
                <h3 className="font-semibold text-sm">{isRTL ? 'الأبناء المرتبطون' : 'Linked Children'}</h3>
                {p?.children?.length > 0 ? (
                  <div className="space-y-2">
                    {p.children.map((child, i) => (
                      <Card key={i} className="border-amber-200/30 hover:shadow-sm transition-shadow">
                        <CardContent className="p-3 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-sm font-bold text-blue-700 dark:text-blue-400">
                              {(child.full_name || '').charAt(0)}
                            </div>
                            <div>
                              <p className="font-medium text-sm">{child.full_name}</p>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                {child.class_name && <span>{child.class_name}</span>}
                                {child.grade_level && <span>• {child.grade_level}</span>}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {child.relationship && <Badge variant="outline" className="text-[10px]">{child.relationship === 'father' ? (isRTL ? 'أب' : 'Father') : child.relationship === 'mother' ? (isRTL ? 'أم' : 'Mother') : child.relationship}</Badge>}
                            {child.is_primary && <Badge className="text-[10px] bg-amber-100 text-amber-700">{isRTL ? 'أساسي' : 'Primary'}</Badge>}
                            <Badge className={`text-[10px] ${child.status === 'active' || !child.status ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                              {child.status === 'active' || !child.status ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
                            </Badge>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    <GraduationCap className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    {isRTL ? 'لا يوجد أبناء مرتبطون' : 'No linked children'}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="credentials" className="space-y-4">
                <h3 className="font-semibold text-sm">{isRTL ? 'إدارة بيانات الدخول' : 'Login Credentials'}</h3>
                {!p?.user_account?.id ? (
                  <Card className="border-amber-200 bg-amber-50/50"><CardContent className="p-4 space-y-3">
                    <div className="flex items-center gap-2 text-amber-700">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span className="font-medium text-sm">{isRTL ? 'لم يتم إنشاء حساب دخول بعد' : 'No login account created yet'}</span>
                    </div>
                    <p className="text-xs text-amber-600">{isRTL ? 'ولي الأمر لديه ملف تعريفي فقط ولا يمكنه تسجيل الدخول حتى يتم إنشاء حساب له.' : 'This parent only has a profile record and cannot log in until an account is created.'}</p>
                    <div className="border-t border-amber-200 pt-3 space-y-3">
                      <div className="space-y-1">
                        <Label className="text-xs">{isRTL ? 'البريد الإلكتروني' : 'Email'}</Label>
                        <Input type="email" value={credForm.new_email || parent.email || ''} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" />
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
                      <span className="font-medium">{p?.user_account?.email || parent.email || '-'}</span>
                      {(p?.user_account?.email || parent.email) && (
                        <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => copyToClipboard(p?.user_account?.email || parent.email, isRTL ? 'البريد' : 'Email')}>
                          <Copy className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="border-t pt-3 space-y-3">
                    <div className="space-y-1">
                      <Label className="text-xs">{isRTL ? 'البريد الجديد (اختياري)' : 'New Email (optional)'}</Label>
                      <Input type="email" value={credForm.new_email} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" />
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
                      <Button size="sm" variant="outline" onClick={handleGeneratePassword} className="text-amber-600">
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

              <TabsContent value="communication" className="space-y-4">
                <h3 className="font-semibold text-sm">{isRTL ? 'إرسال رسالة' : 'Send Message'}</h3>
                <Card><CardContent className="p-4 space-y-3">
                  <div className="space-y-1">
                    <Label className="text-xs">{isRTL ? 'العنوان' : 'Subject'}</Label>
                    <Input value={messageForm.subject} onChange={(e) => setMessageForm(p => ({ ...p, subject: e.target.value }))} className="h-8 text-sm" />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">{isRTL ? 'نوع الرسالة' : 'Type'}</Label>
                    <div className="flex gap-2 flex-wrap">
                      {[
                        { val: 'academic', label: isRTL ? 'تعليمي' : 'Academic' },
                        { val: 'behaviour', label: isRTL ? 'سلوكي' : 'Behaviour' },
                        { val: 'performance', label: isRTL ? 'أداء' : 'Performance' },
                        { val: 'general', label: isRTL ? 'عام' : 'General' },
                      ].map(({ val, label }) => (
                        <Badge key={val} variant={messageForm.message_type === val ? 'default' : 'outline'}
                          className="cursor-pointer text-xs" onClick={() => setMessageForm(p => ({ ...p, message_type: val }))}>
                          {label}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">{isRTL ? 'نص الرسالة' : 'Message'}</Label>
                    <textarea value={messageForm.body} onChange={(e) => setMessageForm(p => ({ ...p, body: e.target.value }))}
                      className="w-full border rounded-lg p-2 text-sm h-24 resize-none bg-background" />
                  </div>
                  <Button size="sm" onClick={handleSendMessage} disabled={sendingMessage || !messageForm.body.trim()}>
                    {sendingMessage ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Send className="h-3.5 w-3.5 me-1" />}{isRTL ? 'إرسال' : 'Send'}
                  </Button>
                </CardContent></Card>

                {p?.notifications?.length > 0 && (
                  <>
                    <h3 className="font-semibold text-sm">{isRTL ? 'الإشعارات الأخيرة' : 'Recent Notifications'}</h3>
                    <div className="space-y-2 max-h-[200px] overflow-y-auto">
                      {p.notifications.map((n, i) => (
                        <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-muted/30 text-sm">
                          <Bell className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                          <div>
                            <p className="text-xs font-medium">{n.subject || n.body?.slice(0, 50)}</p>
                            <p className="text-[10px] text-muted-foreground">{n.created_at ? new Date(n.created_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US') : ''}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
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
                  {status !== 'active' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-green-200 hover:bg-green-50"
                      onClick={() => handleStatusChange('active')}
                      disabled={!!actionLoading}
                    >
                      <UserCheck className="h-4 w-4 me-2 text-green-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-green-700">{isRTL ? 'تفعيل الحساب' : 'Activate Account'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'إعادة تفعيل حساب ولي الأمر' : 'Re-activate the parent account'}</p>
                      </div>
                      {actionLoading === 'active' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>
                  )}
                  {status !== 'suspended' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-yellow-200 hover:bg-yellow-50"
                      onClick={() => handleStatusChange('suspended')}
                      disabled={!!actionLoading}
                    >
                      <UserX className="h-4 w-4 me-2 text-yellow-600" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-yellow-700">{isRTL ? 'تعليق الحساب' : 'Suspend Account'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'تعليق مؤقت لحساب ولي الأمر' : 'Temporarily suspend the account'}</p>
                      </div>
                      {actionLoading === 'suspended' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>
                  )}
                  {status !== 'closed' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-gray-200 hover:bg-gray-50"
                      onClick={() => nassaqConfirm(isRTL ? 'هل أنت متأكد من إغلاق الحساب؟' : 'Are you sure you want to close this account?', () => handleStatusChange('closed'), { title: isRTL ? 'تأكيد الإغلاق' : 'Confirm Close', confirmText: isRTL ? 'نعم، أغلق' : 'Yes, Close', cancelText: isRTL ? 'إلغاء' : 'Cancel' })}
                      disabled={!!actionLoading}
                    >
                      <X className="h-4 w-4 me-2 text-gray-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-gray-700">{isRTL ? 'إغلاق الحساب' : 'Close Account'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'إغلاق الحساب بشكل دائم' : 'Permanently close the account'}</p>
                      </div>
                      {actionLoading === 'closed' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
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
                      <p className="text-sm font-medium text-red-600">{isRTL ? 'حذف ولي الأمر نهائياً' : 'Delete Parent Permanently'}</p>
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
