import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { toast } from 'sonner';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { getApiErrorMessage } from '../../utils/apiError';
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
  const { t } = useTranslation();
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
      nassaqError(getApiErrorMessage(e) || (t('failedToLoadProfile')));
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
      toast.success(t('profileUpdated'));
      setEditing(false);
      fetchProfile();
      onRefresh?.();
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || (t('updateFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCredentials = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/principal/parent/${parent.id}/credentials`, credForm);
      if (res.data?.account_created) {
        toast.success(t('loginAccountCreatedSuccessfully'));
      } else {
        toast.success(t('credentialsUpdated'));
      }
      setCredForm({ new_email: '', new_password: '' });
      fetchProfile();
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || (t('updateFailed')));
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
      nassaqError(t('generationFailed'));
    }
  };

  const handleStatusChange = async (newStatus) => {
    setActionLoading(newStatus);
    try {
      await api.put(`/principal/parent/${parent.id}/status`, { status: newStatus });
      toast.success(t('statusUpdated'));
      if (newStatus === 'closed') {
        onRefresh?.();
        onClose?.();
      } else {
        fetchProfile();
        onRefresh?.();
      }
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || (t('actionFailed')));
    } finally {
      setActionLoading('');
    }
  };

  const handleDelete = () => {
    nassaqConfirm(
      t('areYouSureYouWantToPermanentlyDeleteThisParentThis'),
      async () => {
        setActionLoading('delete');
        try {
          await api.delete(`/parents/${parent.id}`);
          toast.success(t('parentDeletedSuccessfully'));
          onClose?.();
          onRefresh?.();
        } catch (e) {
          nassaqError(getApiErrorMessage(e) || (t('failedToDeleteParent')));
        } finally {
          setActionLoading('');
        }
      },
      { title: t('confirmPermanentDelete'), confirmText: t('yesDeletePermanently'), cancelText: t('cancel') }
    );
  };

  const handleSendMessage = async () => {
    if (!messageForm.body.trim()) return;
    setSendingMessage(true);
    try {
      await api.post(`/principal/parent/${parent.id}/send-message`, messageForm);
      toast.success(t('messageSent'));
      setMessageForm({ subject: '', body: '', message_type: 'general' });
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || (t('sendFailed')));
    } finally {
      setSendingMessage(false);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${t('copied')} ${label}`);
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
  const statusLabels = { active: t('active'), suspended: isRTL ? 'معلق' : 'Suspended', inactive: t('inactive'), closed: t('closed') };

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
              <p className="text-amber-100 text-sm">{parent.relationship || (t('parentguardian'))}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge className={`text-[10px] ${statusColors[status] || statusColors.active}`}>{statusLabels[status]}</Badge>
                <Badge className="text-[10px] bg-white/20 text-white border-0">
                  <Heart className="h-2.5 w-2.5 me-1" />{p?.children?.length || parent.children_count || 0} {t('children')}
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
                <TabsTrigger value="info" className="text-xs"><User className="h-3.5 w-3.5 me-1" />{t('profile')}</TabsTrigger>
                <TabsTrigger value="children" className="text-xs"><Heart className="h-3.5 w-3.5 me-1" />{t('children2')}</TabsTrigger>
                <TabsTrigger value="credentials" className="text-xs"><Key className="h-3.5 w-3.5 me-1" />{t('login2')}</TabsTrigger>
                <TabsTrigger value="communication" className="text-xs"><MessageSquare className="h-3.5 w-3.5 me-1" />{t('contact')}</TabsTrigger>
                <TabsTrigger value="activity" className="text-xs"><History className="h-3.5 w-3.5 me-1" />{t('activity')}</TabsTrigger>
                <TabsTrigger value="actions" className="text-xs"><Settings2 className="h-3.5 w-3.5 me-1" />{t('actions')}</TabsTrigger>
              </TabsList>

              <TabsContent value="info" className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold text-sm">{t('basicContactInfo')}</h3>
                  {!editing ? (
                    <Button size="sm" variant="outline" onClick={startEdit}><Edit className="h-3.5 w-3.5 me-1" />{t('edit')}</Button>
                  ) : (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveBasicInfo} disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5 me-1" />}{t('save')}</Button>
                      <Button size="sm" variant="outline" onClick={() => setEditing(false)}><X className="h-3.5 w-3.5" /></Button>
                    </div>
                  )}
                </div>
                {editing ? (
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { key: 'full_name', label: t('fullName'), icon: User },
                      { key: 'national_id', label: t('nationalId'), icon: Hash },
                      { key: 'phone', label: t('phone'), icon: Phone },
                      { key: 'alt_phone', label: t('altPhone'), icon: Phone },
                      { key: 'email', label: t('email'), icon: Mail },
                      { key: 'address', label: t('address'), icon: MapPin },
                      { key: 'city', label: t('city'), icon: MapPin },
                      { key: 'country', label: t('country'), icon: MapPin },
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
                      { label: t('altPhone'), value: p?.contact_info?.alt_phone, icon: Phone },
                      { label: t('email'), value: p?.contact_info?.email || parent.email, icon: Mail },
                      { label: t('address'), value: p?.contact_info?.address, icon: MapPin },
                      { label: t('city'), value: p?.contact_info?.city, icon: MapPin },
                      { label: t('country'), value: p?.contact_info?.country, icon: MapPin },
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

              <TabsContent value="children" className="space-y-4">
                <h3 className="font-semibold text-sm">{t('linkedChildren')}</h3>
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
                            {child.relationship && <Badge variant="outline" className="text-[10px]">{child.relationship === 'father' ? (t('father')) : child.relationship === 'mother' ? (t('mother')) : child.relationship}</Badge>}
                            {child.is_primary && <Badge className="text-[10px] bg-amber-100 text-amber-700">{t('primary')}</Badge>}
                            <Badge className={`text-[10px] ${child.status === 'active' || !child.status ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                              {child.status === 'active' || !child.status ? (t('active')) : (isRTL ? 'معلق' : 'Suspended')}
                            </Badge>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    <GraduationCap className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    {t('noLinkedChildren')}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="credentials" className="space-y-4">
                <h3 className="font-semibold text-sm">{t('loginCredentials')}</h3>
                {!p?.user_account?.id ? (
                  <Card className="border-amber-200 bg-amber-50/50"><CardContent className="p-4 space-y-3">
                    <div className="flex items-center gap-2 text-amber-700">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span className="font-medium text-sm">{t('noLoginAccountCreatedYet')}</span>
                    </div>
                    <p className="text-xs text-amber-600">{t('thisParentOnlyHasAProfileRecordAndCannotLogInUntil')}</p>
                    <div className="border-t border-amber-200 pt-3 space-y-3">
                      <div className="space-y-1">
                        <Label className="text-xs">{t('email2')}</Label>
                        <Input type="email" value={credForm.new_email || parent.email || ''} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" />
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
                      <span className="font-medium">{p?.user_account?.email || parent.email || '-'}</span>
                      {(p?.user_account?.email || parent.email) && (
                        <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => copyToClipboard(p?.user_account?.email || parent.email, t('email'))}>
                          <Copy className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="border-t pt-3 space-y-3">
                    <div className="space-y-1">
                      <Label className="text-xs">{t('newEmailOptional')}</Label>
                      <Input type="email" value={credForm.new_email} onChange={(e) => setCredForm(p => ({ ...p, new_email: e.target.value }))} className="h-8 text-sm" />
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
                      <Button size="sm" variant="outline" onClick={handleGeneratePassword} className="text-amber-600">
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

              <TabsContent value="communication" className="space-y-4">
                <h3 className="font-semibold text-sm">{t('sendMessage')}</h3>
                <Card><CardContent className="p-4 space-y-3">
                  <div className="space-y-1">
                    <Label className="text-xs">{isRTL ? 'العنوان' : 'Subject'}</Label>
                    <Input value={messageForm.subject} onChange={(e) => setMessageForm(p => ({ ...p, subject: e.target.value }))} className="h-8 text-sm" />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">{t('type')}</Label>
                    <div className="flex gap-2 flex-wrap">
                      {[
                        { val: 'academic', label: t('academic') },
                        { val: 'behaviour', label: t('behaviour') },
                        { val: 'performance', label: t('performance') },
                        { val: 'general', label: t('general') },
                      ].map(({ val, label }) => (
                        <Badge key={val} variant={messageForm.message_type === val ? 'default' : 'outline'}
                          className="cursor-pointer text-xs" onClick={() => setMessageForm(p => ({ ...p, message_type: val }))}>
                          {label}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">{t('message')}</Label>
                    <textarea value={messageForm.body} onChange={(e) => setMessageForm(p => ({ ...p, body: e.target.value }))}
                      className="w-full border rounded-lg p-2 text-sm h-24 resize-none bg-background" />
                  </div>
                  <Button size="sm" onClick={handleSendMessage} disabled={sendingMessage || !messageForm.body.trim()}>
                    {sendingMessage ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Send className="h-3.5 w-3.5 me-1" />}{t('send')}
                  </Button>
                </CardContent></Card>

                {p?.notifications?.length > 0 && (
                  <>
                    <h3 className="font-semibold text-sm">{t('recentNotifications')}</h3>
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
                  {status !== 'active' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-green-200 hover:bg-green-50"
                      onClick={() => handleStatusChange('active')}
                      disabled={!!actionLoading}
                    >
                      <UserCheck className="h-4 w-4 me-2 text-green-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-green-700">{t('activateAccount')}</p>
                        <p className="text-xs text-muted-foreground">{t('reactivateTheParentAccount')}</p>
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
                        <p className="text-sm font-medium text-yellow-700">{t('suspendAccount')}</p>
                        <p className="text-xs text-muted-foreground">{t('temporarilySuspendTheAccount')}</p>
                      </div>
                      {actionLoading === 'suspended' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>
                  )}
                  {status !== 'closed' && (
                    <Button
                      variant="outline"
                      className="justify-start h-auto py-3 border-gray-200 hover:bg-gray-50"
                      onClick={() => nassaqConfirm(t('areYouSureYouWantToCloseThisAccount'), () => handleStatusChange('closed'), { title: t('confirmClose'), confirmText: t('yesClose'), cancelText: t('cancel') })}
                      disabled={!!actionLoading}
                    >
                      <X className="h-4 w-4 me-2 text-gray-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-gray-700">{t('closeAccount')}</p>
                        <p className="text-xs text-muted-foreground">{t('permanentlyCloseTheAccount')}</p>
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
                      <p className="text-sm font-medium text-red-600">{t('deleteParentPermanently')}</p>
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
