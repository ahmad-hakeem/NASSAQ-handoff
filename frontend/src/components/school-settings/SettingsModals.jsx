import React from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Coffee, UserX, DoorClosed } from 'lucide-react';

export function SettingsModals({ hook }) {
  const {
    showBreakModal, setShowBreakModal, editingBreak, handleSaveBreak,
    showUnavailabilityModal, setShowUnavailabilityModal, unavailabilityType,
    handleSaveUnavailability, teachers, classes,
  } = hook;

  return (
    <>
      {showBreakModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir="rtl">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="p-6 border-b">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Coffee className="h-5 w-5 text-[#1C3D74]" />
                {editingBreak ? 'تعديل الفترة' : 'إضافة فترة جديدة'}
              </h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              handleSaveBreak({
                name: formData.get('name'),
                type: formData.get('type'),
                afterPeriod: parseInt(formData.get('afterPeriod')),
                duration: parseInt(formData.get('duration'))
              });
            }} className="p-6 space-y-4">
              <div>
                <Label>اسم الفترة</Label>
                <Input name="name" defaultValue={editingBreak?.name || ''} placeholder="مثال: الاستراحة الأولى" required className="mt-1" />
              </div>
              <div>
                <Label>نوع الفترة</Label>
                <Select name="type" defaultValue={editingBreak?.type || 'break'}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="break">استراحة</SelectItem>
                    <SelectItem value="prayer">صلاة</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>بعد الحصة رقم</Label>
                  <Select name="afterPeriod" defaultValue={String(editingBreak?.afterPeriod || 2)}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {[1,2,3,4,5,6,7,8].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>المدة (دقيقة)</Label>
                  <Select name="duration" defaultValue={String(editingBreak?.duration || 15)}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {[5, 10, 15, 20, 25, 30].map(n => <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowBreakModal(false)}>إلغاء</Button>
                <Button type="submit" className="bg-[#1C3D74]">{editingBreak ? 'تحديث' : 'إضافة'}</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showUnavailabilityModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir="rtl">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="p-6 border-b">
              <h3 className="text-lg font-bold flex items-center gap-2">
                {unavailabilityType === 'teacher' ? <UserX className="h-5 w-5 text-amber-600" /> : <DoorClosed className="h-5 w-5 text-red-600" />}
                إضافة فترة عدم توفر {unavailabilityType === 'teacher' ? 'معلم' : 'فصل'}
              </h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              handleSaveUnavailability({
                [unavailabilityType === 'teacher' ? 'teacher_id' : 'class_id']: formData.get('entity_id'),
                [unavailabilityType === 'teacher' ? 'teacher_name' : 'class_name']: formData.get('entity_name'),
                day: formData.get('day'),
                period: formData.get('period')
              });
            }} className="p-6 space-y-4">
              <div>
                <Label>{unavailabilityType === 'teacher' ? 'اختر المعلم' : 'اختر الفصل'}</Label>
                <Select name="entity_id" required>
                  <SelectTrigger className="mt-1"><SelectValue placeholder={unavailabilityType === 'teacher' ? 'اختر معلم' : 'اختر فصل'} /></SelectTrigger>
                  <SelectContent>
                    {unavailabilityType === 'teacher'
                      ? teachers.map(t => <SelectItem key={t.id} value={t.id}>{t.full_name}</SelectItem>)
                      : classes.map(c => <SelectItem key={c.id} value={c.id}>{c.name} - {c.section}</SelectItem>)
                    }
                  </SelectContent>
                </Select>
                <input type="hidden" name="entity_name" value="" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>اليوم</Label>
                  <Select name="day" required>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="اختر اليوم" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="الأحد">الأحد</SelectItem>
                      <SelectItem value="الإثنين">الإثنين</SelectItem>
                      <SelectItem value="الثلاثاء">الثلاثاء</SelectItem>
                      <SelectItem value="الأربعاء">الأربعاء</SelectItem>
                      <SelectItem value="الخميس">الخميس</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>الحصة</Label>
                  <Select name="period" required>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="اختر الحصة" /></SelectTrigger>
                    <SelectContent>
                      {[1,2,3,4,5,6,7].map(n => <SelectItem key={n} value={String(n)}>الحصة {n}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowUnavailabilityModal(false)}>إلغاء</Button>
                <Button type="submit" className={unavailabilityType === 'teacher' ? 'bg-amber-600' : 'bg-red-600'}>إضافة</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
