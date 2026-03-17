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
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);

  // Fetch teacher registration requests from API
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const fetchRequests = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter && statusFilter !== 'all') {
        params.status = statusFilter;
      }
      
      const response = await api.get('/teacher-registration/requests', { params });
      
      if (response.data && response.data.requests) {
        // Transform API response to match UI expectations
        const transformedRequests = response.data.requests.map(r => ({
          id: r.id,
          teacher_name: r.full_name,
          email: r.email,
          phone: r.phone,
          school_name: r.school_name || '',
          subject: r.subject,
          experience_years: r.years_of_experience,
          status: r.status,
          submitted_at: r.created_at,
          ...r
        }));
        setRequests(transformedRequests);
      } else {
        setRequests([]);
      }
    } catch (error) {
      console.error('Failed to fetch teacher requests:', error);
      nassaqError(isRTL ? 'فشل في تحميل الطلبات' : 'Failed to load requests');
      setRequests([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, [statusFilter]);

  const handleApprove = async (requestId) => {
    try {
      await api.post(`/teacher-registration/requests/${requestId}/approve`);
      toast.success(isRTL ? 'تم قبول الطلب بنجاح' : 'Request approved successfully');
      setDetailsDialogOpen(false);
      fetchRequests(); // Refresh data from API
    } catch (error) {
      console.error('Failed to approve request:', error);
      nassaqError(isRTL ? 'فشل في قبول الطلب' : 'Failed to approve request');
    }
  };

  const handleReject = async (requestId) => {
    try {
      await api.post(`/teacher-registration/requests/${requestId}/reject`, {
        reason: isRTL ? 'تم رفض الطلب من قبل المسؤول' : 'Rejected by admin'
      });
      toast.success(isRTL ? 'تم رفض الطلب' : 'Request rejected');
      setDetailsDialogOpen(false);
      fetchRequests(); // Refresh data from API
    } catch (error) {
      console.error('Failed to reject request:', error);
      nassaqError(isRTL ? 'فشل في رفض الطلب' : 'Failed to reject request');
    }
  };

  const filteredRequests = requests.filter(request => {
    const matchesSearch = 
      request.teacher_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      request.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      request.school_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || request.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-700">{isRTL ? 'قيد المراجعة' : 'Pending'}</Badge>;
      case 'approved':
        return <Badge className="bg-green-100 text-green-700">{isRTL ? 'مقبول' : 'Approved'}</Badge>;
      case 'rejected':
        return <Badge className="bg-red-100 text-red-700">{isRTL ? 'مرفوض' : 'Rejected'}</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const stats = {
    total: requests.length,
    pending: requests.filter(r => r.status === 'pending').length,
    approved: requests.filter(r => r.status === 'approved').length,
    rejected: requests.filter(r => r.status === 'rejected').length,
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="teacher-requests-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'طلبات المعلمين' : 'Teacher Requests'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL ? 'مراجعة وإدارة طلبات تسجيل المعلمين' : 'Review and manage teacher registration requests'}
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
                    <TableHead>{isRTL ? 'اسم المعلم' : 'Teacher Name'}</TableHead>
                    <TableHead>{isRTL ? 'البريد الإلكتروني' : 'Email'}</TableHead>
                    <TableHead>{isRTL ? 'المدرسة' : 'School'}</TableHead>
                    <TableHead>{isRTL ? 'التخصص' : 'Subject'}</TableHead>
                    <TableHead>{isRTL ? 'الخبرة' : 'Experience'}</TableHead>
                    <TableHead>{isRTL ? 'الحالة' : 'Status'}</TableHead>
                    <TableHead>{isRTL ? 'الإجراءات' : 'Actions'}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRequests.map((request) => (
                    <TableRow key={request.id}>
                      <TableCell className="font-medium">{request.teacher_name}</TableCell>
                      <TableCell dir="ltr">{request.email}</TableCell>
                      <TableCell>{request.school_name}</TableCell>
                      <TableCell>{request.subject}</TableCell>
                      <TableCell>
                        {request.experience_years} {isRTL ? 'سنوات' : 'years'}
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
                          {request.status === 'pending' && (
                            <>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                className="text-green-600 hover:text-green-700"
                                onClick={() => handleApprove(request.id)}
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                className="text-red-600 hover:text-red-700"
                                onClick={() => handleReject(request.id)}
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
              <DialogTitle className="font-cairo">
                {isRTL ? 'تفاصيل الطلب' : 'Request Details'}
              </DialogTitle>
            </DialogHeader>
            {selectedRequest && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                  <User className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'اسم المعلم' : 'Teacher Name'}</p>
                    <p className="font-medium">{selectedRequest.teacher_name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                  <Mail className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'البريد الإلكتروني' : 'Email'}</p>
                    <p className="font-medium" dir="ltr">{selectedRequest.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                  <Phone className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'رقم الهاتف' : 'Phone'}</p>
                    <p className="font-medium" dir="ltr">{selectedRequest.phone}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                  <Building2 className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'المدرسة' : 'School'}</p>
                    <p className="font-medium">{selectedRequest.school_name}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{isRTL ? 'الحالة' : 'Status'}</span>
                  {getStatusBadge(selectedRequest.status)}
                </div>
              </div>
            )}
            {selectedRequest?.status === 'pending' && (
              <DialogFooter>
                <Button variant="outline" onClick={() => handleReject(selectedRequest.id)}>
                  <X className="h-4 w-4 me-2" />
                  {isRTL ? 'رفض' : 'Reject'}
                </Button>
                <Button onClick={() => handleApprove(selectedRequest.id)} className="bg-green-600 hover:bg-green-700">
                  <Check className="h-4 w-4 me-2" />
                  {isRTL ? 'قبول' : 'Approve'}
                </Button>
              </DialogFooter>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
};
