import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { Button } from '../ui/button';
import { Building2, Eye, UserPlus, School } from 'lucide-react';
import { getRoleInfo } from './constants';

export default function SchoolUsersTab({ schoolUsers }) {
  const navigate = useNavigate();

  const handleViewUser = (user) => {
    navigate(`/admin/users/${user.id}`);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <CardTitle className="font-cairo flex items-center gap-2 flex-row-reverse">
            <Building2 className="h-5 w-5 text-brand-navy" />
            مستخدمو المدارس
          </CardTitle>
          <Badge variant="outline" className="text-sm">
            {Object.keys(schoolUsers).length} مدرسة
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {Object.keys(schoolUsers).length === 0 ? (
          <div className="py-12 text-center">
            <Building2 className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
            <h3 className="font-bold text-lg mb-2">لا توجد مدارس</h3>
            <p className="text-muted-foreground">لم يتم إضافة مدارس بعد</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {Object.values(schoolUsers).map(({ school, users: schoolUsersList }) => (
              <Card key={school.id} className="border-2 border-teal-200 bg-gradient-to-br from-teal-50/50 to-white" data-testid={`school-card-${school.id}`}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between flex-row-reverse">
                    <div className="flex items-center gap-3 flex-row-reverse">
                      <div className="w-12 h-12 rounded-xl bg-teal-100 flex items-center justify-center">
                        <School className="h-6 w-6 text-teal-600" />
                      </div>
                      <div className="text-right">
                        <h4 className="font-bold text-lg">{school.name}</h4>
                        <Badge variant="outline" className={`text-[10px] ${school.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                          {school.status === 'active' ? 'نشط' : school.status === 'setup' ? 'قيد الإعداد' : school.status}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex flex-col items-start gap-1">
                      <span className="text-xs text-muted-foreground">{schoolUsersList.length} مستخدم</span>
                      <span className="text-xs text-muted-foreground">{school.city || 'غير محدد'}</span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-2">
                  {schoolUsersList.length === 0 ? (
                    <div className="py-4 text-center text-muted-foreground text-sm">
                      لا يوجد مستخدمين في هذه المدرسة
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[200px] overflow-y-auto">
                      {schoolUsersList.slice(0, 5).map((user) => {
                        const roleInfo = getRoleInfo(user.role);
                        const RoleIcon = roleInfo.icon;
                        return (
                          <div key={user.id} className="flex items-center justify-between p-2 rounded-lg bg-white border flex-row-reverse">
                            <div className="flex items-center gap-2 flex-row-reverse">
                              <Avatar className="h-8 w-8">
                                <AvatarFallback className={`${roleInfo.color} text-white text-xs`}>
                                  {user.full_name?.charAt(0)}
                                </AvatarFallback>
                              </Avatar>
                              <div className="text-right">
                                <p className="text-sm font-medium">{user.full_name}</p>
                                <Badge variant="outline" className="text-[9px]">
                                  <RoleIcon className="h-2.5 w-2.5 ms-1" />
                                  {roleInfo.name}
                                </Badge>
                              </div>
                            </div>
                            <Button
                              variant="ghost" size="sm" className="h-7 w-7 p-0"
                              onClick={() => handleViewUser(user)}
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        );
                      })}
                      {schoolUsersList.length > 5 && (
                        <p className="text-center text-xs text-muted-foreground pt-2">
                          +{schoolUsersList.length - 5} مستخدمين آخرين
                        </p>
                      )}
                    </div>
                  )}
                  <div className="flex gap-2 mt-4 pt-3 border-t">
                    <Button
                      variant="outline" size="sm" className="flex-1 text-xs"
                      onClick={() => navigate(`/admin/tenants/${school.id}`)}
                    >
                      <Eye className="h-3 w-3 ms-1" />
                      تفاصيل
                    </Button>
                    <Button variant="outline" size="sm" className="flex-1 text-xs">
                      <UserPlus className="h-3 w-3 ms-1" />
                      إضافة مستخدم
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
