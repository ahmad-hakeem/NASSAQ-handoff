import { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import {
  Loader2,
  Clock,
  Users,
  BookOpen,
  User,
  RefreshCw,
  Eye,
  Activity,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const LiveSessionsMonitor = ({ open, onClose, onOpenChange }) => {
  const { isRTL } = useTheme();
  const { token } = useAuth();
  
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [todaySchedule, setTodaySchedule] = useState([]);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    
    try {
      const [currentRes, todayRes] = await Promise.all([
        axios.get(`${API_URL}/api/schedules/sessions/current`, { headers }).catch(() => ({ data: { sessions: [] } })),
        axios.get(`${API_URL}/api/schedules/sessions/today`, { headers }).catch(() => ({ data: { sessions: [] } })),
      ]);
      
      setSessions(currentRes.data.sessions || []);
      setTodaySchedule(todayRes.data.sessions || []);
      setLastRefresh(new Date());
    } catch (error) {
      console.error('Error fetching sessions:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (open) {
      fetchSessions();
      // Auto-refresh every 30 seconds
      const interval = setInterval(fetchSessions, 30000);
      return () => clearInterval(interval);
    }
  }, [open, fetchSessions]);

  const getCurrentTime = () => {
    const now = new Date();
    return now.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' });
  };

  const isCurrentPeriod = (start, end) => {
    const now = new Date();
    const currentTime = now.getHours() * 60 + now.getMinutes();
    const [startH, startM] = start.split(':').map(Number);
    const [endH, endM] = end.split(':').map(Number);
    const startMinutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;
    return currentTime >= startMinutes && currentTime <= endMinutes;
  };

  // Handle close - support both onClose and onOpenChange
  const handleClose = () => {
    if (onOpenChange) onOpenChange(false);
    else if (onClose) onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="live-sessions-monitor">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between font-cairo text-xl">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-cyan-100 rounded-xl flex items-center justify-center">
                <Eye className="h-5 w-5 text-cyan-600" />
              </div>
              {isRTL ? 'الحصص الجارية' : 'Live Sessions'}
            </div>
            <Button variant="outline" size="sm" onClick={fetchSessions} disabled={loading}>
              <RefreshCw className={`h-4 w-4 me-2 ${loading ? 'animate-spin' : ''}`} />
              {isRTL ? 'تحديث' : 'Refresh'}
            </Button>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Current Time */}
          <div className="flex items-center justify-between p-4 bg-gradient-to-r from-cyan-50 to-blue-50 rounded-xl">
            <div className="flex items-center gap-3">
              <Clock className="h-6 w-6 text-cyan-600" />
              <div>
                <p className="text-sm text-muted-foreground font-tajawal">{isRTL ? 'الوقت الحالي' : 'Current Time'}</p>
                <p className="text-2xl font-bold text-cyan-700" dir="ltr">{getCurrentTime()}</p>
              </div>
            </div>
            <div className="text-end">
              <p className="text-sm text-muted-foreground font-tajawal">{isRTL ? 'حصص جارية' : 'Active Sessions'}</p>
              <p className="text-3xl font-bold text-cyan-700">{sessions.length}</p>
            </div>
          </div>

          {/* Active Sessions */}
          <div>
            <h3 className="font-bold font-cairo mb-4 flex items-center gap-2">
              <Activity className="h-5 w-5 text-green-600" />
              {isRTL ? 'الحصص الجارية الآن' : 'Currently Active'}
            </h3>
            
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-cyan-600" />
              </div>
            ) : sessions.length === 0 ? (
              <Card className="bg-muted/30">
                <CardContent className="py-8 text-center">
                  <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                  <p className="text-muted-foreground font-tajawal">
                    {isRTL ? 'لا توجد حصص جارية حالياً' : 'No active sessions right now'}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sessions.map((session, idx) => (
                  <Card key={idx} className="bg-gradient-to-br from-green-50 to-emerald-50 border-green-200">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between mb-3">
                        <Badge className="bg-green-600">{isRTL ? `الحصة ${session.period_number}` : `Period ${session.period_number}`}</Badge>
                        <span className="text-sm font-mono text-green-700">{session.start_time} - {session.end_time}</span>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <BookOpen className="h-4 w-4 text-green-600" />
                          <span className="font-medium">{session.subject_name || session.subject_id}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-green-600" />
                          <span className="text-sm">{session.teacher_name || session.teacher_id}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Users className="h-4 w-4 text-green-600" />
                          <span className="text-sm">{session.class_name || session.class_id}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* Today's Schedule */}
          <div>
            <h3 className="font-bold font-cairo mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-blue-600" />
              {isRTL ? 'جدول اليوم الكامل' : "Today's Full Schedule"}
            </h3>
            
            {todaySchedule.length === 0 ? (
              <Card className="bg-muted/30">
                <CardContent className="py-6 text-center">
                  <p className="text-muted-foreground font-tajawal">
                    {isRTL ? 'لا يوجد جدول لهذا اليوم' : 'No schedule for today'}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                {todaySchedule.map((session, idx) => {
                  const isCurrent = isCurrentPeriod(session.start_time, session.end_time);
                  return (
                    <div
                      key={idx}
                      className={`flex items-center gap-4 p-3 rounded-lg transition-colors ${
                        isCurrent ? 'bg-green-100 border border-green-300' : 'bg-muted/30'
                      }`}
                    >
                      <Badge variant={isCurrent ? 'default' : 'outline'} className={isCurrent ? 'bg-green-600' : ''}>
                        {session.period_number}
                      </Badge>
                      <span className="font-mono text-sm w-28" dir="ltr">
                        {session.start_time} - {session.end_time}
                      </span>
                      <div className="flex-1">
                        <span className="font-medium">{session.subject_name}</span>
                        <span className="text-muted-foreground mx-2">•</span>
                        <span className="text-sm text-muted-foreground">{session.teacher_name}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">{session.class_name}</span>
                      {isCurrent && <CheckCircle2 className="h-5 w-5 text-green-600" />}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Last Refresh */}
          {lastRefresh && (
            <p className="text-center text-xs text-muted-foreground">
              {isRTL ? 'آخر تحديث:' : 'Last refresh:'} {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default LiveSessionsMonitor;
