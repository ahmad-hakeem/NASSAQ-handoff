import React from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Avatar, AvatarFallback } from '../ui/avatar';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../ui/dialog';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '../ui/sheet';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select';
import {
  Edit, Trash2, Lock, Unlock, Bell, Send, Key,
  AlertTriangle, Archive, CheckCircle2, XCircle,
  Eye, QrCode, Copy, Check, FileText, Info
} from 'lucide-react';
import { getRoleInfo, formatDate, formatTimeAgo } from './constants';
import { USER_ROLES } from './constants';
import { APPROVAL_TYPE_CONFIG } from './approvalConfig';

export function UserDetailsDialog({ user, onClose, onEdit, onSuspend, onNotify }) {
  if (!user) return null;
  const roleInfo = getRoleInfo(user.role);

  return (
    <Dialog open={!!user} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-3 flex-row-reverse justify-end">
            {user.full_name}
            <Avatar className="h-12 w-12">
              <AvatarFallback className="bg-brand-navy text-white">
                {user.full_name?.charAt(0)}
              </AvatarFallback>
            </Avatar>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="text-right">
              <p className="text-sm text-muted-foreground">البريد الإلكتروني</p>
              <p className="font-medium" dir="ltr">{user.email}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">الهاتف</p>
              <p className="font-medium" dir="ltr">{user.phone || '-'}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">الدور</p>
              <Badge className={`${roleInfo.color} text-white`}>{roleInfo.name}</Badge>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">الحالة</p>
              <Badge className={user.is_active !== false ? 'bg-green-500' : 'bg-red-500'}>
                {user.is_active !== false ? 'نشط' : 'موقوف'}
              </Badge>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">المدرسة</p>
              <p className="font-medium">{user.school_name || '-'}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">القسم</p>
              <p className="font-medium">{user.department || '-'}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">آخر دخول</p>
              <p className="font-medium">{formatTimeAgo(user.last_login)}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">تاريخ الإنشاء</p>
              <p className="font-medium">{formatDate(user.created_at)}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">حالة AI</p>
              <Badge className={user.ai_enabled ? 'bg-purple-500' : 'bg-gray-400'}>
                {user.ai_enabled ? 'مفعّل' : 'غير مفعّل'}
              </Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 pt-4 border-t">
            <Button variant="outline" size="sm" onClick={() => { onClose(); onEdit(user); }}>
              <Edit className="h-4 w-4 ms-2" />تعديل البيانات
            </Button>
            <Button variant="outline" size="sm">
              <Key className="h-4 w-4 ms-2" />إعادة تعيين كلمة المرور
            </Button>
            <Button variant="outline" size="sm" onClick={() => { onClose(); onNotify(user); }}>
              <Bell className="h-4 w-4 ms-2" />إرسال إشعار
            </Button>
            <Button variant="outline" size="sm" className="text-red-600" onClick={() => { onClose(); onSuspend(user); }}>
              {user.is_active !== false ? (
                <><Lock className="h-4 w-4 ms-2" />تعليق الحساب</>
              ) : (
                <><Unlock className="h-4 w-4 ms-2" />تفعيل الحساب</>
              )}
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>إغلاق</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function SuspendDialog({ user, onClose, onConfirm }) {
  return (
    <Dialog open={!!user} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-yellow-600">
            <AlertTriangle className="h-5 w-5" />
            {user?.is_active !== false ? 'تأكيد تعليق الحساب' : 'تأكيد تفعيل الحساب'}
          </DialogTitle>
          <DialogDescription className="text-right">
            {user?.is_active !== false
              ? `هل أنت متأكد من تعليق حساب "${user?.full_name}"؟ لن يتمكن المستخدم من تسجيل الدخول.`
              : `هل أنت متأكد من إعادة تفعيل حساب "${user?.full_name}"؟`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-row-reverse gap-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button variant={user?.is_active !== false ? "destructive" : "default"} onClick={() => onConfirm(user)}>
            {user?.is_active !== false ? (
              <><Lock className="h-4 w-4 ms-2" />تعليق</>
            ) : (
              <><Unlock className="h-4 w-4 ms-2" />تفعيل</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function DeleteDialog({ user, onClose, onConfirm }) {
  return (
    <Dialog open={!!user} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-red-600">
            <Trash2 className="h-5 w-5" />تأكيد الحذف
          </DialogTitle>
          <DialogDescription className="text-right">
            هل أنت متأكد من حذف حساب <strong>{user?.full_name}</strong>؟
            <br /><span className="text-muted-foreground text-sm">سيتم نقل الحساب إلى الأرشيف ولن يتم حذفه نهائياً.</span>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-row-reverse gap-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button variant="destructive" onClick={() => onConfirm(user)}>
            <Archive className="h-4 w-4 ms-2" />أرشفة الحساب
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function NotificationDialog({ user, form, setForm, onClose, onSend }) {
  return (
    <Dialog open={!!user} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end">
            <Bell className="h-5 w-5 text-blue-600" />إرسال إشعار إلى {user?.full_name}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-right block">نوع الإشعار</Label>
            <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
              <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="system">إشعار داخل النظام</SelectItem>
                <SelectItem value="email">بريد إلكتروني</SelectItem>
                <SelectItem value="push">إشعار فوري</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-right block">العنوان</Label>
            <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-xl text-right" placeholder="عنوان الإشعار" />
          </div>
          <div className="space-y-2">
            <Label className="text-right block">الرسالة</Label>
            <Textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className="rounded-xl text-right min-h-[100px]" placeholder="اكتب رسالتك هنا..." />
          </div>
        </div>
        <DialogFooter className="flex-row-reverse gap-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button onClick={() => onSend(user)}><Send className="h-4 w-4 ms-2" />إرسال</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ApprovalConfirmDialog({ data, onClose, onConfirm }) {
  if (!data) return null;
  const config = APPROVAL_TYPE_CONFIG[data.requestType];
  const fields = config?.confirmFields(data.request) || [];

  return (
    <Dialog open={!!data} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-green-600">
            <CheckCircle2 className="h-5 w-5" />{config?.approveTitle}
          </DialogTitle>
          <DialogDescription className="text-right">{config?.approveDesc}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="p-4 bg-muted/30 rounded-xl space-y-2 text-right">
            {fields.map((field, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <span dir={field.dir || undefined} className={idx === 0 ? 'font-bold' : ''}>{field.value}</span>
                <span className="text-muted-foreground">{field.label}:</span>
              </div>
            ))}
          </div>
          <p className="text-sm text-muted-foreground text-center">{config?.approveNote}</p>
        </div>
        <DialogFooter className="flex-row-reverse gap-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button className="bg-green-600 hover:bg-green-700" onClick={() => { onConfirm(data.request, data.requestType); onClose(); }}>
            <CheckCircle2 className="h-4 w-4 ms-2" />تأكيد الموافقة
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ApprovalSuccessDialog({ data, onClose, copyToClipboard }) {
  if (!data) return null;
  const config = APPROVAL_TYPE_CONFIG[data.requestType];
  const credFields = config?.credentialFields(data) || [];

  return (
    <Dialog open={!!data} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-green-600">
            <CheckCircle2 className="h-6 w-6" />{config?.successTitle}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="p-4 bg-green-50 rounded-xl border border-green-200">
            <h4 className="font-bold text-green-800 mb-2 text-right">{config?.successSubtitle}</h4>
            <div className="space-y-2 text-sm">
              {credFields.map((field, idx) => (
                <div key={idx} className="flex items-center justify-between">
                  <Button variant="ghost" size="sm" onClick={() => copyToClipboard(field.value)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                  <div className="text-right">
                    <span className="text-muted-foreground">{field.label}: </span>
                    <span className={`font-mono ${field.highlight ? 'font-bold text-brand-navy' : ''}`} dir={field.dir || undefined}>{field.value}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          {config?.showQrCode && (
            <div className="p-4 bg-blue-50 rounded-xl border border-blue-200 text-center">
              <QrCode className="h-16 w-16 mx-auto text-blue-600 mb-2" />
              <p className="text-sm text-blue-700">QR Code</p>
            </div>
          )}
          <p className="text-sm text-muted-foreground text-center">يمكنك نسخ البيانات وإرسالها عبر البريد أو الرسائل</p>
        </div>
        <DialogFooter>
          <Button onClick={onClose} className="w-full"><Check className="h-4 w-4 ms-2" />تم</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function RejectDialog({ data, rejectionReason, setRejectionReason, onClose, onConfirm }) {
  if (!data) return null;
  const config = APPROVAL_TYPE_CONFIG[data.requestType];

  return (
    <Dialog open={!!data} onOpenChange={() => { onClose(); setRejectionReason(''); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-red-600">
            <XCircle className="h-5 w-5" />{config?.rejectTitle(data.request)}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-right block">سبب الرفض *</Label>
            <Textarea value={rejectionReason} onChange={(e) => setRejectionReason(e.target.value)} className="rounded-xl text-right min-h-[100px]" placeholder="اكتب سبب رفض الطلب..." />
            <div className="flex flex-wrap gap-2 mt-2">
              {config?.quickReasons.map((reason, idx) => (
                <Button key={idx} variant="outline" size="sm" onClick={() => setRejectionReason(reason)}>{reason}</Button>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter className="flex-row-reverse gap-2">
          <Button variant="outline" onClick={() => { onClose(); setRejectionReason(''); }}>إلغاء</Button>
          <Button variant="destructive" onClick={() => onConfirm(data.request, data.requestType)} disabled={!rejectionReason.trim()}>
            <XCircle className="h-4 w-4 ms-2" />رفض وإرسال
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function MoreInfoDialog({ request, message, setMessage, onClose, onConfirm }) {
  return (
    <Dialog open={!!request} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-blue-600">
            <Info className="h-5 w-5" />طلب معلومات إضافية من {request?.full_name}
          </DialogTitle>
          <DialogDescription className="text-right">سيتم إرسال رسالة تطلب تزويدكم بالمعلومات المحددة أدناه</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-right block">المعلومات المطلوبة *</Label>
            <Textarea value={message} onChange={(e) => setMessage(e.target.value)} className="rounded-xl text-right min-h-[100px]" placeholder="مثال: يرجى رفع صورة الهوية وتحديد المادة التي تدرسها..." />
            <div className="flex flex-wrap gap-2 mt-2">
              <Button variant="outline" size="sm" onClick={() => setMessage('يرجى رفع صورة الهوية')}>رفع صورة الهوية</Button>
              <Button variant="outline" size="sm" onClick={() => setMessage('يرجى تأكيد المادة التي تدرسها')}>تأكيد المادة</Button>
              <Button variant="outline" size="sm" onClick={() => setMessage('يرجى تحديد المدرسة التي تعمل بها')}>تحديد المدرسة</Button>
            </div>
          </div>
        </div>
        <DialogFooter className="flex-row-reverse gap-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button onClick={() => onConfirm(request)} disabled={!message.trim() || message.trim().length < 10}>
            <Send className="h-4 w-4 ms-2" />إرسال الطلب
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function RequestDetailsDialog({ request, onClose }) {
  if (!request) return null;

  return (
    <Dialog open={!!request} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" dir="rtl">
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2 flex-row-reverse justify-end">
            <FileText className="h-5 w-5 text-brand-navy" />تفاصيل الطلب
          </DialogTitle>
          <DialogDescription className="text-right">
            {request.account_type === 'teacher' ? 'طلب تسجيل معلم مستقل' :
             request.account_type === 'school' ? 'طلب تسجيل مدرسة' : 'طلب تسجيل'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <Badge className={
              request.status === 'approved' ? 'bg-green-100 text-green-800' :
              request.status === 'rejected' ? 'bg-red-100 text-red-800' :
              request.status === 'under_review' ? 'bg-orange-100 text-orange-800' :
              request.status === 'info_required' ? 'bg-blue-100 text-blue-800' :
              request.status === 'archived' ? 'bg-gray-100 text-gray-800' :
              'bg-yellow-100 text-yellow-800'
            }>
              {request.status === 'approved' ? 'معتمد' :
               request.status === 'rejected' ? 'مرفوض' :
               request.status === 'under_review' ? 'تحت المراجعة' :
               request.status === 'info_required' ? 'بانتظار معلومات' :
               request.status === 'archived' ? 'مؤرشف' :
               request.status === 'cancelled' ? 'ملغي' :
               'قيد الاعتماد'}
            </Badge>
            <span className="text-xs text-muted-foreground">{request.id?.substring(0, 8)}…</span>
          </div>

          <RequestDetailsContent request={request} />

          {request.rejection_reason && (
            <div className="p-4 border border-red-200 rounded-lg">
              <h4 className="text-sm font-bold text-red-700 mb-2">سبب الرفض</h4>
              <p className="text-sm">{request.rejection_reason}</p>
              {request.rejected_by_name && (
                <p className="text-xs text-muted-foreground mt-2">بواسطة: {request.rejected_by_name} — {formatDate(request.rejected_at)}</p>
              )}
            </div>
          )}

          {request.review_history?.length > 0 && (
            <div className="p-4 border rounded-lg">
              <h4 className="text-sm font-bold mb-2">سجل المراجعة</h4>
              <div className="space-y-3">
                {request.review_history.map((entry, idx) => (
                  <div key={idx} className="flex items-start gap-3 text-sm border-b pb-2 last:border-0">
                    <div className="flex-1">
                      <div className="font-medium">{entry.action_by_name || 'النظام'}</div>
                      <div className="text-muted-foreground text-xs">
                        {entry.action?.replace(/_/g, ' ')} — {formatDate(entry.timestamp)}
                      </div>
                      {entry.details?.reason && <div className="text-xs mt-1">{entry.details.reason}</div>}
                      {entry.details?.notes && <div className="text-xs mt-1">{entry.details.notes}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>إغلاق</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RequestDetailsContent({ request }) {
  return (
    <div className="p-4 border rounded-lg">
      <h4 className="text-sm font-bold mb-3">بيانات المتقدم</h4>
      <div className="grid grid-cols-2 gap-3 text-sm">
        {request.full_name && (
          <div><span className="text-muted-foreground">الاسم:</span> <span className="font-medium">{request.full_name}</span></div>
        )}
        {request.school_name && (
          <div><span className="text-muted-foreground">المدرسة:</span> <span className="font-medium">{request.school_name}</span></div>
        )}
        {(request.email || request.school_email) && (
          <div><span className="text-muted-foreground">البريد:</span> <span className="font-medium" dir="ltr">{request.school_email || request.email}</span></div>
        )}
        {(request.phone || request.school_phone) && (
          <div><span className="text-muted-foreground">الهاتف:</span> <span className="font-medium" dir="ltr">{request.school_phone || request.phone}</span></div>
        )}
        {request.national_id && (
          <div><span className="text-muted-foreground">رقم الهوية:</span> <span className="font-medium" dir="ltr">{request.national_id}</span></div>
        )}
        {request.subject && (
          <div><span className="text-muted-foreground">المادة:</span> <span className="font-medium">{request.subject}</span></div>
        )}
        {request.education_level && (
          <div><span className="text-muted-foreground">المرحلة:</span> <span className="font-medium">{request.education_level}</span></div>
        )}
        {request.school_city && (
          <div><span className="text-muted-foreground">المدينة:</span> <span className="font-medium">{request.school_city}</span></div>
        )}
        {request.created_at && (
          <div><span className="text-muted-foreground">تاريخ الطلب:</span> <span className="font-medium">{formatDate(request.created_at)}</span></div>
        )}
      </div>
    </div>
  );
}

export function EditUserSheet({ user, onClose, onSave, api, fetchUsers }) {
  const [editRole, setEditRole] = React.useState(user?.role || '');

  React.useEffect(() => {
    if (user) setEditRole(user.role || '');
  }, [user]);

  if (!user) return null;

  return (
    <Sheet open={!!user} onOpenChange={onClose}>
      <SheetContent side="left" className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="font-cairo flex items-center gap-2">
            <Edit className="h-5 w-5 text-brand-turquoise" />تعديل بيانات المستخدم
          </SheetTitle>
        </SheetHeader>
        <div className="space-y-6 py-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>الاسم الكامل</Label>
              <Input defaultValue={user.full_name} className="rounded-xl" id="edit-user-name" />
            </div>
            <div className="space-y-2">
              <Label>البريد الإلكتروني</Label>
              <Input defaultValue={user.email} className="rounded-xl" id="edit-user-email" />
            </div>
            <div className="space-y-2">
              <Label>رقم الهاتف</Label>
              <Input defaultValue={user.phone} className="rounded-xl" id="edit-user-phone" />
            </div>
            <div className="space-y-2">
              <Label>الدور</Label>
              <Select value={editRole} onValueChange={setEditRole}>
                <SelectTrigger className="rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {USER_ROLES.map((role) => (
                    <SelectItem key={role.id} value={role.id}>{role.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              className="flex-1 bg-brand-navy hover:bg-brand-navy/90 rounded-xl"
              onClick={async () => {
                const name = document.getElementById('edit-user-name')?.value;
                const email = document.getElementById('edit-user-email')?.value;
                const phone = document.getElementById('edit-user-phone')?.value;

                try {
                  await api.patch(`/users/${user.id}`, {
                    full_name: name,
                    email: email,
                    phone: phone,
                    role: editRole || undefined,
                  });
                  onSave('تم تحديث بيانات المستخدم بنجاح');
                  fetchUsers();
                  onClose();
                } catch (error) {
                  console.error('Error updating user:', error);
                  onSave(null, error?.response?.data?.detail || 'فشل في تحديث بيانات المستخدم');
                }
              }}
            >
              حفظ التغييرات
            </Button>
            <Button variant="outline" className="rounded-xl" onClick={onClose}>إلغاء</Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
