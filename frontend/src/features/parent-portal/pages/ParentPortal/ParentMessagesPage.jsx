import React, { useState, useEffect } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import PortalLayout from '@/features/student-portal/components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { Avatar, AvatarFallback } from '@/shared/components/ui/avatar';
import {
  MessageSquare, Send, ArrowUpRight, ArrowDownLeft, Clock, AlertCircle
} from 'lucide-react';


const ParentMessagesPage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const res = await api.get('/parent-portal/messages');
        setMessages(res.data?.messages || []);
      } catch (err) {
        console.error('Error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchMessages();
  }, [token, api]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <LoadingState variant="fullpage" />
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-messages-page">
        <div className="flex items-center gap-2 mb-2">
          <MessageSquare className="h-6 w-6 text-brand-navy" />
          <h1 className="text-xl font-bold font-cairo">{t('messages2')}</h1>
        </div>

        {messages.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-16 text-center">
              <MessageSquare className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="font-cairo font-bold text-lg text-foreground mb-2">
                {t('noMessagesYet')}
              </h3>
              <p className="text-muted-foreground text-sm">
                {t('messagesWillAppearHereWhenCommunicatingWithTeacher')}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {messages.map((msg) => (
              <Card key={msg.id} className="rounded-xl border-0 shadow-sm hover:shadow-md transition-all">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      msg.is_sent ? 'bg-blue-100 dark:bg-blue-900/40' : 'bg-green-100 dark:bg-green-900/40'
                    }`}>
                      {msg.is_sent ? (
                        <ArrowUpRight className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                      ) : (
                        <ArrowDownLeft className="h-5 w-5 text-green-600 dark:text-green-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-medium text-sm truncate">
                          {msg.is_sent
                            ? (isRTL ? `إلى: ${msg.receiver_name}` : `To: ${msg.receiver_name}`)
                            : (isRTL ? `من: ${msg.sender_name}` : `From: ${msg.sender_name}`)}
                        </p>
                        {!msg.read_status && !msg.is_sent && (
                          <Badge className="bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 border-0 text-xs">
                            {isRTL ? 'جديد' : 'New'}
                          </Badge>
                        )}
                      </div>
                      <p className="font-bold text-sm">{msg.subject}</p>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{msg.content}</p>
                      <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        <span>{msg.created_at?.slice(0, 16).replace('T', ' ')}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentMessagesPage;
