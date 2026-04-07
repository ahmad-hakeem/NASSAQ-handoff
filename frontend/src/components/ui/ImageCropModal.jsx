import { useState, useCallback, useRef } from 'react';
import Cropper from 'react-easy-crop';
import imageCompression from 'browser-image-compression';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './dialog';
import { Button } from './button';
import { Slider } from './slider';
import { Loader2, ZoomIn, ZoomOut, Upload, X, Check, ImagePlus } from 'lucide-react';

import { useTranslation } from '../../contexts/ThemeContext';
async function getCroppedImg(imageSrc, pixelCrop) {
  const image = new Image();
  image.crossOrigin = 'anonymous';
  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = reject;
    image.src = imageSrc;
  });

  const canvas = document.createElement('canvas');
  canvas.width = pixelCrop.width;
  canvas.height = pixelCrop.height;
  const ctx = canvas.getContext('2d');

  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    pixelCrop.width,
    pixelCrop.height
  );

  return new Promise((resolve) => {
    canvas.toBlob(
      (blob) => resolve(blob),
      'image/jpeg',
      0.9
    );
  });
}

const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const MAX_FILE_SIZE = 5 * 1024 * 1024;

export function ImageCropModal({ open, onOpenChange, onSave, isRTL = true }) {
  const [imageSrc, setImageSrc] = useState(null);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const onCropComplete = useCallback((_croppedArea, croppedPixels) => {
    setCroppedAreaPixels(croppedPixels);
  }, []);

  const resetState = useCallback(() => {
    setImageSrc(null);
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setCroppedAreaPixels(null);
    setSaving(false);
    setError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(t('unsupportedFormatAllowedJpegPngWebp'));
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(t('imageTooLargeMax5mb'));
      return;
    }

    setError('');
    const reader = new FileReader();
    reader.onload = () => {
      setImageSrc(reader.result);
      setCrop({ x: 0, y: 0 });
      setZoom(1);
    };
    reader.onerror = () => {
      setError(t('failedToReadImage'));
    };
    reader.readAsDataURL(file);
  }, [isRTL]);

  const handleSave = useCallback(async () => {
    if (!imageSrc || !croppedAreaPixels) return;
    setSaving(true);
    setError('');

    try {
      const croppedBlob = await getCroppedImg(imageSrc, croppedAreaPixels);

      const compressedBlob = await imageCompression(
        new File([croppedBlob], 'avatar.jpg', { type: 'image/jpeg' }),
        {
          maxSizeMB: 0.5,
          maxWidthOrHeight: 512,
          useWebWorker: true,
          fileType: 'image/jpeg',
        }
      );

      const base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(compressedBlob);
      });

      await onSave(base64);
      resetState();
      onOpenChange(false);
    } catch (err) {
      setError(t('failedToProcessImagePleaseTryAgain'));
    } finally {
      setSaving(false);
    }
  }, [imageSrc, croppedAreaPixels, onSave, onOpenChange, resetState, isRTL]);

  const handleCancel = useCallback(() => {
    resetState();
    onOpenChange(false);
  }, [resetState, onOpenChange]);

  const handleChangeImage = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleOpenChange = useCallback((val) => {
    if (!val) {
      resetState();
    }
    onOpenChange(val);
  }, [resetState, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-cairo">
            <ImagePlus className="h-5 w-5 text-brand-navy" />
            {t('editProfileImage')}
          </DialogTitle>
          <DialogDescription className="font-tajawal">
            {t('selectAnImageAndCropItToFit')}
          </DialogDescription>
        </DialogHeader>

        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/jpg,image/png,image/webp"
          className="hidden"
          onChange={handleFileSelect}
        />

        {error && (
          <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg text-center font-tajawal">
            {error}
          </div>
        )}

        {!imageSrc ? (
          <div
            className="border-2 border-dashed border-muted-foreground/30 rounded-xl p-12 text-center cursor-pointer hover:border-brand-navy/50 transition-colors"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
            <p className="text-sm text-muted-foreground font-tajawal">
              {t('clickToSelectAnImage')}
            </p>
            <p className="text-xs text-muted-foreground/70 mt-2 font-tajawal">
              {t('jpegPngWebpMax5mb')}
            </p>
          </div>
        ) : (
          <>
            <div className="relative w-full h-[300px] bg-black/5 rounded-xl overflow-hidden">
              <Cropper
                image={imageSrc}
                crop={crop}
                zoom={zoom}
                aspect={1}
                cropShape="round"
                showGrid={false}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={onCropComplete}
              />
            </div>

            <div className="flex items-center gap-3 px-2">
              <ZoomOut className="h-4 w-4 text-muted-foreground shrink-0" />
              <Slider
                value={[zoom]}
                min={1}
                max={3}
                step={0.05}
                onValueChange={([val]) => setZoom(val)}
                className="flex-1"
              />
              <ZoomIn className="h-4 w-4 text-muted-foreground shrink-0" />
            </div>

            <div className="flex items-center gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={handleChangeImage}
                disabled={saving}
                className="font-tajawal"
              >
                <ImagePlus className="h-4 w-4" />
                {t('changeImage')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancel}
                disabled={saving}
                className="font-tajawal"
              >
                <X className="h-4 w-4" />
                {t('cancel')}
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={saving}
                className="bg-brand-navy hover:bg-brand-navy/90 font-tajawal"
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                {t('save')}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
