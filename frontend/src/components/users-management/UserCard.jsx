import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { Button } from '../ui/button';
import {
  Eye, Edit, Trash2, Lock, Unlock, Bell, Mail, Phone,
  Building2, Briefcase, Clock, Calendar, Brain
} from 'lucide-react';
import { getRoleInfo, formatDate, formatTimeAgo } from './constants';

export default function UserCard({
  user,
  onView,
  onSuspend,
  onEdit,
  onDelete,
  onNotify,
}) {
  const roleInfo = getRoleInfo(user.role);
  const RoleIcon = roleInfo.icon;

  return (
    <Card className="hover:shadow-lg transition-all" data-testid={`user-card-${user.id}`}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-4 flex-row-reverse">
          <div className="flex items-center gap-3 flex-row-reverse">
            <Avatar className="h-14 w-14 border-2">
              <AvatarFallback className={`${roleInfo.color} text-white text-lg`}>
                {user.full_name?.charAt(0)}
              </AvatarFallback>
            </Avatar>
            <div className="text-right">
              <h4 className="font-bold text-base">{user.full_name}</h4>
              <Badge variant="outline" className={`${roleInfo.color} text-white border-0 text-[10px] mt-1`}>
                <RoleIcon className="h-3 w-3 ms-1" />
                {roleInfo.name}
              </Badge>
            </div>
          </div>
          <div className="flex flex-col gap-1 items-start">
            {user.is_active !== false ? (
              <Badge className="bg-green-100 text-green-700 text-[10px]">نشط</Badge>
            ) : (
              <Badge className="bg-red-100 text-red-700 text-[10px]">موقوف</Badge>
            )}
            {user.ai_enabled && (
              <Badge className="bg-purple-100 text-purple-700 text-[10px]">
                <Brain className="h-3 w-3 ms-1" />
                AI
              </Badge>
            )}
          </div>
        </div>

        <div className="space-y-2 text-sm mb-4">
          <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
            <Mail className="h-4 w-4 flex-shrink-0" />
            <span className="truncate text-right flex-1" dir="ltr">{user.email}</span>
          </div>
          {user.phone && (
            <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
              <Phone className="h-4 w-4 flex-shrink-0" />
              <span dir="ltr">{user.phone}</span>
            </div>
          )}
          {user.school_name && (
            <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
              <Building2 className="h-4 w-4 flex-shrink-0" />
              <span className="text-right">{user.school_name}</span>
            </div>
          )}
          {user.department && (
            <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
              <Briefcase className="h-4 w-4 flex-shrink-0" />
              <span className="text-right">{user.department}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
            <Clock className="h-4 w-4 flex-shrink-0" />
            <span className="text-right text-xs">{formatTimeAgo(user.last_login)}</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
            <Calendar className="h-4 w-4 flex-shrink-0" />
            <span className="text-right text-xs">تاريخ الإنشاء: {formatDate(user.created_at)}</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 pt-3 border-t">
          <Button
            variant="outline" size="sm"
            className="flex-1 min-w-[60px] rounded-lg text-xs"
            onClick={() => onView(user)}
            data-testid={`view-user-${user.id}`}
          >
            <Eye className="h-3 w-3 ms-1" />
            عرض
          </Button>
          <Button
            variant="outline" size="sm"
            className="flex-1 min-w-[60px] rounded-lg text-xs"
            onClick={() => onSuspend(user)}
            data-testid={`suspend-user-${user.id}`}
          >
            {user.is_active !== false ? (
              <><Lock className="h-3 w-3 ms-1" />تعليق</>
            ) : (
              <><Unlock className="h-3 w-3 ms-1" />تفعيل</>
            )}
          </Button>
          <Button
            variant="outline" size="sm"
            className="flex-1 min-w-[60px] rounded-lg text-xs"
            onClick={() => onEdit(user)}
            data-testid={`edit-user-${user.id}`}
          >
            <Edit className="h-3 w-3 ms-1" />
            تعديل
          </Button>
          <Button
            variant="outline" size="sm"
            className="flex-1 min-w-[60px] rounded-lg text-xs text-red-600 hover:bg-red-50"
            onClick={() => onDelete(user)}
            data-testid={`delete-user-${user.id}`}
          >
            <Trash2 className="h-3 w-3 ms-1" />
            حذف
          </Button>
          <Button
            variant="outline" size="sm"
            className="flex-1 min-w-[60px] rounded-lg text-xs text-blue-600 hover:bg-blue-50"
            onClick={() => onNotify(user)}
            data-testid={`notify-user-${user.id}`}
          >
            <Bell className="h-3 w-3 ms-1" />
            إشعار
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
