import { useState, useCallback } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { toast } from 'sonner';
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Download,
  Eye,
  ArrowLeft,
  ArrowRight,
  Users,
  FileText,
  Sparkles,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Required fields for teacher import
const REQUIRED_FIELDS = [
  { key: 'full_name', label_ar: 'اسم المعلم الكامل', label_en: 'Full Name', required: true },
  { key: 'gender', label_ar: 'الجنس', label_en: 'Gender', required: true },
  { key: 'national_id', label_ar: 'رقم الهوية', label_en: 'National ID', required: true },
  { key: 'phone', label_ar: 'رقم الهاتف', label_en: 'Phone', required: true },
  { key: 'email', label_ar: 'البريد الإلكتروني', label_en: 'Email', required: true },
  { key: 'subject', label_ar: 'المادة الدراسية', label_en: 'Subject', required: true },
  { key: 'education_level', label_ar: 'المرحلة التعليمية', label_en: 'Education Level', required: true },
  { key: 'grades', label_ar: 'الصفوف التي يدرسها', label_en: 'Teaching Grades', required: true },
  { key: 'rank', label_ar: 'الرتبة المهنية', label_en: 'Teacher Rank', required: true },
  { key: 'address', label_ar: 'العنوان', label_en: 'Address', required: false },
];

// Step 1: Upload File
const UploadStep = ({ onFileSelect, isRTL }) => {
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      onFileSelect(acceptedFiles[0]);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
    },
    maxFiles: 1,
  });

  const downloadTemplate = () => {
    // Create CSV template
    const headers = REQUIRED_FIELDS.map(f => isRTL ? f.label_ar : f.label_en).join(',');
    const example = 'أحمد محمد العمري,ذكر,1029384756,0500000000,teacher@school.com,الرياضيات,ابتدائي,الرابع;الخامس,معلم متقدم,الرياض';
    const csvContent = `${headers}\n${example}`;
    
    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'teachers_template.csv';
    link.click();
    toast.success(isRTL ? 'تم تحميل القالب' : 'Template downloaded');
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Upload className="h-8 w-8 text-blue-600" />
        </div>
        <h3 className="text-xl font-bold font-cairo">{isRTL ? 'رفع ملف المعلمين' : 'Upload Teachers File'}</h3>
        <p className="text-muted-foreground mt-2">
          {isRTL ? 'قم برفع ملف Excel أو CSV يحتوي على بيانات المعلمين' : 'Upload an Excel or CSV file with teacher data'}
        </p>
      </div>

      {/* Required Fields Info */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {isRTL ? 'البيانات المطلوبة' : 'Required Fields'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {REQUIRED_FIELDS.map(field => (
              <Badge 
                key={field.key} 
                variant={field.required ? 'default' : 'secondary'}
                className={field.required ? 'bg-red-100 text-red-700 border-red-200' : ''}
              >
                {isRTL ? field.label_ar : field.label_en}
                {field.required && ' *'}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
          isDragActive 
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' 
            : 'border-border hover:border-blue-300 hover:bg-muted/30'
        }`}
      >
        <input {...getInputProps()} />
        <FileSpreadsheet className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
        <p className="text-lg font-medium">
          {isDragActive 
            ? (isRTL ? 'أفلت الملف هنا...' : 'Drop the file here...')
            : (isRTL ? 'اسحب وأفلت الملف هنا أو انقر للاختيار' : 'Drag & drop file here or click to select')
          }
        </p>
        <p className="text-sm text-muted-foreground mt-2">
          {isRTL ? 'الصيغ المدعومة: Excel (.xlsx, .xls) أو CSV' : 'Supported: Excel (.xlsx, .xls) or CSV'}
        </p>
      </div>

      {/* Download Template Button */}
      <div className="flex justify-center">
        <Button variant="outline" onClick={downloadTemplate} className="rounded-xl">
          <Download className="h-4 w-4 me-2" />
          {isRTL ? 'تحميل قالب البيانات' : 'Download Template'}
        </Button>
      </div>
    </div>
  );
};

// Step 2: Preview & Analyze
const PreviewStep = ({ data, errors, onFix, isRTL }) => {
  const validRows = data.filter((_, idx) => !errors.some(e => e.row === idx));
  const invalidRows = data.filter((_, idx) => errors.some(e => e.row === idx));

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Sparkles className="h-8 w-8 text-purple-600" />
        </div>
        <h3 className="text-xl font-bold font-cairo">{isRTL ? 'تحليل البيانات' : 'Data Analysis'}</h3>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <Users className="h-8 w-8 mx-auto mb-2 text-blue-600" />
            <p className="text-2xl font-bold">{data.length}</p>
            <p className="text-sm text-muted-foreground">{isRTL ? 'إجمالي السجلات' : 'Total Records'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-600" />
            <p className="text-2xl font-bold text-green-600">{validRows.length}</p>
            <p className="text-sm text-muted-foreground">{isRTL ? 'صالحة' : 'Valid'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <XCircle className="h-8 w-8 mx-auto mb-2 text-red-600" />
            <p className="text-2xl font-bold text-red-600">{invalidRows.length}</p>
            <p className="text-sm text-muted-foreground">{isRTL ? 'بها أخطاء' : 'With Errors'}</p>
          </CardContent>
        </Card>
      </div>

      {/* Errors List */}
      {errors.length > 0 && (
        <Card className="border-red-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-4 w-4" />
              {isRTL ? 'الأخطاء المكتشفة' : 'Detected Errors'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-48 overflow-y-auto space-y-2">
              {errors.slice(0, 10).map((error, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm p-2 bg-red-50 rounded-lg">
                  <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
                  <span className="font-medium">{isRTL ? `الصف ${error.row + 1}:` : `Row ${error.row + 1}:`}</span>
                  <span className="text-muted-foreground">{error.message}</span>
                </div>
              ))}
              {errors.length > 10 && (
                <p className="text-sm text-muted-foreground text-center">
                  {isRTL ? `و ${errors.length - 10} أخطاء أخرى...` : `And ${errors.length - 10} more errors...`}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Data Preview Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Eye className="h-4 w-4" />
            {isRTL ? 'معاينة البيانات' : 'Data Preview'}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto max-h-64">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>{isRTL ? 'الاسم' : 'Name'}</TableHead>
                  <TableHead>{isRTL ? 'الهوية' : 'ID'}</TableHead>
                  <TableHead>{isRTL ? 'البريد' : 'Email'}</TableHead>
                  <TableHead>{isRTL ? 'المادة' : 'Subject'}</TableHead>
                  <TableHead>{isRTL ? 'الحالة' : 'Status'}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.slice(0, 10).map((row, idx) => {
                  const hasError = errors.some(e => e.row === idx);
                  return (
                    <TableRow key={idx} className={hasError ? 'bg-red-50' : ''}>
                      <TableCell className="font-medium">{idx + 1}</TableCell>
                      <TableCell>{row.full_name}</TableCell>
                      <TableCell dir="ltr">{row.national_id}</TableCell>
                      <TableCell dir="ltr">{row.email}</TableCell>
                      <TableCell>{row.subject}</TableCell>
                      <TableCell>
                        {hasError ? (
                          <Badge variant="destructive" className="text-xs">
                            <XCircle className="h-3 w-3 me-1" />
                            {isRTL ? 'خطأ' : 'Error'}
                          </Badge>
                        ) : (
                          <Badge variant="default" className="bg-green-100 text-green-700 text-xs">
                            <CheckCircle2 className="h-3 w-3 me-1" />
                            {isRTL ? 'صالح' : 'Valid'}
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// Step 3: Import Progress
const ImportStep = ({ progress, total, created, failed, isRTL }) => (
  <div className="space-y-6">
    <div className="text-center">
      <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <Loader2 className="h-8 w-8 text-amber-600 animate-spin" />
      </div>
      <h3 className="text-xl font-bold font-cairo">{isRTL ? 'جاري الاستيراد...' : 'Importing...'}</h3>
      <p className="text-muted-foreground mt-2">
        {isRTL ? 'يرجى الانتظار حتى اكتمال العملية' : 'Please wait while we process your data'}
      </p>
    </div>

    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span>{progress} / {total}</span>
        <span>{Math.round((progress / total) * 100)}%</span>
      </div>
      <Progress value={(progress / total) * 100} className="h-3" />
    </div>

    <div className="grid grid-cols-2 gap-4 text-center">
      <Card>
        <CardContent className="p-4">
          <p className="text-2xl font-bold text-green-600">{created}</p>
          <p className="text-sm text-muted-foreground">{isRTL ? 'تم إنشاؤهم' : 'Created'}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4">
          <p className="text-2xl font-bold text-red-600">{failed}</p>
          <p className="text-sm text-muted-foreground">{isRTL ? 'فشل' : 'Failed'}</p>
        </CardContent>
      </Card>
    </div>
  </div>
);

// Step 4: Results
const ResultsStep = ({ results, isRTL, onClose }) => (
  <div className="space-y-6 text-center">
    <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto">
      <CheckCircle2 className="h-10 w-10 text-green-600" />
    </div>
    
    <div>
      <h3 className="text-2xl font-bold font-cairo text-green-700">
        {isRTL ? 'تم الاستيراد بنجاح!' : 'Import Complete!'}
      </h3>
      <p className="text-muted-foreground mt-2">
        {isRTL 
          ? `تم إنشاء ${results.created} حساب معلم بنجاح`
          : `Successfully created ${results.created} teacher accounts`
        }
      </p>
    </div>

    <div className="grid grid-cols-3 gap-4">
      <Card>
        <CardContent className="p-4 text-center">
          <p className="text-2xl font-bold">{results.total}</p>
          <p className="text-xs text-muted-foreground">{isRTL ? 'الإجمالي' : 'Total'}</p>
        </CardContent>
      </Card>
      <Card className="border-green-200">
        <CardContent className="p-4 text-center">
          <p className="text-2xl font-bold text-green-600">{results.created}</p>
          <p className="text-xs text-muted-foreground">{isRTL ? 'تم إنشاؤهم' : 'Created'}</p>
        </CardContent>
      </Card>
      <Card className="border-red-200">
        <CardContent className="p-4 text-center">
          <p className="text-2xl font-bold text-red-600">{results.failed}</p>
          <p className="text-xs text-muted-foreground">{isRTL ? 'فشل' : 'Failed'}</p>
        </CardContent>
      </Card>
    </div>

    <Button onClick={onClose} className="bg-green-600 hover:bg-green-700">
      {isRTL ? 'إغلاق' : 'Close'}
    </Button>
  </div>
);

// Main Bulk Import Wizard
export const BulkTeacherImport = ({ open, onClose }) => {
  const { isRTL } = useTheme();
  const { token, api } = useAuth();
  
  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [parsedData, setParsedData] = useState([]);
  const [errors, setErrors] = useState([]);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState({ total: 0, created: 0, failed: 0 });

  const handleFileSelect = async (selectedFile) => {
    setFile(selectedFile);
    
    // Parse file (simplified - in real app, use xlsx library)
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    try {
      const response = await api.post('/teachers/bulk/parse', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setParsedData(response.data.data || []);
      setErrors(response.data.errors || []);
      setStep(2);
    } catch (error) {
      // Show error - no mock data
      console.error('Error parsing file:', error);
      setParsedData([]);
      setErrors([{ row: 0, field: 'file', message: isRTL ? 'فشل في قراءة الملف. يرجى التحقق من صيغة الملف.' : 'Failed to parse file. Please check file format.' }]);
      setStep(2);
    }
  };

  const handleImport = async () => {
    setImporting(true);
    setStep(3);
    
    const validData = parsedData.filter((_, idx) => !errors.some(e => e.row === idx));
    let created = 0;
    let failed = 0;

    for (let i = 0; i < validData.length; i++) {
      try {
        await api.post('/teachers/bulk/create-single', validData[i]);
        created++;
      } catch {
        failed++;
      }
      setProgress(i + 1);
      setResults({ total: validData.length, created, failed });
    }

    setImporting(false);
    setStep(4);
  };

  const handleReset = () => {
    setStep(1);
    setFile(null);
    setParsedData([]);
    setErrors([]);
    setProgress(0);
    setResults({ total: 0, created: 0, failed: 0 });
  };

  const handleClose = () => {
    handleReset();
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="bulk-teacher-import">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 font-cairo text-xl">
            <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
              <Upload className="h-5 w-5 text-blue-600" />
            </div>
            {isRTL ? 'استيراد جماعي للمعلمين' : 'Bulk Teacher Import'}
          </DialogTitle>
          <DialogDescription>
            {isRTL 
              ? 'قم برفع ملف Excel أو CSV لإنشاء حسابات المعلمين دفعة واحدة'
              : 'Upload an Excel or CSV file to create multiple teacher accounts at once'
            }
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {step === 1 && <UploadStep onFileSelect={handleFileSelect} isRTL={isRTL} />}
          {step === 2 && <PreviewStep data={parsedData} errors={errors} isRTL={isRTL} />}
          {step === 3 && <ImportStep progress={progress} total={parsedData.length} created={results.created} failed={results.failed} isRTL={isRTL} />}
          {step === 4 && <ResultsStep results={results} isRTL={isRTL} onClose={handleClose} />}
        </div>

        {!importing && step < 4 && (
          <DialogFooter className="flex justify-between gap-3">
            <div>
              {step > 1 && (
                <Button variant="outline" onClick={() => setStep(s => s - 1)} className="rounded-xl">
                  {isRTL ? <ArrowRight className="h-4 w-4 me-2" /> : <ArrowLeft className="h-4 w-4 me-2" />}
                  {isRTL ? 'السابق' : 'Back'}
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={handleClose}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              {step === 2 && (
                <Button onClick={handleImport} className="bg-blue-600 hover:bg-blue-700 rounded-xl">
                  <Upload className="h-4 w-4 me-2" />
                  {isRTL ? 'بدء الاستيراد' : 'Start Import'}
                </Button>
              )}
            </div>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default BulkTeacherImport;
