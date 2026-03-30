import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  FileText,
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
  User,
  Mail,
  Phone,
  Building2,
  Eye,
  Check,
  X,
  School,
  GraduationCap,
  MapPin,
  Users,
  Copy,
} from 'lucide-react';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

export const TeacherRequestsPage = () => {
  const { api } = useAuth();
  const { isRTL, isDark } = useTheme();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);
  const [approving, setApproving] = useState(false);
  const [credentialsDialog, setCredentialsDialog] = useState(null);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const fetchRequests = async () => {
    setLoading(true);
    try {
      const [teacherRes, registrationRes] = await Promise.allSettled([
        api.get('/teacher-registration/requests'),
        api.get('/registration-requests')
      ]);

      let all = [];

      if (teacherRes.status === 'fulfilled' && teacherRes.value?.data?.requests) {
        const teacherRequests = teacherRes.value.data.requests.map(r => ({
          id: r.id,
          display_name: r.full_name,
          email: r.email,
          phone: r.phone,
          school_name: r.school_name || '',
          subject: r.subject,
          experience_years: r.years_of_experience,
          status: r.status,
          submitted_at: r.created_at,
          account_type: 'teacher',
          source: 'teacher_registration',
          ...r
        }));
        all = [...all, ...teacherRequests];
      }

      if (registrationRes.status === 'fulfilled' && registrationRes.value?.data?.requests) {
        const regRequests = registrationRes.value.data.requests.map(r => ({
          id: r.id,
          display_name: r.full_name || r.school_name || '',
          email: r.email || r.school_email || '',
          phone: r.phone || r.school_phone || '',
          school_name: r.school_name || '',
          school_city: r.school_city || '',
          school_address: r.school_address || '',
          student_capacity: r.student_capacity || '',
          subject: r.subject || r.specialization || '',
          experience_years: r.years_of_experience,
          status: r.status,
          submitted_at: r.created_at,
          account_type: r.account_type || 'teacher',
          source: 'registration_requests',
          ...r
        }));
        all = [...all, ...regRequests];
      }

      const seen = new Set();
      const deduped = all.filter(r => {
        if (seen.has(r.id)) return false;
        seen.add(r.id);
        return true;
      });

      deduped.sort((a, b) => {
        const dateA = a.submitted_at || a.created_at || '';
        const dateB = b.submitted_at || b.created_at || '';
        return dateB.localeCompare(dateA);
      });

      setRequests(deduped);
    } catch (error) {
      console.error('Failed to fetch requests:', error);
      nassaqError(isRTL ? 'فشل في تحميل الطلبات' : 'Failed to load requests');
      setRequests([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const handleApprove = async (req) => {
    setApproving(true);
    try {
      let result;
      if (req.account_type === 'school') {
        const res = await api.post(`/registration-requests/${req.id}/approve-school`);
        result = res.data;
      } else {
        if (req.source === 'teacher_registration') {
          const res = await api.post(`/teacher-registration/requests/${req.id}/approve`);
          result = res.data;
        } else {
          const res = await api.post(`/registration-requests/${req.id}/approve`, {});
          result = res.data;
        }
      }

      toast.success(isRTL ? 'تم قبول الطلب بنجاح' : 'Request approved successfully');
      setDetailsDialogOpen(false);

      if (result?.temporary_password || result?.email || result?.school_code) {
        setCredentialsDialog(result);
      }

      fetchRequests();
    } catch (error) {
      console.error('Failed to approve request:', error);
      const detail = error.response?.data?.detail;
      nassaqError(detail || (isRTL ? 'فشل في قبول الطلب' : 'Failed to approve request'));
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async (req) => {
    try {
      if (req.source === 'teacher_registration') {
        await api.post(`/teacher-registration/requests/${req.id}/reject`, {
          reason: isRTL ? 'تم رفض الطلب من قبل المسؤول' : 'Rejected by admin'
        });
      } else {
        await api.post(`/registration-requests/${req.id}/reject`, {
          reason: isRTL ? 'تم رفض الطلب من قبل المسؤول' : 'Rejected by admin'
        });
      }
      toast.success(isRTL ? 'تم رفض الطلب' : 'Request rejected');
      setDetailsDialogOpen(false);
      fetchRequests();
    } catch (error) {
      console.error('Failed to reject request:', error);
      nassaqError(isRTL ? 'فشل في رفض الطلب' : 'Failed to reject request');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success(isRTL ? 'تم النسخ' : 'Copied');
  };

  const filteredRequests = requests.filter(request => {
    const searchLower = searchTerm.toLowerCase();
    const matchesSearch = !searchTerm ||
      (request.display_name || '').toLowerCase().includes(searchLower) ||
      (request.email || '').toLowerCase().includes(searchLower) ||
      (request.school_name || '').toLowerCase().includes(searchLower);
    const matchesStatus = statusFilter === 'all' || 
      (statusFilter === 'pending' ? isPending(request.status) : request.status === statusFilter);
    const matchesType = typeFilter === 'all' || request.account_type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'pending':
      case 'pending_review':
        return <Badge className="bg-yellow-100 text-yellow-700">{isRTL ? 'قيد المراجعة' : 'Pending'}</Badge>;
      case 'approved':
        return <Badge className="bg-green-100 text-green-700">{isRTL ? 'مقبول' : 'Approved'}</Badge>;
      case 'rejected':
        return <Badge className="bg-red-100 text-red-700">{isRTL ? 'مرفوض' : 'Rejected'}</Badge>;
      case 'more_info_requested':
        return <Badge className="bg-blue-100 text-blue-700">{isRTL ? 'طلب معلومات' : 'Info Requested'}</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getTypeBadge = (type) => {
    if (type === 'school') {
      return <Badge className="bg-purple-100 text-purple-700"><School className="h-3 w-3 me-1 inline" />{isRTL ? 'مدرسة' : 'School'}</Badge>;
    }
    return <Badge className="bg-blue-100 text-blue-700"><GraduationCap className="h-3 w-3 me-1 inline" />{isRTL ? 'معلم' : 'Teacher'}</Badge>;
  };

  const isPending = (status) => ['pending', 'pending_review'].includes(status);

  const stats = {
    total: requests.length,
    pending: requests.filter(r => isPending(r.status)).length,
    approved: requests.filter(r => r.status === 'approved').length,
    rejected: requests.filter(r => r.status === 'rejected').length,
    schools: requests.filter(r => r.account_type === 'school').length,
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="teacher-requests-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'طلبات التسجيل' : 'Registration Requests'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL ? 'مراجعة وإدارة طلبات تسجيل المعلمين والمدارس' : 'Review and manage teacher & school registration requests'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" className="rounded-xl" onClick={() => fetchRequests()}>
                <RefreshCw className={`h-4 w-4 me-2 ${loading ? 'animate-spin' : ''}`} />
                {isRTL ? 'تحديث' : 'Refresh'}
              </Button>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Under Development Banner */}
          <Card className="card-nassaq border-yellow-500/30 bg-yellow-500/5">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                <AlertCircle className="h-6 w-6 text-yellow-600" />
              </div>
              <div>
                <h3 className="font-cairo font-medium text-brand-navy dark:text-brand-turquoise">
                  {isRTL ? 'نظام إدارة الطلبات' : 'Requests Management System'}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {isRTL 
                    ? 'يمكنك إنشاء ومتابعة جميع طلباتك من هنا.'
                    : 'You can create and track all your requests here.'}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                  <FileText className="h-6 w-6 text-brand-navy" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total}</p>
                  <p className="text-sm text-muted-foreground">{isRTL ? 'إجمالي الطلبات' : 'Total Requests'}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                  <Clock className="h-6 w-6 text-yellow-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.pending}</p>
                  <p className="text-sm text-muted-foreground">{isRTL ? 'قيد المراجعة' : 'Pending'}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-green-500/10 flex items-center justify-center">
                  <CheckCircle className="h-6 w-6 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.approved}</p>
                  <p className="text-sm text-muted-foreground">{isRTL ? 'مقبول' : 'Approved'}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center">
                  <XCircle className="h-6 w-6 text-red-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.rejected}</p>
                  <p className="text-sm text-muted-foreground">{isRTL ? 'مرفوض' : 'Rejected'}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative flex-1 min-w-[300px]">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={isRTL ? 'البحث في الطلبات...' : 'Search requests...'}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="ps-10 rounded-xl"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[180px] rounded-xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{isRTL ? 'جميع الأنواع' : 'All Types'}</SelectItem>
                <SelectItem value="school">{isRTL ? 'مدارس' : 'Schools'}</SelectItem>
                <SelectItem value="teacher">{isRTL ? 'معلمين' : 'Teachers'}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px] rounded-xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{isRTL ? 'جميع الحالات' : 'All Status'}</SelectItem>
                <SelectItem value="pending">{isRTL ? 'قيد المراجعة' : 'Pending'}</SelectItem>
                <SelectItem value="approved">{isRTL ? 'مقبول' : 'Approved'}</SelectItem>
                <SelectItem value="rejected">{isRTL ? 'مرفوض' : 'Rejected'}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Requests Table */}
          <Card className="card-nassaq">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{isRTL ? 'النوع' : 'Type'}</TableHead>
                    <TableHead>{isRTL ? 'الاسم' : 'Name'}</TableHead>
                    <TableHead>{isRTL ? 'البريد الإلكتروني' : 'Email'}</TableHead>
                    <TableHead>{isRTL ? 'الهاتف' : 'Phone'}</TableHead>
                    <TableHead>{isRTL ? 'التفاصيل' : 'Details'}</TableHead>
                    <TableHead>{isRTL ? 'الحالة' : 'Status'}</TableHead>
                    <TableHead>{isRTL ? 'الإجراءات' : 'Actions'}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRequests.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                        {isRTL ? 'لا توجد طلبات' : 'No requests found'}
                      </TableCell>
                    </TableRow>
                  )}
                  {filteredRequests.map((request) => (
                    <TableRow key={request.id}>
                      <TableCell>{getTypeBadge(request.account_type)}</TableCell>
                      <TableCell className="font-medium">{request.display_name}</TableCell>
                      <TableCell dir="ltr" className="text-sm">{request.email}</TableCell>
                      <TableCell dir="ltr" className="text-sm">{request.phone}</TableCell>
                      <TableCell className="text-sm">
                        {request.account_type === 'school'
                          ? `${request.school_city || ''} • ${isRTL ? 'سعة' : 'Cap'}: ${request.student_capacity || '-'}`
                          : `${request.subject || ''} • ${request.experience_years || 0} ${isRTL ? 'سنوات' : 'yrs'}`}
                      </TableCell>
                      <TableCell>{getStatusBadge(request.status)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => { setSelectedRequest(request); setDetailsDialogOpen(true); }}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {isPending(request.status) && (
                            <>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                className="text-green-600 hover:text-green-700"
                                disabled={approving}
                                onClick={() => handleApprove(request)}
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                className="text-red-600 hover:text-red-700"
                                onClick={() => handleReject(request)}
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        {/* Details Dialog */}
        <Dialog open={detailsDialogOpen} onOpenChange={setDetailsDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                {selectedRequest && getTypeBadge(selectedRequest?.account_type)}
                {isRTL ? 'تفاصيل الطلب' : 'Request Details'}
              </DialogTitle>
            </DialogHeader>
            {selectedRequest && (
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                  <User className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'الاسم' : 'Name'}</p>
                    <p className="font-medium">{selectedRequest.display_name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                  <Mail className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'البريد الإلكتروني' : 'Email'}</p>
                    <p className="font-medium" dir="ltr">{selectedRequest.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                  <Phone className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'رقم الهاتف' : 'Phone'}</p>
                    <p className="font-medium" dir="ltr">{selectedRequest.phone}</p>
                  </div>
                </div>

                {selectedRequest.account_type === 'school' ? (
                  <>
                    <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                      <Building2 className="h-5 w-5 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm text-muted-foreground">{isRTL ? 'اسم المدرسة' : 'School Name'}</p>
                        <p className="font-medium">{selectedRequest.school_name}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                      <MapPin className="h-5 w-5 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm text-muted-foreground">{isRTL ? 'المدينة' : 'City'}</p>
                        <p className="font-medium">{selectedRequest.school_city || '-'}</p>
                      </div>
                    </div>
                    {selectedRequest.school_address && (
                      <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                        <MapPin className="h-5 w-5 text-muted-foreground shrink-0" />
                        <div>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'العنوان' : 'Address'}</p>
                          <p className="font-medium">{selectedRequest.school_address}</p>
                        </div>
                      </div>
                    )}
                    <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                      <Users className="h-5 w-5 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm text-muted-foreground">{isRTL ? 'السعة الطلابية' : 'Student Capacity'}</p>
                        <p className="font-medium">{selectedRequest.student_capacity || '-'}</p>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                      <Building2 className="h-5 w-5 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm text-muted-foreground">{isRTL ? 'المدرسة' : 'School'}</p>
                        <p className="font-medium">{selectedRequest.school_name || '-'}</p>
                      </div>
                    </div>
                    {selectedRequest.subject && (
                      <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                        <GraduationCap className="h-5 w-5 text-muted-foreground shrink-0" />
                        <div>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'التخصص' : 'Subject'}</p>
                          <p className="font-medium">{selectedRequest.subject}</p>
                        </div>
                      </div>
                    )}
                  </>
                )}

                <div className="flex items-center justify-between p-2">
                  <span className="text-sm text-muted-foreground">{isRTL ? 'الحالة' : 'Status'}</span>
                  {getStatusBadge(selectedRequest.status)}
                </div>
              </div>
            )}
            {selectedRequest && isPending(selectedRequest.status) && (
              <DialogFooter>
                <Button variant="outline" onClick={() => handleReject(selectedRequest)}>
                  <X className="h-4 w-4 me-2" />
                  {isRTL ? 'رفض' : 'Reject'}
                </Button>
                <Button 
                  onClick={() => handleApprove(selectedRequest)} 
                  className="bg-green-600 hover:bg-green-700"
                  disabled={approving}
                >
                  <Check className="h-4 w-4 me-2" />
                  {approving ? (isRTL ? 'جاري القبول...' : 'Approving...') : (isRTL ? 'قبول' : 'Approve')}
                </Button>
              </DialogFooter>
            )}
          </DialogContent>
        </Dialog>

        {/* Credentials Dialog */}
        <Dialog open={!!credentialsDialog} onOpenChange={() => setCredentialsDialog(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo text-green-700">
                <CheckCircle className="h-5 w-5 inline me-2" />
                {isRTL ? 'تم القبول بنجاح' : 'Approved Successfully'}
              </DialogTitle>
              <DialogDescription>
                {isRTL ? 'بيانات الدخول للحساب الجديد:' : 'Login credentials for the new account:'}
              </DialogDescription>
            </DialogHeader>
            {credentialsDialog && (
              <div className="space-y-3">
                {credentialsDialog.school_code && (
                  <div className="flex items-center justify-between p-3 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
                    <div>
                      <p className="text-sm text-muted-foreground">{isRTL ? 'رمز المدرسة' : 'School Code'}</p>
                      <p className="font-mono font-bold text-lg">{credentialsDialog.school_code}</p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => copyToClipboard(credentialsDialog.school_code)}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                )}
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-xl">
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'البريد الإلكتروني' : 'Email'}</p>
                    <p className="font-medium" dir="ltr">{credentialsDialog.email}</p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => copyToClipboard(credentialsDialog.email)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <div className="flex items-center justify-between p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-xl">
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'كلمة المرور المؤقتة' : 'Temporary Password'}</p>
                    <p className="font-mono font-bold">{credentialsDialog.temporary_password}</p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => copyToClipboard(credentialsDialog.temporary_password)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                {credentialsDialog.message_template && (
                  <div className="p-3 bg-muted/30 rounded-xl">
                    <p className="text-sm text-muted-foreground mb-2">{isRTL ? 'رسالة للإرسال:' : 'Message to send:'}</p>
                    <pre className="text-xs whitespace-pre-wrap font-tajawal bg-background p-2 rounded-lg max-h-40 overflow-y-auto" dir="rtl">
                      {credentialsDialog.message_template}
                    </pre>
                    <Button variant="outline" size="sm" className="mt-2 w-full" onClick={() => copyToClipboard(credentialsDialog.message_template)}>
                      <Copy className="h-4 w-4 me-2" />
                      {isRTL ? 'نسخ الرسالة' : 'Copy Message'}
                    </Button>
                  </div>
                )}
              </div>
            )}
            <DialogFooter>
              <Button onClick={() => setCredentialsDialog(null)}>
                {isRTL ? 'إغلاق' : 'Close'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
};
