import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { Button } from '../ui/button';
import { ExternalLink, Lock, Unlock, Clock } from 'lucide-react';
import { getRoleInfo, formatTimeAgo } from './constants';

export default function UserCard({ user, onView, onSuspend }) {
  const roleInfo = getRoleInfo(user.role);
  const RoleIcon = roleInfo.icon;

  return (
    <Card className="hover:shadow-lg transition-all group" data-testid={`user-card-${user.id}`}>
      <CardContent className="p-4">
        <div className="flex items-center gap-3 flex-row-reverse mb-3">
          <Avatar className="h-12 w-12 border-2 flex-shrink-0">
            <AvatarFallback className={`${roleInfo.color} text-white text-lg`}>
              {user.full_name?.charAt(0)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0 text-right">
            <h4 className="font-bold text-base truncate">{user.full_name}</h4>
            <Badge variant="outline" className={`${roleInfo.color} text-white border-0 text-[10px] mt-1`}>
              <RoleIcon className="h-3 w-3 ms-1" />
              {roleInfo.name}
            </Badge>
          </div>
          {user.is_active !== false ? (
            <Badge className="bg-green-100 text-green-700 text-[10px] flex-shrink-0">نشط</Badge>
          ) : (
            <Badge className="bg-red-100 text-red-700 text-[10px] flex-shrink-0">موقوف</Badge>
          )}
        </div>

        <div className="flex items-center gap-2 text-muted-foreground text-xs mb-4 flex-row-reverse">
          <Clock className="h-3.5 w-3.5 flex-shrink-0" />
          <span>{formatTimeAgo(user.last_login)}</span>
        </div>

        <div className="flex gap-2 pt-3 border-t">
          <Button
            variant="default"
            size="sm"
            className="flex-1 rounded-lg text-xs bg-brand-navy hover:bg-brand-navy/90"
            onClick={() => onView(user)}
            data-testid={`view-user-${user.id}`}
          >
            <ExternalLink className="h-3.5 w-3.5 ms-1.5" />
            فتح الحساب
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={`flex-1 rounded-lg text-xs ${user.is_active !== false ? 'text-orange-600 hover:bg-orange-50' : 'text-green-600 hover:bg-green-50'}`}
            onClick={() => onSuspend(user)}
            data-testid={`suspend-user-${user.id}`}
          >
            {user.is_active !== false ? (
              <><Lock className="h-3.5 w-3.5 ms-1.5" />تعليق</>
            ) : (
              <><Unlock className="h-3.5 w-3.5 ms-1.5" />تفعيل</>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
