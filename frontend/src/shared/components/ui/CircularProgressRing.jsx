import { useEffect, useState } from 'react';

export const CircularProgressRing = ({
  value = 0,
  size = 140,
  stroke = 12,
  color = '#1B93A4',
  trackClassName = 'text-muted/15',
  label,
  sublabel,
  centerClassName = '',
  animate = true,
}) => {
  const safeValue = Number.isFinite(Number(value))
    ? Math.max(0, Math.min(100, Number(value)))
    : 0;
  const [animated, setAnimated] = useState(animate ? 0 : safeValue);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  useEffect(() => {
    if (!animate) {
      setAnimated(safeValue);
      return undefined;
    }
    let frame;
    const start = performance.now();
    const duration = 800;
    const from = animated;
    const to = safeValue;
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimated(from + (to - from) * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeValue, animate]);

  const offset = circumference - (animated / 100) * circumference;
  const display = Math.round(animated);

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          className={trackClassName}
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div
        className={`absolute inset-0 flex flex-col items-center justify-center text-center ${centerClassName}`}
      >
        <span className="text-2xl font-bold font-cairo" style={{ color }}>
          {display}%
        </span>
        {label && (
          <span className="text-xs text-muted-foreground font-tajawal mt-0.5">
            {label}
          </span>
        )}
        {sublabel && (
          <span className="text-[10px] text-muted-foreground/70 font-tajawal mt-0.5">
            {sublabel}
          </span>
        )}
      </div>
    </div>
  );
};

export default CircularProgressRing;
