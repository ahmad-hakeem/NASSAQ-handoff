import { useState, useCallback, useRef } from 'react';
import Cropper from 'react-easy-crop';
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
  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = () => reject(new Error('Image failed to load'));
    image.src = imageSrc;
  });

  // Always downscale to the final display size. Mirrors AVATAR_MAX_PX in
  // backend/utils/avatar_image.py so client and server agree on dimensions.
  const MAX_DIM = 256;
  const sw = pixelCrop.width;
  const sh = pixelCrop.height;
  const scale = Math.min(1, MAX_DIM / Math.max(sw, sh));
  const dw = Math.max(1, Math.round(sw * scale));
  const dh = Math.max(1, Math.round(sh * scale));

  const canvas = document.createElement('canvas');
  canvas.width = dw;
  canvas.height = dh;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(image, pixelCrop.x, pixelCrop.y, sw, sh, 0, 0, dw, dh);

  // Preserve transparency for logos that genuinely need it: encode as PNG
  // only when the cropped pixels actually contain non-opaque alpha
  // (the server re-encodes alpha images to WEBP). Everything else becomes
  // a small JPEG.
  let hasAlpha = false;
  try {
    const { data } = ctx.getImageData(0, 0, dw, dh);
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] < 255) {
        hasAlpha = true;
        break;
      }
    }
  } catch (e) {
    // getImageData can throw on tainted canvases; fall back to JPEG.
  }
  const mimeType = hasAlpha ? 'image/png' : 'image/jpeg';

  const blob = await new Promise((resolve) => {
    canvas.toBlob((b) => resolve(b), mimeType, 0.85);
  });
  if (blob) return blob;

  // Fallback: synthesize a Blob from a data URL when canvas.toBlob is unavailable
  const dataUrl = canvas.toDataURL(mimeType, 0.85);
  const byteString = atob(dataUrl.split(',')[1]);
  const mime = dataUrl.split(',')[0].split(':')[1].split(';')[0];
  const buf = new ArrayBuffer(byteString.length);
  const arr = new Uint8Array(buf);
  for (let i = 0; i < byteString.length; i++) arr[i] = byteString.charCodeAt(i);
  return new Blob([buf], { type: mime });
}

const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const MAX_FILE_SIZE = 5 * 1024 * 1024;

export function ImageCropModal({ open, onOpenChange, onSave, isRTL = true }) {
  const { t } = useTranslation();
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
      // getCroppedImg already bounds the export to 256px, so the payload is
      // a few kB — no secondary compression pass needed.
      const finalBlob = await getCroppedImg(imageSrc, croppedAreaPixels);

      const base64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Failed to read compressed image'));
        reader.readAsDataURL(finalBlob);
      });

      await onSave(base64);
      resetState();
      onOpenChange(false);
    } catch (err) {
      console.error('Image crop/upload error:', err);
      setError(err?.message || t('failedToProcessImagePleaseTryAgain'));
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
