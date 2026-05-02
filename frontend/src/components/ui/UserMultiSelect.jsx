import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronsUpDown, Loader2, Search, X } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Button } from './button';
import { Badge } from './badge';
import { Input } from './input';
import { Popover, PopoverContent, PopoverTrigger } from './popover';
import { cn } from '../../lib/utils';

export function UserMultiSelect({ value = [], onChange, placeholder, dataTestId = 'user-multi-select' }) {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();

  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get('/users');
        const payload = res.data;
        const list = Array.isArray(payload)
          ? payload
          : Array.isArray(payload?.users)
            ? payload.users
            : Array.isArray(payload?.data)
              ? payload.data
              : [];
        if (!cancelled) setUsers(list);
      } catch (e) {
        if (!cancelled) setUsers([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [api]);

  const usersById = useMemo(() => {
    const map = {};
    for (const u of users) map[u.id] = u;
    return map;
  }, [users]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) => {
      const name = (u.full_name || '').toLowerCase();
      const email = (u.email || '').toLowerCase();
      const phone = (u.phone || '').toLowerCase();
      return name.includes(q) || email.includes(q) || phone.includes(q);
    });
  }, [users, search]);

  const toggle = (id) => {
    if (value.includes(id)) onChange(value.filter((v) => v !== id));
    else onChange([...value, id]);
  };

  const remove = (id) => onChange(value.filter((v) => v !== id));

  const ph = placeholder || (isRTL ? 'ابحث عن مستخدمين...' : 'Search for users...');

  return (
    <div className="space-y-2" data-testid={dataTestId}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between rounded-xl font-normal"
            data-testid={`${dataTestId}-trigger`}
          >
            <span className={cn('truncate', value.length === 0 && 'text-muted-foreground')}>
              {value.length === 0
                ? ph
                : isRTL
                  ? `تم اختيار ${value.length} مستخدم`
                  : `${value.length} user${value.length === 1 ? '' : 's'} selected`}
            </span>
            <ChevronsUpDown className="h-4 w-4 opacity-50 shrink-0" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
          <div className="p-2 border-b border-border/60">
            <div className="relative">
              <Search className="h-4 w-4 absolute top-1/2 -translate-y-1/2 text-muted-foreground start-2" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={ph}
                className="ps-8 rounded-lg"
                data-testid={`${dataTestId}-search`}
              />
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {loading ? (
              <div className="flex items-center justify-center py-6 text-muted-foreground text-sm">
                <Loader2 className="h-4 w-4 animate-spin me-2" />
                {t('loading') || (isRTL ? 'جارٍ التحميل...' : 'Loading...')}
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center text-sm text-muted-foreground py-6">
                {isRTL ? 'لا يوجد مستخدمون' : 'No users found'}
              </div>
            ) : (
              filtered.slice(0, 200).map((u) => {
                const selected = value.includes(u.id);
                return (
                  <button
                    type="button"
                    key={u.id}
                    onClick={() => toggle(u.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/60 transition-colors text-start"
                    data-testid={`${dataTestId}-option-${u.id}`}
                  >
                    <Check className={cn('h-4 w-4 shrink-0', selected ? 'opacity-100 text-brand-turquoise' : 'opacity-0')} />
                    <div className="flex-1 min-w-0">
                      <p className="truncate font-medium">{u.full_name || u.email || u.id}</p>
                      {(u.email || u.role) && (
                        <p className="text-xs text-muted-foreground truncate">
                          {u.role}{u.email ? ` • ${u.email}` : ''}
                        </p>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </PopoverContent>
      </Popover>

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((id) => {
            const u = usersById[id];
            return (
              <Badge key={id} variant="secondary" className="gap-1 ps-2 pe-1 py-1">
                <span className="text-xs">{u?.full_name || u?.email || id}</span>
                <button
                  type="button"
                  onClick={() => remove(id)}
                  className="rounded-full hover:bg-background/60 p-0.5"
                  aria-label="remove"
                  data-testid={`${dataTestId}-remove-${id}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default UserMultiSelect;
