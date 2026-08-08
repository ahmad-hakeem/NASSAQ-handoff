import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Avatar, AvatarFallback } from '@/shared/components/ui/avatar';
import { Button } from '@/shared/components/ui/button';
import {
  Eye, CheckCircle2, XCircle, Clock, Archive, Info
} from 'lucide-react';
import { PENDING_STATUSES, formatDate } from './constants';

const STATUS_MAP = {
  approved: { label: 'معتمد', color: 'bg-green-500', border: 'border-green-200 bg-green-50/30' },
  rejected: { label: 'مرفوض', color: 'bg-red-500', border: 'border-red-200 bg-red-50/30' },
  under_review: { label: 'تحت المراجعة', color: 'bg-orange-500', border: 'border-orange-200 bg-orange-50/30' },
  info_required: { label: 'بانتظار معلومات', color: 'bg-blue-500', border: 'border-blue-200 bg-blue-50/30' },
  more_info_requested: { label: 'بانتظار معلومات', color: 'bg-blue-500', border: 'border-blue-200 bg-blue-50/30' },
  archived: { label: 'مؤرشف', color: 'bg-gray-500', border: 'border-gray-200 bg-gray-50/30' },
  cancelled: { label: 'ملغي', color: 'bg-gray-400', border: 'border-gray-200 bg-gray-50/30' },
};

export default function ApprovalRequestsTab({
  requestType,
  config,
  requests,
  filteredRequests,
  currentFilter,
  onFilterChange,
  onViewDetails,
  onApprove,
  onMarkUnderReview,
  onReject,
  onArchive,
  onRequestMoreInfo,
}) {
  const TypeIcon = config.tabIcon;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <CardTitle className="font-cairo flex items-center gap-2 flex-row-reverse">
            <TypeIcon className="h-5 w-5 text-brand-navy" />
            {config.cardTitle}
          </CardTitle>
          <div className="flex gap-2 flex-wrap">
            {config.statusFilters.map((status) => (
              <Button
                key={status.id}
                variant={currentFilter === status.id ? 'default' : 'outline'}
                size="sm"
                className={`text-xs ${currentFilter === status.id ? status.color + ' text-white' : ''}`}
                onClick={() => onFilterChange(status.id)}
              >
                {status.name}
                {status.id !== 'all' && (
                  <Badge variant="secondary" className="ms-1 h-5 w-5 p-0 flex items-center justify-center text-[10px]">
                    {status.id === 'pending'
                      ? requests.filter(r => PENDING_STATUSES.includes(r.status)).length
                      : requests.filter(r => r.status === status.id).length}
                  </Badge>
                )}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {filteredRequests.length === 0 ? (
          <div className="py-12 text-center">
            <TypeIcon className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
            <h3 className="font-bold text-lg mb-2">{config.emptyTitle}</h3>
            <p className="text-muted-foreground">
              {currentFilter === 'all' ? config.emptyMessage : 'لا توجد طلبات في الحالة المحددة'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredRequests.map((request) => {
              const isPending = PENDING_STATUSES.includes(request.status);
              const statusInfo = STATUS_MAP[request.status] || { label: 'قيد المراجعة', color: 'bg-yellow-500', border: 'border-yellow-200 bg-yellow-50/30' };
              const fields = config.cardFields(request);

              return (
                <Card key={request.id} className={`border-2 ${statusInfo.border}`}>
                  <CardContent className="p-4">
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                      <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-3 flex-row-reverse justify-end">
                          <div className="text-right">
                            <h4 className="font-bold text-lg">{request[config.nameField] || 'بدون اسم'}</h4>
                            <Badge className={`${statusInfo.color} text-white text-xs mt-1`}>{statusInfo.label}</Badge>
                          </div>
                          <Avatar className="h-12 w-12 border-2">
                            <AvatarFallback className={`${config.avatarBg} text-white`}>
                              {config.avatarContent(request)}
                            </AvatarFallback>
                          </Avatar>
                        </div>
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                          {fields.map((field, idx) => (
                            <div key={idx} className={`flex items-center gap-2 flex-row-reverse ${field.colSpan === 2 ? 'col-span-2' : ''}`}>
                              <span className="text-muted-foreground">{field.label}:</span>
                              <span className={`font-medium ${field.className || ''}`} dir={field.dir || undefined}>
                                {field.value === '__date__' ? formatDate(request[field.dateKey]) : field.value}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="flex flex-wrap lg:flex-col gap-2">
                        <Button variant="outline" size="sm" className="flex-1 lg:flex-none" onClick={() => onViewDetails(request)}>
                          <Eye className="h-4 w-4 ms-2" />
                          تفاصيل
                        </Button>
                        {isPending && (
                          <>
                            <Button size="sm" className="bg-green-600 hover:bg-green-700 flex-1 lg:flex-none" onClick={() => onApprove(request)}>
                              <CheckCircle2 className="h-4 w-4 ms-2" />
                              موافقة
                            </Button>
                            {request.status !== 'under_review' && (
                              <Button size="sm" variant="outline" className="flex-1 lg:flex-none border-orange-400 text-orange-600 hover:bg-orange-50 hover:text-orange-600 focus-visible:text-orange-600" onClick={() => onMarkUnderReview(request)}>
                                <Clock className="h-4 w-4 ms-2" />
                                تحت المراجعة
                              </Button>
                            )}
                            <Button size="sm" variant="destructive" className="flex-1 lg:flex-none" onClick={() => onReject(request)}>
                              <XCircle className="h-4 w-4 ms-2" />
                              رفض
                            </Button>
                            {config.showMoreInfoAction && (
                              <Button size="sm" variant="outline" className="flex-1 lg:flex-none" onClick={() => onRequestMoreInfo(request)}>
                                <Info className="h-4 w-4 ms-2" />
                                طلب معلومات
                              </Button>
                            )}
                          </>
                        )}
                        {(request.status === 'approved' || request.status === 'rejected') && (
                          <Button size="sm" variant="outline" className="flex-1 lg:flex-none" onClick={() => onArchive(request)}>
                            <Archive className="h-4 w-4 ms-2" />
                            أرشفة
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
