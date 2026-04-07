import React, { useState, useEffect } from 'react';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { toast } from 'sonner';
import {
  User, Mail, Phone, MapPin, Shield, Eye, EyeOff, Copy, Check,
  ChevronLeft, ChevronRight, UserPlus, Settings, Lock, Send,
  CheckCircle2, XCircle, Plus, AlertTriangle, Sparkles,
  Building2, Users, BarChart3, Activity, FileText, Brain,
  GraduationCap, UserCheck, CalendarCheck, Bell, MessageSquare,
  Link2, Archive, Server, Database, Key, School, LayoutDashboard
} from 'lucide-react';

import { useTranslation } from '../../contexts/ThemeContext';
// =============================================================
// مناطق ومدن المملكة العربية السعودية
// =============================================================

const SAUDI_REGIONS = [
  {
    id: 'riyadh',
    name: 'منطقة الرياض',
    name_en: 'Riyadh Region',
    cities: [
      { id: 'riyadh', name: 'الرياض', name_en: 'Riyadh' },
      { id: 'kharj', name: 'الخرج', name_en: 'Al-Kharj' },
      { id: 'dawadmi', name: 'الدوادمي', name_en: 'Dawadmi' },
      { id: 'majmaah', name: 'المجمعة', name_en: 'Al-Majmaah' },
      { id: 'quwayiyah', name: 'القويعية', name_en: 'Al-Quwayiyah' },
      { id: 'wadi_dawasir', name: 'وادي الدواسر', name_en: 'Wadi Al-Dawasir' },
      { id: 'aflaj', name: 'الأفلاج', name_en: 'Al-Aflaj' },
      { id: 'zulfi', name: 'الزلفي', name_en: 'Az-Zulfi' },
      { id: 'shaqra', name: 'شقراء', name_en: 'Shaqra' },
      { id: 'hotat_bani_tamim', name: 'حوطة بني تميم', name_en: 'Hotat Bani Tamim' },
      { id: 'afif', name: 'عفيف', name_en: 'Afif' },
      { id: 'sulayil', name: 'السليل', name_en: 'As-Sulayyil' },
      { id: 'dhruma', name: 'ضرما', name_en: 'Dhurma' },
      { id: 'muzahimiyah', name: 'المزاحمية', name_en: 'Al-Muzahimiyah' },
      { id: 'rumah', name: 'رماح', name_en: 'Rumah' },
      { id: 'thadiq', name: 'ثادق', name_en: 'Thadiq' },
      { id: 'huraymila', name: 'حريملاء', name_en: 'Huraymila' },
      { id: 'diriyah', name: 'الدرعية', name_en: 'Diriyah' },
    ],
    educationalDepartments: [
      { id: 'riyadh_edu', name: 'إدارة تعليم الرياض', name_en: 'Riyadh Education' },
      { id: 'kharj_edu', name: 'إدارة تعليم الخرج', name_en: 'Al-Kharj Education' },
      { id: 'dawadmi_edu', name: 'إدارة تعليم الدوادمي', name_en: 'Dawadmi Education' },
      { id: 'majmaah_edu', name: 'إدارة تعليم المجمعة', name_en: 'Al-Majmaah Education' },
      { id: 'quwayiyah_edu', name: 'إدارة تعليم القويعية', name_en: 'Al-Quwayiyah Education' },
      { id: 'wadi_dawasir_edu', name: 'إدارة تعليم وادي الدواسر', name_en: 'Wadi Al-Dawasir Education' },
      { id: 'aflaj_edu', name: 'إدارة تعليم الأفلاج', name_en: 'Al-Aflaj Education' },
      { id: 'zulfi_edu', name: 'إدارة تعليم الزلفي', name_en: 'Az-Zulfi Education' },
      { id: 'shaqra_edu', name: 'إدارة تعليم شقراء', name_en: 'Shaqra Education' },
      { id: 'hotat_bani_tamim_edu', name: 'إدارة تعليم حوطة بني تميم', name_en: 'Hotat Bani Tamim Education' },
      { id: 'afif_edu', name: 'إدارة تعليم عفيف', name_en: 'Afif Education' },
    ]
  },
  {
    id: 'makkah',
    name: 'منطقة مكة المكرمة',
    name_en: 'Makkah Region',
    cities: [
      { id: 'makkah', name: 'مكة المكرمة', name_en: 'Makkah' },
      { id: 'jeddah', name: 'جدة', name_en: 'Jeddah' },
      { id: 'taif', name: 'الطائف', name_en: 'Taif' },
      { id: 'qunfudhah', name: 'القنفذة', name_en: 'Al-Qunfudhah' },
      { id: 'lith', name: 'الليث', name_en: 'Al-Lith' },
      { id: 'rabigh', name: 'رابغ', name_en: 'Rabigh' },
      { id: 'khulais', name: 'خليص', name_en: 'Khulais' },
      { id: 'jumum', name: 'الجموم', name_en: 'Al-Jumum' },
      { id: 'kamil', name: 'الكامل', name_en: 'Al-Kamil' },
      { id: 'moya', name: 'ميسان', name_en: 'Maysan' },
      { id: 'adham', name: 'أضم', name_en: 'Adham' },
      { id: 'turubah', name: 'تربة', name_en: 'Turubah' },
      { id: 'ranyah', name: 'رنية', name_en: 'Ranyah' },
      { id: 'khurma', name: 'الخرمة', name_en: 'Al-Khurma' },
      { id: 'muwayh', name: 'المويه', name_en: 'Al-Muwayh' },
    ],
    educationalDepartments: [
      { id: 'makkah_edu', name: 'إدارة تعليم مكة المكرمة', name_en: 'Makkah Education' },
      { id: 'jeddah_edu', name: 'إدارة تعليم جدة', name_en: 'Jeddah Education' },
      { id: 'taif_edu', name: 'إدارة تعليم الطائف', name_en: 'Taif Education' },
      { id: 'qunfudhah_edu', name: 'إدارة تعليم القنفذة', name_en: 'Al-Qunfudhah Education' },
      { id: 'lith_edu', name: 'إدارة تعليم الليث', name_en: 'Al-Lith Education' },
    ]
  },
  {
    id: 'madinah',
    name: 'منطقة المدينة المنورة',
    name_en: 'Madinah Region',
    cities: [
      { id: 'madinah', name: 'المدينة المنورة', name_en: 'Madinah' },
      { id: 'yanbu', name: 'ينبع', name_en: 'Yanbu' },
      { id: 'ula', name: 'العلا', name_en: 'Al-Ula' },
      { id: 'mahd', name: 'مهد الذهب', name_en: 'Mahd Al-Dhahab' },
      { id: 'badr', name: 'بدر', name_en: 'Badr' },
      { id: 'khaybar', name: 'خيبر', name_en: 'Khaybar' },
      { id: 'hanakiyah', name: 'الحناكية', name_en: 'Al-Hanakiyah' },
    ],
    educationalDepartments: [
      { id: 'madinah_edu', name: 'إدارة تعليم المدينة المنورة', name_en: 'Madinah Education' },
      { id: 'yanbu_edu', name: 'إدارة تعليم ينبع', name_en: 'Yanbu Education' },
      { id: 'ula_edu', name: 'إدارة تعليم العلا', name_en: 'Al-Ula Education' },
      { id: 'mahd_edu', name: 'إدارة تعليم مهد الذهب', name_en: 'Mahd Al-Dhahab Education' },
    ]
  },
  {
    id: 'eastern',
    name: 'المنطقة الشرقية',
    name_en: 'Eastern Province',
    cities: [
      { id: 'dammam', name: 'الدمام', name_en: 'Dammam' },
      { id: 'dhahran', name: 'الظهران', name_en: 'Dhahran' },
      { id: 'khobar', name: 'الخبر', name_en: 'Al-Khobar' },
      { id: 'qatif', name: 'القطيف', name_en: 'Qatif' },
      { id: 'jubail', name: 'الجبيل', name_en: 'Jubail' },
      { id: 'hofuf', name: 'الهفوف', name_en: 'Al-Hofuf' },
      { id: 'mubarraz', name: 'المبرز', name_en: 'Al-Mubarraz' },
      { id: 'hafr_albatin', name: 'حفر الباطن', name_en: 'Hafr Al-Batin' },
      { id: 'ras_tanura', name: 'رأس تنورة', name_en: 'Ras Tanura' },
      { id: 'buqayq', name: 'بقيق', name_en: 'Buqayq' },
      { id: 'khafji', name: 'الخفجي', name_en: 'Al-Khafji' },
      { id: 'nuayriyah', name: 'النعيرية', name_en: "An-Nu'ayriyah" },
      { id: 'qaryat_ulya', name: 'قرية العليا', name_en: "Qaryat Al-'Ulya" },
    ],
    educationalDepartments: [
      { id: 'eastern_edu', name: 'إدارة تعليم المنطقة الشرقية', name_en: 'Eastern Province Education' },
      { id: 'ahsa_edu', name: 'إدارة تعليم الأحساء', name_en: 'Al-Ahsa Education' },
      { id: 'hafr_edu', name: 'إدارة تعليم حفر الباطن', name_en: 'Hafr Al-Batin Education' },
    ]
  },
  {
    id: 'asir',
    name: 'منطقة عسير',
    name_en: 'Asir Region',
    cities: [
      { id: 'abha', name: 'أبها', name_en: 'Abha' },
      { id: 'khamis_mushait', name: 'خميس مشيط', name_en: 'Khamis Mushait' },
      { id: 'bisha', name: 'بيشة', name_en: 'Bisha' },
      { id: 'namas', name: 'النماص', name_en: 'An-Namas' },
      { id: 'muhayil', name: 'محايل عسير', name_en: 'Muhayil Asir' },
      { id: 'sarat_abidah', name: 'سراة عبيدة', name_en: 'Sarat Abidah' },
      { id: 'rijal_alma', name: 'رجال ألمع', name_en: 'Rijal Almaa' },
      { id: 'ahad_rufaydah', name: 'أحد رفيدة', name_en: 'Ahad Rufaydah' },
      { id: 'dhahran_aljanoub', name: 'ظهران الجنوب', name_en: 'Dhahran Al-Janoub' },
      { id: 'tathlith', name: 'تثليث', name_en: 'Tathlith' },
      { id: 'balqarn', name: 'بلقرن', name_en: 'Balqarn' },
      { id: 'majardah', name: 'المجاردة', name_en: 'Al-Majardah' },
      { id: 'bariq', name: 'بارق', name_en: 'Bariq' },
    ],
    educationalDepartments: [
      { id: 'asir_edu', name: 'إدارة تعليم عسير', name_en: 'Asir Education' },
      { id: 'bisha_edu', name: 'إدارة تعليم بيشة', name_en: 'Bisha Education' },
      { id: 'namas_edu', name: 'إدارة تعليم النماص', name_en: 'An-Namas Education' },
      { id: 'muhayil_edu', name: 'إدارة تعليم محايل عسير', name_en: 'Muhayil Asir Education' },
      { id: 'sarat_abidah_edu', name: 'إدارة تعليم سراة عبيدة', name_en: 'Sarat Abidah Education' },
    ]
  },
  {
    id: 'qassim',
    name: 'منطقة القصيم',
    name_en: 'Qassim Region',
    cities: [
      { id: 'buraidah', name: 'بريدة', name_en: 'Buraidah' },
      { id: 'unayzah', name: 'عنيزة', name_en: 'Unayzah' },
      { id: 'rass', name: 'الرس', name_en: 'Ar-Rass' },
      { id: 'bukayriyah', name: 'البكيرية', name_en: 'Al-Bukayriyah' },
      { id: 'badaya', name: 'البدائع', name_en: 'Al-Badaya' },
      { id: 'mithnab', name: 'المذنب', name_en: 'Al-Mithnab' },
      { id: 'shimasiyah', name: 'الشماسية', name_en: 'Ash-Shimasiyah' },
      { id: 'asyah', name: 'عيون الجواء', name_en: "Uyun Al-Jawa" },
      { id: 'riyadh_alkhabra', name: 'رياض الخبراء', name_en: 'Riyadh Al-Khabra' },
    ],
    educationalDepartments: [
      { id: 'qassim_edu', name: 'إدارة تعليم القصيم', name_en: 'Qassim Education' },
      { id: 'rass_edu', name: 'إدارة تعليم الرس', name_en: 'Ar-Rass Education' },
    ]
  },
  {
    id: 'tabuk',
    name: 'منطقة تبوك',
    name_en: 'Tabuk Region',
    cities: [
      { id: 'tabuk', name: 'تبوك', name_en: 'Tabuk' },
      { id: 'umluj', name: 'أملج', name_en: 'Umluj' },
      { id: 'wajh', name: 'الوجه', name_en: 'Al-Wajh' },
      { id: 'duba', name: 'ضباء', name_en: 'Duba' },
      { id: 'tayma', name: 'تيماء', name_en: 'Tayma' },
      { id: 'haql', name: 'حقل', name_en: 'Haql' },
    ],
    educationalDepartments: [
      { id: 'tabuk_edu', name: 'إدارة تعليم تبوك', name_en: 'Tabuk Education' },
      { id: 'wajh_edu', name: 'إدارة تعليم الوجه', name_en: 'Al-Wajh Education' },
    ]
  },
  {
    id: 'hail',
    name: 'منطقة حائل',
    name_en: 'Hail Region',
    cities: [
      { id: 'hail', name: 'حائل', name_en: 'Hail' },
      { id: 'baqaa', name: 'بقعاء', name_en: "Baqa'a" },
      { id: 'ghazalah', name: 'الغزالة', name_en: 'Al-Ghazalah' },
      { id: 'shinan', name: 'الشنان', name_en: 'Ash-Shinan' },
      { id: 'shamli', name: 'الشملي', name_en: 'Ash-Shamli' },
    ],
    educationalDepartments: [
      { id: 'hail_edu', name: 'إدارة تعليم حائل', name_en: 'Hail Education' },
    ]
  },
  {
    id: 'northern_borders',
    name: 'منطقة الحدود الشمالية',
    name_en: 'Northern Borders Region',
    cities: [
      { id: 'arar', name: 'عرعر', name_en: 'Arar' },
      { id: 'rafha', name: 'رفحاء', name_en: 'Rafha' },
      { id: 'turayf', name: 'طريف', name_en: 'Turayf' },
    ],
    educationalDepartments: [
      { id: 'northern_borders_edu', name: 'إدارة تعليم الحدود الشمالية', name_en: 'Northern Borders Education' },
    ]
  },
  {
    id: 'jazan',
    name: 'منطقة جازان',
    name_en: 'Jazan Region',
    cities: [
      { id: 'jazan', name: 'جازان', name_en: 'Jazan' },
      { id: 'sabya', name: 'صبيا', name_en: 'Sabya' },
      { id: 'abu_arish', name: 'أبو عريش', name_en: 'Abu Arish' },
      { id: 'samtah', name: 'صامطة', name_en: 'Samtah' },
      { id: 'ahad_almasarihah', name: 'أحد المسارحة', name_en: 'Ahad Al-Masarihah' },
      { id: 'damad', name: 'ضمد', name_en: 'Damad' },
      { id: 'farasan', name: 'فرسان', name_en: 'Farasan' },
    ],
    educationalDepartments: [
      { id: 'jazan_edu', name: 'إدارة تعليم جازان', name_en: 'Jazan Education' },
      { id: 'sabya_edu', name: 'إدارة تعليم صبيا', name_en: 'Sabya Education' },
    ]
  },
  {
    id: 'najran',
    name: 'منطقة نجران',
    name_en: 'Najran Region',
    cities: [
      { id: 'najran', name: 'نجران', name_en: 'Najran' },
      { id: 'sharorah', name: 'شرورة', name_en: 'Sharorah' },
      { id: 'habuna', name: 'حبونا', name_en: 'Habuna' },
      { id: 'badr_aljanoub', name: 'بدر الجنوب', name_en: 'Badr Al-Janoub' },
    ],
    educationalDepartments: [
      { id: 'najran_edu', name: 'إدارة تعليم نجران', name_en: 'Najran Education' },
      { id: 'sharorah_edu', name: 'إدارة تعليم شرورة', name_en: 'Sharorah Education' },
    ]
  },
  {
    id: 'bahah',
    name: 'منطقة الباحة',
    name_en: 'Al-Bahah Region',
    cities: [
      { id: 'bahah', name: 'الباحة', name_en: 'Al-Bahah' },
      { id: 'baljurashi', name: 'بلجرشي', name_en: 'Baljurashi' },
      { id: 'mandaq', name: 'المندق', name_en: 'Al-Mandaq' },
      { id: 'makhwah', name: 'المخواة', name_en: 'Al-Makhwah' },
      { id: 'qilwah', name: 'قلوة', name_en: 'Qilwah' },
    ],
    educationalDepartments: [
      { id: 'bahah_edu', name: 'إدارة تعليم الباحة', name_en: 'Al-Bahah Education' },
    ]
  },
  {
    id: 'jouf',
    name: 'منطقة الجوف',
    name_en: 'Al-Jouf Region',
    cities: [
      { id: 'sakakah', name: 'سكاكا', name_en: 'Sakakah' },
      { id: 'dumat_aljandal', name: 'دومة الجندل', name_en: 'Dumat Al-Jandal' },
      { id: 'qurayyat', name: 'القريات', name_en: 'Al-Qurayyat' },
      { id: 'tabarjal', name: 'طبرجل', name_en: 'Tabarjal' },
    ],
    educationalDepartments: [
      { id: 'jouf_edu', name: 'إدارة تعليم الجوف', name_en: 'Al-Jouf Education' },
      { id: 'qurayyat_edu', name: 'إدارة تعليم القريات', name_en: 'Al-Qurayyat Education' },
    ]
  },
];

// =============================================================
// نظام الأدوار والصلاحيات - Roles & Permissions System (RBAC)
// =============================================================

const AVAILABLE_ROLES = [
  {
    id: 'platform_admin',
    name: 'مدير منصة',
    name_en: 'Platform Admin',
    description: 'صلاحيات كاملة للتحكم في جميع جوانب المنصة',
    description_en: 'Full access to all platform features',
    icon: Shield,
    color: 'bg-brand-navy',
  },
  {
    id: 'platform_sub_admin',
    name: 'نائب مدير منصة',
    name_en: 'Platform Sub-Admin',
    description: 'صلاحيات إدارية مع بعض القيود',
    description_en: 'Administrative permissions with some limitations',
    icon: Users,
    color: 'bg-blue-600',
  },
  {
    id: 'independent_teacher',
    name: 'معلم مستقل',
    name_en: 'Independent Teacher',
    description: 'معلم غير مرتبط بمدرسة محددة، يمكنه العمل مع عدة مدارس',
    description_en: 'Teacher not affiliated with a specific school',
    icon: GraduationCap,
    color: 'bg-violet-500',
  },
];

// تعريف الصلاحيات (مختصرة للمعلم)
const TEACHER_PERMISSIONS = [
  { id: 'view_classes', name: 'عرض الفصول', name_en: 'View Classes', icon: Building2 },
  { id: 'manage_own_class', name: 'إدارة فصله الخاص', name_en: 'Manage Own Class', icon: Settings },
  { id: 'view_class_students', name: 'عرض طلاب فصوله', name_en: 'View Class Students', icon: Users },
  { id: 'record_attendance', name: 'تسجيل الحضور', name_en: 'Record Attendance', icon: CalendarCheck },
  { id: 'create_assignments', name: 'إنشاء واجبات', name_en: 'Create Assignments', icon: FileText },
  { id: 'grade_assignments', name: 'تصحيح الواجبات', name_en: 'Grade Assignments', icon: CheckCircle2 },
  { id: 'enter_grades', name: 'إدخال الدرجات', name_en: 'Enter Grades', icon: BarChart3 },
  { id: 'view_student_reports', name: 'عرض تقارير الطلاب', name_en: 'View Student Reports', icon: FileText },
  { id: 'message_students', name: 'مراسلة الطلاب', name_en: 'Message Students', icon: MessageSquare },
  { id: 'message_parents', name: 'مراسلة أولياء الأمور', name_en: 'Message Parents', icon: MessageSquare },
  { id: 'use_ai_assistant', name: 'استخدام مساعد AI التعليمي', name_en: 'Use AI Teaching Assistant', icon: Brain },
];

// صلاحيات مدير المنصة
const PLATFORM_ADMIN_PERMISSIONS = [
  { id: 'manage_schools', name: 'إدارة المدارس', name_en: 'Manage Schools', icon: Building2 },
  { id: 'manage_users', name: 'إدارة المستخدمين', name_en: 'Manage Users', icon: Users },
  { id: 'manage_roles', name: 'إدارة الأدوار والصلاحيات', name_en: 'Manage Roles & Permissions', icon: Shield },
  { id: 'view_reports', name: 'عرض التقارير', name_en: 'View Reports', icon: BarChart3 },
  { id: 'manage_rules', name: 'إدارة القواعد', name_en: 'Manage Rules', icon: FileText },
  { id: 'system_settings', name: 'إعدادات النظام', name_en: 'System Settings', icon: Settings },
  { id: 'security_center', name: 'مركز الأمان', name_en: 'Security Center', icon: Shield },
  { id: 'integrations', name: 'التكاملات', name_en: 'Integrations', icon: Link2 },
  { id: 'communications', name: 'الاتصالات والإشعارات', name_en: 'Communications', icon: Bell },
  { id: 'ai_tools', name: 'أدوات الذكاء الاصطناعي', name_en: 'AI Tools', icon: Brain },
  { id: 'audit_logs', name: 'سجلات المراجعة', name_en: 'Audit Logs', icon: Activity },
];

// صلاحيات نائب مدير المنصة
const PLATFORM_SUB_ADMIN_PERMISSIONS = [
  { id: 'view_dashboard', name: 'عرض لوحة التحكم', name_en: 'View Dashboard', icon: LayoutDashboard },
  { id: 'view_schools', name: 'عرض المدارس', name_en: 'View Schools', icon: Building2 },
  { id: 'view_users', name: 'عرض المستخدمين', name_en: 'View Users', icon: Users },
  { id: 'manage_support', name: 'إدارة الدعم الفني', name_en: 'Manage Support', icon: MessageSquare },
  { id: 'view_reports', name: 'عرض التقارير', name_en: 'View Reports', icon: BarChart3 },
  { id: 'view_activity', name: 'عرض سجل النشاط', name_en: 'View Activity Log', icon: Activity },
  { id: 'manage_teacher_requests', name: 'إدارة طلبات المعلمين', name_en: 'Manage Teacher Requests', icon: UserCheck },
];

// صلاحيات المعلم المستقل
const INDEPENDENT_TEACHER_PERMISSIONS = [
  { id: 'view_schools', name: 'عرض المدارس المتاحة', name_en: 'View Available Schools', icon: Building2 },
  { id: 'apply_to_schools', name: 'التقدم للمدارس', name_en: 'Apply to Schools', icon: FileText },
  { id: 'manage_profile', name: 'إدارة الملف الشخصي', name_en: 'Manage Profile', icon: User },
  { id: 'view_own_schedule', name: 'عرض الجدول الشخصي', name_en: 'View Own Schedule', icon: CalendarCheck },
  { id: 'use_ai_assistant', name: 'استخدام مساعد AI', name_en: 'Use AI Assistant', icon: Brain },
];

// صلاحيات مدير العمليات
const OPERATIONS_MANAGER_PERMISSIONS = [
  { id: 'view_dashboard', name: 'عرض لوحة التحكم', name_en: 'View Dashboard', icon: LayoutDashboard },
  { id: 'view_schools', name: 'عرض المدارس', name_en: 'View Schools', icon: Building2 },
  { id: 'view_users', name: 'عرض المستخدمين', name_en: 'View Users', icon: Users },
  { id: 'view_reports', name: 'عرض التقارير', name_en: 'View Reports', icon: BarChart3 },
  { id: 'manage_support', name: 'إدارة الدعم الفني', name_en: 'Manage Support', icon: MessageSquare },
  { id: 'view_activity', name: 'عرض سجل النشاط', name_en: 'View Activity Log', icon: Activity },
];

// صلاحيات المسؤول التقني
const TECHNICAL_ADMIN_PERMISSIONS = [
  { id: 'system_monitoring', name: 'مراقبة النظام', name_en: 'System Monitoring', icon: Activity },
  { id: 'manage_integrations', name: 'إدارة التكاملات', name_en: 'Manage Integrations', icon: Link2 },
  { id: 'manage_database', name: 'إدارة قاعدة البيانات', name_en: 'Manage Database', icon: Database },
  { id: 'manage_servers', name: 'إدارة الخوادم', name_en: 'Manage Servers', icon: Server },
  { id: 'security_settings', name: 'إعدادات الأمان', name_en: 'Security Settings', icon: Shield },
  { id: 'api_management', name: 'إدارة الـ APIs', name_en: 'API Management', icon: Key },
];

// صلاحيات مسؤول الدعم
const SUPPORT_SPECIALIST_PERMISSIONS = [
  { id: 'view_tickets', name: 'عرض التذاكر', name_en: 'View Tickets', icon: FileText },
  { id: 'respond_tickets', name: 'الرد على التذاكر', name_en: 'Respond to Tickets', icon: MessageSquare },
  { id: 'view_users', name: 'عرض المستخدمين', name_en: 'View Users', icon: Users },
  { id: 'reset_passwords', name: 'إعادة تعيين كلمات المرور', name_en: 'Reset Passwords', icon: Key },
  { id: 'view_activity', name: 'عرض سجل النشاط', name_en: 'View Activity Log', icon: Activity },
];

// صلاحيات محلل البيانات
const DATA_ANALYST_PERMISSIONS = [
  { id: 'view_reports', name: 'عرض التقارير', name_en: 'View Reports', icon: BarChart3 },
  { id: 'export_data', name: 'تصدير البيانات', name_en: 'Export Data', icon: Archive },
  { id: 'view_analytics', name: 'عرض التحليلات', name_en: 'View Analytics', icon: Activity },
  { id: 'create_reports', name: 'إنشاء التقارير', name_en: 'Create Reports', icon: FileText },
];

// صلاحيات مسؤول الأمان
const SECURITY_OFFICER_PERMISSIONS = [
  { id: 'security_monitoring', name: 'مراقبة الأمان', name_en: 'Security Monitoring', icon: Shield },
  { id: 'audit_logs', name: 'سجلات المراجعة', name_en: 'Audit Logs', icon: Activity },
  { id: 'manage_access', name: 'إدارة الوصول', name_en: 'Manage Access', icon: Key },
  { id: 'incident_response', name: 'الاستجابة للحوادث', name_en: 'Incident Response', icon: AlertTriangle },
  { id: 'security_reports', name: 'تقارير الأمان', name_en: 'Security Reports', icon: FileText },
];

// صلاحيات حساب الاختبار
const TESTING_ACCOUNT_PERMISSIONS = [
  { id: 'test_features', name: 'اختبار الميزات', name_en: 'Test Features', icon: Settings },
  { id: 'view_test_data', name: 'عرض بيانات الاختبار', name_en: 'View Test Data', icon: Database },
];

// دالة للحصول على الصلاحيات حسب الدور
const getPermissionsByRole = (roleId) => {
  const { t } = useTranslation();
  switch (roleId) {
    case 'platform_admin':
      return PLATFORM_ADMIN_PERMISSIONS;
    case 'platform_sub_admin':
      return PLATFORM_SUB_ADMIN_PERMISSIONS;
    case 'independent_teacher':
      return INDEPENDENT_TEACHER_PERMISSIONS;
    case 'platform_operations_manager':
      return OPERATIONS_MANAGER_PERMISSIONS;
    case 'platform_technical_admin':
      return TECHNICAL_ADMIN_PERMISSIONS;
    case 'platform_support_specialist':
      return SUPPORT_SPECIALIST_PERMISSIONS;
    case 'platform_data_analyst':
      return DATA_ANALYST_PERMISSIONS;
    case 'platform_security_officer':
      return SECURITY_OFFICER_PERMISSIONS;
    case 'testing_account':
      return TESTING_ACCOUNT_PERMISSIONS;
    case 'teacher':
      return TEACHER_PERMISSIONS;
    default:
      return [];
  }
};

// توليد كلمة مرور آمنة
const generateSecurePassword = () => {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%';
  let password = '';
  for (let i = 0; i < 12; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return password;
};

// =============================================================
// مكون المعالج الرئيسي - Create User Wizard Component
// =============================================================

export default function CreateUserWizard({ open, onOpenChange, onSuccess, api, isRTL }) {
  const { nassaqError } = useNassaqAlert();
  const [step, setStep] = useState(1);
  const totalSteps = 5;
  
  // بيانات النموذج
  const [formData, setFormData] = useState({
    role: '',
    full_name: '',
    email: '',
    phone: '',
    region: '',
    city: '',
    educational_department: '',
    school_name_ar: '',
    school_name_en: '',
  });
  
  // الصلاحيات
  const [selectedPermissions, setSelectedPermissions] = useState([]);
  
  // كلمة المرور المؤقتة
  const [tempPassword, setTempPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedMessage, setCopiedMessage] = useState(false);
  
  // حالة الإرسال
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdUser, setCreatedUser] = useState(null);
  
  // الحصول على المنطقة والمدن والإدارات التعليمية
  const selectedRegion = SAUDI_REGIONS.find(r => r.id === formData.region);
  const availableCities = selectedRegion?.cities || [];
  const availableEducationalDepts = selectedRegion?.educationalDepartments || [];
  
  // عند اختيار دور، تحميل الصلاحيات الافتراضية
  useEffect(() => {
    if (formData.role) {
      const rolePermissions = getPermissionsByRole(formData.role);
      setSelectedPermissions(rolePermissions.map(p => p.id));
    }
  }, [formData.role]);
  
  // إعادة تعيين المدينة والإدارة عند تغيير المنطقة
  useEffect(() => {
    setFormData(prev => ({ ...prev, city: '', educational_department: '' }));
  }, [formData.region]);
  
  // إعادة تعيين النموذج عند الفتح
  useEffect(() => {
    if (open) {
      setStep(1);
      setFormData({
        role: '',
        full_name: '',
        email: '',
        phone: '',
        region: '',
        city: '',
        educational_department: '',
        school_name_ar: '',
        school_name_en: '',
      });
      setSelectedPermissions([]);
      setTempPassword('');
      setCreatedUser(null);
    }
  }, [open]);
  
  // تبديل صلاحية
  const togglePermission = (permId) => {
    setSelectedPermissions(prev => 
      prev.includes(permId) 
        ? prev.filter(p => p !== permId)
        : [...prev, permId]
    );
  };
  
  // الانتقال للخطوة التالية
  const nextStep = () => {
    if (step < totalSteps) {
      // توليد كلمة المرور عند الانتقال إلى الخطوة 4 (من الخطوة 3)
      if (step === 3) {
        setTempPassword(generateSecurePassword());
      }
      setStep(step + 1);
    }
  };
  
  // الانتقال للخطوة السابقة
  const prevStep = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };
  
  // التحقق من صحة الخطوة
  const isStepValid = () => {
    switch (step) {
      case 1:
        return formData.role !== '';
      case 2:
        // التحقق من الاسم الكامل
        if (!formData.full_name || formData.full_name.trim().length < 2) {
          return false;
        }
        // التحقق من البريد الإلكتروني
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!formData.email || !emailRegex.test(formData.email)) {
          return false;
        }
        // للمعلم، يجب اختيار المنطقة والمدينة
        if (formData.role === 'independent_teacher') {
          return formData.region !== '' && formData.city !== '';
        }
        return true;
      case 3:
        return selectedPermissions.length > 0;
      case 4:
        return tempPassword !== '';
      default:
        return true;
    }
  };
  
  // حفظ الحساب - الربط مع Backend API
  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const userData = {
        email: formData.email,
        password: tempPassword,
        full_name: formData.full_name,
        role: formData.role,
        phone: formData.phone || null,
        region: formData.region || null,
        city: formData.city || null,
        educational_department: formData.educational_department || null,
        school_name_ar: formData.school_name_ar || null,
        school_name_en: formData.school_name_en || null,
        permissions: selectedPermissions,
      };
      
      const response = await api.post('/users/create', userData);
      
      if (response.data) {
        setCreatedUser(response.data);
        setStep(5);
        if (onSuccess) {
          onSuccess(response.data);
        }
      }
    } catch (error) {
      console.error('Error creating user:', error);
      const errorMessage = error.response?.data?.detail || error.message || (t('errorCreatingAccount'));
      nassaqError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // نسخ بيانات الدخول
  const copyCredentials = () => {
    const text = `البريد الإلكتروني: ${formData.email}\nكلمة المرور: ${tempPassword}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success(t('credentialsCopied'));
  };
  
  // نسخ رسالة الترحيب
  const copyWelcomeMessage = () => {
    const loginUrl = window.location.origin + '/login';
    const message = `مرحبًا،

تم إنشاء حسابك بنجاح على منصة نَسَّق | NASSAQ.

يسعدنا انضمامك إلى فريق إدارة المنصة، وقد تم منحك الصلاحيات المناسبة لدورك داخل النظام. يمكنك الآن تسجيل الدخول إلى المنصة باستخدام بيانات الدخول التالية:

البريد الإلكتروني: ${formData.email}
كلمة المرور المؤقتة: ${tempPassword}

يرجى تسجيل الدخول عبر الرابط التالي:
${loginUrl}

عند تسجيل الدخول لأول مرة سيطلب منك النظام تغيير كلمة المرور لضمان أمان حسابك.

إذا واجهت أي مشكلة أثناء تسجيل الدخول أو احتجت إلى مساعدة، يرجى التواصل مع إدارة المنصة.

نتمنى لك تجربة موفقة داخل منصة نَسَّق، ونسعد بمساهمتك في تطوير وتشغيل النظام.

مع خالص التحية،
إدارة منصة نَسَّق | NASSAQ`;
    
    navigator.clipboard.writeText(message);
    setCopiedMessage(true);
    setTimeout(() => setCopiedMessage(false), 2000);
    toast.success(t('welcomeMessageCopied'));
  };
  
  const selectedRole = AVAILABLE_ROLES.find(r => r.id === formData.role);
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col p-0" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b bg-gradient-to-r from-brand-navy/5 to-brand-turquoise/5 flex-shrink-0">
          <DialogTitle className="font-cairo text-xl flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-navy flex items-center justify-center">
              <UserPlus className="h-5 w-5 text-white" />
            </div>
            {t('createNewUserAccount')}
          </DialogTitle>
          <DialogDescription>
            {t('followTheStepsToCreateANewAccount')}
          </DialogDescription>
          
          {/* Progress Steps */}
          <div className="flex items-center gap-2 mt-4">
            {[1, 2, 3, 4, 5].map((s) => (
              <div key={s} className="flex items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                  s === step 
                    ? 'bg-brand-navy text-white' 
                    : s < step 
                      ? 'bg-green-500 text-white'
                      : 'bg-muted text-muted-foreground'
                }`}>
                  {s < step ? <Check className="h-4 w-4" /> : s}
                </div>
                {s < 5 && <div className={`w-8 h-1 ${s < step ? 'bg-green-500' : 'bg-muted'}`} />}
              </div>
            ))}
          </div>
          
          {/* Step Labels */}
          <div className="flex justify-between mt-2 text-xs text-muted-foreground px-1">
            <span className={step === 1 ? 'text-brand-navy font-medium' : ''}>{t('role')}</span>
            <span className={step === 2 ? 'text-brand-navy font-medium' : ''}>{isRTL ? 'البيانات' : 'Data'}</span>
            <span className={step === 3 ? 'text-brand-navy font-medium' : ''}>{t('permissions')}</span>
            <span className={step === 4 ? 'text-brand-navy font-medium' : ''}>{t('password')}</span>
            <span className={step === 5 ? 'text-brand-navy font-medium' : ''}>{t('confirm')}</span>
          </div>
        </DialogHeader>
        
        {/* Content - Scrollable */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="p-6">
            
            {/* ====================================== */}
            {/* الخطوة 1: اختيار نوع الحساب */}
            {/* ====================================== */}
            {step === 1 && (
              <div className="space-y-4">
                <h3 className="font-cairo font-bold text-lg mb-4 flex items-center gap-2">
                  <Shield className="h-5 w-5 text-brand-navy" />
                  {t('selectAccountType')}
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {AVAILABLE_ROLES.map((role) => (
                    <Card
                      key={role.id}
                      className={`cursor-pointer transition-all hover:shadow-md ${
                        formData.role === role.id 
                          ? 'ring-2 ring-brand-turquoise border-brand-turquoise' 
                          : 'border-border hover:border-brand-turquoise/50'
                      }`}
                      onClick={() => setFormData({ ...formData, role: role.id })}
                      data-testid={`role-card-${role.id}`}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <div className={`w-12 h-12 rounded-xl ${role.color} flex items-center justify-center flex-shrink-0`}>
                            <role.icon className="h-6 w-6 text-white" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="font-cairo font-bold text-sm">
                              {isRTL ? role.name : role.name_en}
                            </h4>
                            <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                              {isRTL ? role.description : role.description_en}
                            </p>
                          </div>
                          {formData.role === role.id && (
                            <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}
            
            {/* ====================================== */}
            {/* الخطوة 2: البيانات الأساسية */}
            {/* ====================================== */}
            {step === 2 && (
              <div className="space-y-6">
                <h3 className="font-cairo font-bold text-lg mb-4 flex items-center gap-2">
                  <User className="h-5 w-5 text-brand-navy" />
                  {t('userBasicInformation')}
                </h3>
                
                {/* الدور المختار */}
                {selectedRole && (
                  <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl border">
                    <div className={`w-10 h-10 rounded-xl ${selectedRole.color} flex items-center justify-center`}>
                      <selectedRole.icon className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{isRTL ? selectedRole.name : selectedRole.name_en}</p>
                      <p className="text-xs text-muted-foreground">{t('selectedRole')}</p>
                    </div>
                  </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* الاسم الكامل */}
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <User className="h-4 w-4" />
                      {t('fullName2')}
                    </Label>
                    <Input
                      value={formData.full_name}
                      onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                      placeholder={t('enterFullName2')}
                      className="rounded-xl"
                      data-testid="user-fullname-input"
                    />
                  </div>
                  
                  {/* البريد الإلكتروني */}
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Mail className="h-4 w-4" />
                      {t('email4')}
                    </Label>
                    <Input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      placeholder="example@domain.com"
                      className="rounded-xl"
                      dir="ltr"
                      data-testid="user-email-input"
                    />
                  </div>
                  
                  {/* رقم الهاتف */}
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Phone className="h-4 w-4" />
                      {isRTL ? 'رقم الهاتف' : 'Phone Number'}
                    </Label>
                    <Input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="05xxxxxxxx"
                      className="rounded-xl"
                      dir="ltr"
                      data-testid="user-phone-input"
                    />
                  </div>
                  
                  {/* المنطقة */}
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <MapPin className="h-4 w-4" />
                      {t('region')}
                    </Label>
                    <Select value={formData.region} onValueChange={(v) => setFormData({ ...formData, region: v })}>
                      <SelectTrigger className="rounded-xl">
                        <SelectValue placeholder={t('selectRegion')} />
                      </SelectTrigger>
                      <SelectContent>
                        {SAUDI_REGIONS.map((region) => (
                          <SelectItem key={region.id} value={region.id}>
                            {isRTL ? region.name : region.name_en}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {/* المدينة */}
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Building2 className="h-4 w-4" />
                      {t('city3')}
                    </Label>
                    <Select 
                      value={formData.city} 
                      onValueChange={(v) => setFormData({ ...formData, city: v })}
                      disabled={!formData.region}
                    >
                      <SelectTrigger className="rounded-xl">
                        <SelectValue placeholder={isRTL ? 'اختر المدينة' : 'Select city'} />
                      </SelectTrigger>
                      <SelectContent>
                        {availableCities.map((city) => (
                          <SelectItem key={city.id} value={city.id}>
                            {isRTL ? city.name : city.name_en}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {/* الإدارة التعليمية - للمعلم فقط */}
                  {formData.role === 'independent_teacher' && (
                    <div className="space-y-2">
                      <Label className="flex items-center gap-2">
                        <GraduationCap className="h-4 w-4" />
                        {t('educationalDepartment')}
                      </Label>
                      <Select 
                        value={formData.educational_department} 
                        onValueChange={(v) => setFormData({ ...formData, educational_department: v })}
                        disabled={!formData.region}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('selectDepartment')} />
                        </SelectTrigger>
                        <SelectContent>
                          {availableEducationalDepts.map((dept) => (
                            <SelectItem key={dept.id} value={dept.id}>
                              {isRTL ? dept.name : dept.name_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
                
                {/* حقول المدرسة - للمعلم فقط */}
                {formData.role === 'independent_teacher' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
                    <div className="space-y-2">
                      <Label className="flex items-center gap-2">
                        <School className="h-4 w-4" />
                        {t('schoolNameArabic')}
                      </Label>
                      <Input
                        value={formData.school_name_ar}
                        onChange={(e) => setFormData({ ...formData, school_name_ar: e.target.value })}
                        placeholder={t('enterSchoolNameInArabic')}
                        className="rounded-xl"
                        data-testid="school-name-ar-input"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label className="flex items-center gap-2">
                        <School className="h-4 w-4" />
                        {t('schoolNameEnglish')}
                      </Label>
                      <Input
                        value={formData.school_name_en}
                        onChange={(e) => setFormData({ ...formData, school_name_en: e.target.value })}
                        placeholder="Enter school name in English"
                        className="rounded-xl"
                        dir="ltr"
                        data-testid="school-name-en-input"
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {/* ====================================== */}
            {/* الخطوة 3: تحديد الصلاحيات */}
            {/* ====================================== */}
            {step === 3 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-cairo font-bold text-lg flex items-center gap-2">
                    <Shield className="h-5 w-5 text-brand-navy" />
                    {t('configurePermissions')}
                  </h3>
                  <Badge variant="outline" className="text-sm">
                    {selectedPermissions.length} {t('permissionsSelected')}
                  </Badge>
                </div>
                
                {/* شرح */}
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-2 text-sm">
                  <AlertTriangle className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-blue-800">
                      {t('defaultPermissions')}
                    </p>
                    <p className="text-blue-600">
                      {t('defaultPermissionsForTheSelectedRoleHaveBeenLoaded')}
                    </p>
                  </div>
                </div>
                
                {/* قائمة الصلاحيات حسب الدور المختار */}
                {formData.role && (
                  <Card className="border-border">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg ${selectedRole?.color || 'bg-gray-100'} flex items-center justify-center`}>
                            {selectedRole?.icon && <selectedRole.icon className="h-4 w-4 text-white" />}
                          </div>
                          <div>
                            <p className="font-medium text-sm">
                              {isRTL 
                                ? `صلاحيات ${selectedRole?.name || 'الدور'}` 
                                : `${selectedRole?.name_en || 'Role'} Permissions`}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {selectedPermissions.length} / {getPermissionsByRole(formData.role).length} {t('selected')}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => {
                            const rolePerms = getPermissionsByRole(formData.role);
                            const allIds = rolePerms.map(p => p.id);
                            const allSelected = allIds.every(id => selectedPermissions.includes(id));
                            if (allSelected) {
                              setSelectedPermissions([]);
                            } else {
                              setSelectedPermissions(allIds);
                            }
                          }}
                        >
                          {selectedPermissions.length === getPermissionsByRole(formData.role).length 
                            ? (isRTL ? 'إلغاء الكل' : 'Deselect All')
                            : (t('selectAll'))
                          }
                        </Button>
                      </div>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {getPermissionsByRole(formData.role).map((perm) => {
                          const isSelected = selectedPermissions.includes(perm.id);
                          const IconComp = perm.icon;
                          return (
                            <div
                              key={perm.id}
                              onClick={() => togglePermission(perm.id)}
                              className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all border ${
                                isSelected 
                                  ? 'bg-green-50 border-green-300' 
                                  : 'bg-muted/30 border-transparent hover:border-muted-foreground/30'
                              }`}
                              data-testid={`permission-${perm.id}`}
                            >
                              <div className={`w-5 h-5 rounded flex items-center justify-center ${
                                isSelected ? 'bg-green-500' : 'bg-muted'
                              }`}>
                                {isSelected && <Check className="h-3 w-3 text-white" />}
                              </div>
                              <IconComp className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                              <span className="text-xs flex-1">
                                {isRTL ? perm.name : perm.name_en}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                )}
                
                {/* رسالة إذا لم يتم اختيار دور */}
                {!formData.role && (
                  <div className="p-6 bg-muted/30 rounded-xl text-center">
                    <Shield className="h-12 w-12 mx-auto text-muted-foreground/50 mb-3" />
                    <p className="text-muted-foreground">
                      {t('pleaseSelectARoleFirstToViewPermissions')}
                    </p>
                  </div>
                )}
              </div>
            )}
            
            {/* ====================================== */}
            {/* الخطوة 4: كلمة المرور المؤقتة */}
            {/* ====================================== */}
            {step === 4 && (
              <div className="space-y-6">
                <h3 className="font-cairo font-bold text-lg mb-4 flex items-center gap-2">
                  <Lock className="h-5 w-5 text-brand-navy" />
                  {t('temporaryPassword')}
                </h3>
                
                {/* ملخص المستخدم */}
                <Card className="bg-muted/30">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4">
                      {selectedRole && (
                        <div className={`w-12 h-12 rounded-xl ${selectedRole.color} flex items-center justify-center`}>
                          <selectedRole.icon className="h-6 w-6 text-white" />
                        </div>
                      )}
                      <div>
                        <p className="font-bold">{formData.full_name}</p>
                        <p className="text-sm text-muted-foreground">{formData.email}</p>
                        <p className="text-xs text-muted-foreground">
                          {selectedRole && (isRTL ? selectedRole.name : selectedRole.name_en)}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* كلمة المرور */}
                <div className="space-y-3">
                  <Label>{t('temporaryPassword')}</Label>
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        value={tempPassword}
                        readOnly
                        className="rounded-xl pe-10 font-mono text-lg"
                        dir="ltr"
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() => setTempPassword(generateSecurePassword())}
                      className="rounded-xl"
                    >
                      <Settings className="h-4 w-4 me-2" />
                      {t('regenerate')}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t('userWillBeRequiredToChangePasswordOnFirstLogin')}
                  </p>
                </div>
                
                {/* عدد الصلاحيات */}
                <div className="p-4 bg-green-50 border border-green-200 rounded-xl">
                  <div className="flex items-center gap-3">
                    <Shield className="h-6 w-6 text-green-600" />
                    <div>
                      <p className="font-medium text-green-800">
                        {selectedPermissions.length} {t('permissions2')}
                      </p>
                      <p className="text-sm text-green-600">
                        {t('willBeGrantedToTheUser')}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* ====================================== */}
            {/* الخطوة 5: التأكيد والنجاح */}
            {/* ====================================== */}
            {step === 5 && createdUser && (
              <div className="space-y-6 text-center">
                {/* أيقونة النجاح */}
                <div className="w-20 h-20 mx-auto rounded-full bg-green-100 flex items-center justify-center">
                  <CheckCircle2 className="h-10 w-10 text-green-600" />
                </div>
                
                <div>
                  <h3 className="font-cairo font-bold text-xl text-green-700">
                    {isRTL ? 'تم إنشاء الحساب بنجاح!' : 'Account Created Successfully!'}
                  </h3>
                  <p className="text-muted-foreground mt-2">
                    {t('youCanNowSendLoginCredentialsToTheUser')}
                  </p>
                </div>
                
                {/* بيانات الدخول */}
                <Card className="text-start">
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center gap-2 mb-3">
                      <Key className="h-5 w-5" />
                      <span className="font-cairo font-medium">{t('loginCredentials3')}</span>
                    </div>
                    
                    <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                      <div>
                        <p className="text-xs text-muted-foreground">{t('email2')}</p>
                        <p className="font-mono text-sm">{formData.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                      <div>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'كلمة المرور المؤقتة' : 'Temp Password'}</p>
                        <p className="font-mono text-sm">{showPassword ? tempPassword : '••••••••••••'}</p>
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => setShowPassword(!showPassword)}>
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                    
                    <div className="flex gap-2 pt-2">
                      <Button onClick={copyCredentials} variant="outline" className="flex-1 rounded-xl">
                        {copied ? <Check className="h-4 w-4 me-2" /> : <Copy className="h-4 w-4 me-2" />}
                        {t('copyCredentials')}
                      </Button>
                      <Button onClick={copyWelcomeMessage} className="flex-1 bg-brand-navy rounded-xl">
                        {copiedMessage ? <Check className="h-4 w-4 me-2" /> : <Send className="h-4 w-4 me-2" />}
                        {t('copyWelcomeMessage')}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
            
          </div>
        </ScrollArea>
        
        {/* Footer - Fixed */}
        <DialogFooter className="px-6 py-4 border-t bg-background flex-shrink-0">
          <div className="flex justify-between w-full gap-3">
            {step > 1 && step < 5 ? (
              <Button variant="outline" onClick={prevStep} className="rounded-xl min-w-[100px]">
                <ChevronRight className="h-4 w-4 me-2 rtl:rotate-180" />
                {isRTL ? 'السابق' : 'Previous'}
              </Button>
            ) : (
              <div />
            )}
            
            {step < 4 && (
              <Button 
                onClick={nextStep} 
                disabled={!isStepValid()}
                className="bg-brand-navy rounded-xl min-w-[100px]"
              >
                {t('next')}
                <ChevronLeft className="h-4 w-4 ms-2 rtl:rotate-180" />
              </Button>
            )}
            
            {step === 4 && (
              <Button 
                onClick={handleSubmit} 
                disabled={isSubmitting}
                className="bg-green-600 hover:bg-green-700 rounded-xl min-w-[120px]"
              >
                {isSubmitting ? (
                  <>
                    <Settings className="h-4 w-4 me-2 animate-spin" />
                    {t('creating')}
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 me-2" />
                    {t('createAccount')}
                  </>
                )}
              </Button>
            )}
            
            {step === 5 && (
              <Button 
                onClick={() => onOpenChange(false)}
                className="bg-brand-navy rounded-xl min-w-[100px]"
              >
                {t('close')}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
