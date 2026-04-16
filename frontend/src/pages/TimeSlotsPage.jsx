import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Clock,
  Plus,
  Trash2,
  Edit,
  Sun,
  Moon,
  Globe,
  Loader2,
  ArrowLeft,
  Coffee,
  Sparkles,
  GripVertical,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Link } from 'react-router-dom';

export const TimeSlotsPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [timeSlots, setTimeSlots] = useState([]);
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedSchool, setSelectedSchool] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [seeding, setSeeding] = useState(false);
  
  const { nassaqError, nassaqWarning, nassaqConfirm } = useNassaqAlert();
  const [newSlot, setNewSlot] = useState({
    name: '',
    name_en: '',
    start_time: '07:00',
    end_time: '07:45',
    slot_number: 1,
    duration_minutes: 45,
    is_break: false,
  });

  const fetchSchools = async () => {
    try {
      const res = await api.get('/schools');
      setSchools(res.data);
      if (res.data.length > 0 && !selectedSchool) {
        setSelectedSchool(res.data[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch schools:', error);
    }
  };

  const fetchTimeSlots = async () => {
    if (!selectedSchool) return;
    
    setLoading(true);
    try {
      const res = await api.get(`/time-slots?school_id=${selectedSchool}`);
      setTimeSlots(res.data.sort((a, b) => a.slot_number - b.slot_number));
    } catch (error) {
      console.error('Failed to fetch time slots:', error);
      nassaqError(t('failedToLoadTimeSlots'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchools();
  }, []);

  useEffect(() => {
    if (selectedSchool) {
      fetchTimeSlots();
    }
  }, [selectedSchool]);

  const handleCreateSlot = async () => {
    if (!newSlot.name || !selectedSchool) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/time-slots', {
        ...newSlot,
        school_id: selectedSchool,
      });
      toast.success(t('timeSlotAddedSuccessfully'));
      setCreateDialogOpen(false);
      setNewSlot({
        name: '',
        name_en: '',
        start_time: '07:00',
        end_time: '07:45',
        slot_number: timeSlots.length + 1,
        duration_minutes: 45,
        is_break: false,
      });
      fetchTimeSlots();
    } catch (error) {
      nassaqError(error.response?.data?.detail || (t('failedToAddTimeSlot')));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteSlot = async (slotId) => {
    nassaqConfirm(
      t('areYouSureYouWantToDeleteThisTimeSlot'),
      async () => {
        try {
          await api.delete(`/time-slots/${slotId}`);
          toast.success(t('timeSlotDeleted'));
          setTimeSlots(prev => prev.filter(s => s.id !== slotId));
        } catch (error) {
          nassaqError(t('failedToDeleteTimeSlot'));
        }
      }
    );
  };

  const handleSeedTimeSlots = async () => {
    if (!selectedSchool) {
      nassaqError(t('pleaseSelectASchoolFirst'));
      return;
    }

    setSeeding(true);
    try {
      const res = await api.post(`/seed/time-slots/${selectedSchool}`);
      toast.success(isRTL ? res.data.message : `Created ${res.data.count} time slots`);
      fetchTimeSlots();
    } catch (error) {
      nassaqError(t('failedToCreateDefaultTimeSlots'));
    } finally {
      setSeeding(false);
    }
  };

  const formatTime = (time) => {
    if (!time) return '';
    const [hours, minutes] = time.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? (t('pm')) : (t('am'));
    const displayHour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
    return `${displayHour}:${minutes} ${ampm}`;
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="time-slots-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" asChild className="rounded-xl">
                <Link to="/admin/schedule">
                  <ArrowLeft className="h-5 w-5" />
                </Link>
              </Button>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  {t('timeSlotsManagement')}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {t('defineClassPeriodsAndBreaks')}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* School Selection & Actions */}
          <div className="flex flex-col md:flex-row gap-4 justify-between">
            <div className="flex gap-4 items-center">
              <Select value={selectedSchool} onValueChange={setSelectedSchool}>
                <SelectTrigger className="w-[280px] rounded-xl" data-testid="school-select">
                  <SelectValue placeholder={t('selectSchool')} />
                </SelectTrigger>
                <SelectContent>
                  {schools.map(school => (
                    <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              <Badge variant="secondary" className="rounded-lg px-3 py-1">
                <Clock className="h-4 w-4 me-1" />
                {timeSlots.filter(s => !s.is_break).length} {t('periods')}
              </Badge>
            </div>

            <div className="flex gap-3">
              {timeSlots.length === 0 && selectedSchool && (
                <Button 
                  variant="outline" 
                  onClick={handleSeedTimeSlots}
                  disabled={seeding}
                  className="rounded-xl"
                  data-testid="seed-slots-btn"
                >
                  {seeding ? (
                    <Loader2 className="h-5 w-5 animate-spin me-2" />
                  ) : (
                    <Sparkles className="h-5 w-5 me-2" />
                  )}
                  {t('createDefaultSlots')}
                </Button>
              )}
              
              <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" data-testid="add-slot-btn">
                    <Plus className="h-5 w-5 me-2" />
                    {t('addTimeSlot')}
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[500px]">
                  <DialogHeader>
                    <DialogTitle className="font-cairo">
                      {t('addNewTimeSlot')}
                    </DialogTitle>
                    <DialogDescription>
                      {t('defineTheTimeSlotDetails')}
                    </DialogDescription>
                  </DialogHeader>
                  
                  <div className="grid gap-4 py-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t('nameArabic2')}</Label>
                        <Input
                          value={newSlot.name}
                          onChange={(e) => setNewSlot({ ...newSlot, name: e.target.value })}
                          placeholder={t('firstPeriod2')}
                          className="rounded-xl"
                          data-testid="slot-name-input"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t('nameEnglish')}</Label>
                        <Input
                          value={newSlot.name_en}
                          onChange={(e) => setNewSlot({ ...newSlot, name_en: e.target.value })}
                          placeholder="Period 1"
                          className="rounded-xl"
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t('startTime')}</Label>
                        <Input
                          type="time"
                          value={newSlot.start_time}
                          onChange={(e) => setNewSlot({ ...newSlot, start_time: e.target.value })}
                          className="rounded-xl"
                          data-testid="slot-start-input"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t('endTime')}</Label>
                        <Input
                          type="time"
                          value={newSlot.end_time}
                          onChange={(e) => setNewSlot({ ...newSlot, end_time: e.target.value })}
                          className="rounded-xl"
                          data-testid="slot-end-input"
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t('slotOrder')}</Label>
                        <Input
                          type="number"
                          min={1}
                          value={newSlot.slot_number}
                          onChange={(e) => setNewSlot({ ...newSlot, slot_number: parseInt(e.target.value) || 1 })}
                          className="rounded-xl"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t('durationMinutes')}</Label>
                        <Input
                          type="number"
                          min={1}
                          value={newSlot.duration_minutes}
                          onChange={(e) => setNewSlot({ ...newSlot, duration_minutes: parseInt(e.target.value) || 45 })}
                          className="rounded-xl"
                        />
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between p-4 bg-muted/50 rounded-xl">
                      <div className="flex items-center gap-3">
                        <Coffee className="h-5 w-5 text-amber-500" />
                        <div>
                          <Label className="font-medium">{t('breakPeriod')}</Label>
                          <p className="text-xs text-muted-foreground">
                            {t('markAsBreakTime')}
                          </p>
                        </div>
                      </div>
                      <Switch
                        checked={newSlot.is_break}
                        onCheckedChange={(checked) => setNewSlot({ ...newSlot, is_break: checked })}
                        data-testid="slot-break-switch"
                      />
                    </div>
                  </div>
                  
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                      {t('cancel')}
                    </Button>
                    <Button 
                      onClick={handleCreateSlot} 
                      className="bg-brand-navy rounded-xl" 
                      disabled={submitting}
                      data-testid="create-slot-btn"
                    >
                      {submitting ? (
                        <><Loader2 className="h-4 w-4 animate-spin me-2" />{t('adding')}</>
                      ) : (
                        t('add')
                      )}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Time Slots Grid */}
          <Card className="card-nassaq">
            <CardHeader className="pb-4">
              <CardTitle className="font-cairo text-lg flex items-center gap-2">
                <Clock className="h-5 w-5 text-brand-turquoise" />
                {t('timeSlots')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : timeSlots.length === 0 ? (
                <div className="text-center py-16">
                  <Clock className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                  <p className="text-muted-foreground mb-4">
                    {t('noTimeSlotsDefined')}
                  </p>
                  <Button onClick={handleSeedTimeSlots} disabled={seeding} variant="outline" className="rounded-xl">
                    {seeding ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Sparkles className="h-4 w-4 me-2" />}
                    {t('createDefaultSlots')}
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {timeSlots.map((slot, index) => (
                    <div
                      key={slot.id}
                      className={`flex items-center justify-between p-4 rounded-2xl border transition-all hover:shadow-md ${
                        slot.is_break 
                          ? 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800' 
                          : 'bg-card border-border hover:border-brand-turquoise/50'
                      }`}
                      data-testid={`time-slot-${slot.id}`}
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <GripVertical className="h-5 w-5 cursor-move" />
                          <span className="w-8 h-8 flex items-center justify-center rounded-lg bg-muted font-bold text-sm">
                            {slot.slot_number}
                          </span>
                        </div>
                        
                        <div>
                          <div className="font-medium flex items-center gap-2">
                            {slot.is_break && <Coffee className="h-4 w-4 text-amber-500" />}
                            {isRTL ? slot.name : (slot.name_en || slot.name)}
                          </div>
                          <div className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                            <Clock className="h-3 w-3" />
                            {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
                            <Badge variant="secondary" className="ms-2 text-xs">
                              {slot.duration_minutes} {t('minutes')}
                            </Badge>
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {slot.is_break ? (
                          <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">
                            {t('break')}
                          </Badge>
                        ) : (
                          <Badge className="bg-brand-turquoise/10 text-brand-turquoise">
                            {t('periodLabel')}
                          </Badge>
                        )}
                        
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="rounded-xl text-red-500 hover:text-red-600 hover:bg-red-50"
                          onClick={() => handleDeleteSlot(slot.id)}
                          data-testid={`delete-slot-${slot.id}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Summary Card */}
          {timeSlots.length > 0 && (
            <Card className="card-nassaq bg-gradient-to-br from-brand-navy/5 to-brand-turquoise/5">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex gap-8">
                    <div className="text-center">
                      <div className="text-3xl font-bold text-brand-navy dark:text-brand-turquoise">
                        {timeSlots.filter(s => !s.is_break).length}
                      </div>
                      <div className="text-sm text-muted-foreground">{t('classPeriods')}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-amber-500">
                        {timeSlots.filter(s => s.is_break).length}
                      </div>
                      <div className="text-sm text-muted-foreground">{t('breakPeriods')}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-3xl font-bold text-brand-purple">
                        {timeSlots.reduce((acc, s) => acc + (s.is_break ? 0 : s.duration_minutes), 0)}
                      </div>
                      <div className="text-sm text-muted-foreground">{t('teachingMinutes')}</div>
                    </div>
                  </div>
                  <div className="text-end">
                    <p className="text-sm text-muted-foreground">
                      {t('schoolDay')}
                    </p>
                    <p className="font-medium">
                      {formatTime(timeSlots[0]?.start_time)} - {formatTime(timeSlots[timeSlots.length - 1]?.end_time)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
