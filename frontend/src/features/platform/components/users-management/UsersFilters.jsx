import React from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import { Search, RefreshCw } from 'lucide-react';
import { USER_ROLES, ACCOUNT_TYPES, ACCOUNT_STATUSES } from './constants';

export default function UsersFilters({
  searchQuery, setSearchQuery,
  selectedAccountType, setSelectedAccountType,
  selectedRole, setSelectedRole,
  selectedStatus, setSelectedStatus,
  selectedAIStatus, setSelectedAIStatus,
  hasActiveFilters, clearFilters,
  loading, onRefresh,
}) {
  return (
    <>
      <Card className="hidden lg:block">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-4 flex-row-reverse">
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="text-red-500">
                مسح الفلاتر
              </Button>
            )}

            <Button variant="outline" size="icon" onClick={onRefresh} className="rounded-xl">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>

            <Select value={selectedAIStatus} onValueChange={setSelectedAIStatus}>
              <SelectTrigger className="w-32 rounded-xl">
                <SelectValue placeholder="AI" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">الكل</SelectItem>
                <SelectItem value="enabled">AI مفعّل</SelectItem>
                <SelectItem value="disabled">AI معطّل</SelectItem>
              </SelectContent>
            </Select>

            <Select value={selectedStatus} onValueChange={setSelectedStatus}>
              <SelectTrigger className="w-32 rounded-xl">
                <SelectValue placeholder="الحالة" />
              </SelectTrigger>
              <SelectContent>
                {ACCOUNT_STATUSES.map((status) => (
                  <SelectItem key={status.id} value={status.id}>
                    <span className="flex items-center gap-2">
                      {status.color && <span className={`w-2 h-2 rounded-full ${status.color}`} />}
                      {status.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedRole} onValueChange={setSelectedRole}>
              <SelectTrigger className="w-40 rounded-xl">
                <SelectValue placeholder="الدور" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">جميع الأدوار</SelectItem>
                {USER_ROLES.map((role) => (
                  <SelectItem key={role.id} value={role.id}>{role.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedAccountType} onValueChange={setSelectedAccountType}>
              <SelectTrigger className="w-40 rounded-xl">
                <SelectValue placeholder="نوع الحساب" />
              </SelectTrigger>
              <SelectContent>
                {ACCOUNT_TYPES.map((type) => (
                  <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="relative flex-1 min-w-[300px]">
              <Search className="absolute end-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="البحث بالاسم، البريد، الهاتف، المدرسة..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pe-10 rounded-xl text-right"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="lg:hidden relative">
        <Search className="absolute end-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="البحث..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pe-10 rounded-xl text-right"
        />
      </div>
    </>
  );
}
