import React, { useState, useEffect, useRef, useMemo } from 'react';
import useHakimContext from './useHakimContext';

const SIZES = {
  xs: { img: 'w-10 h-10', msg: 'text-[10px] max-w-[120px] px-2 py-1', bubble: 'rounded-xl' },
  sm: { img: 'w-16 h-16', msg: 'text-xs max-w-[160px] px-3 py-1.5', bubble: 'rounded-xl' },
  md: { img: 'w-24 h-24', msg: 'text-sm max-w-[200px] px-3 py-2', bubble: 'rounded-2xl' },
  lg: { img: 'w-36 h-36', msg: 'text-sm max-w-[240px] px-4 py-2.5', bubble: 'rounded-2xl' },
  xl: { img: 'w-48 h-48', msg: 'text-base max-w-[280px] px-4 py-3', bubble: 'rounded-2xl' },
};

const HakimPresence = ({
  size = 'md',
  showMessage = true,
  messagePosition = 'top',
  placement = 'inline',
  className = '',
  onClick,
  autoDetect = true,
  overridePose,
  overrideMessage,
  overrideAnimation,
}) => {
  const ctx = useHakimContext({ autoDetect });
  const [msgVisible, setMsgVisible] = useState(false);
  const [imgLoaded, setImgLoaded] = useState(false);
  const timerRef = useRef(null);

  const poseUrl = overridePose || ctx.poseUrl;
  const message = overrideMessage || ctx.message;
  const animLevel = overrideAnimation || ctx.animationLevel;

  useEffect(() => {
    if (message && showMessage) {
      setMsgVisible(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      if (ctx.event) {
        timerRef.current = setTimeout(() => setMsgVisible(false), 8000);
      }
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [message, showMessage, ctx.event]);

  const sc = useMemo(() => SIZES[size] || SIZES.md, [size]);

  if (!ctx.visible) return null;

  const animClass =
    animLevel === 'celebration' ? 'hakim-presence-celebrate' :
    animLevel === 'interaction' ? 'hakim-presence-interact' :
    'hakim-presence-idle';

  const positionClass = placement === 'corner-bottom-start'
    ? 'fixed bottom-6 start-6 z-50'
    : placement === 'corner-bottom-end'
    ? 'fixed bottom-6 end-6 z-50'
    : '';

  const msgBubble = msgVisible && message && showMessage && (
    <div
      className={`${sc.msg} ${sc.bubble} font-tajawal text-center text-gray-700 shadow-sm border border-violet-100/50 transition-all duration-300`}
      style={{
        background: 'linear-gradient(135deg, rgba(124,58,237,0.06) 0%, rgba(27,147,164,0.06) 100%)',
        opacity: msgVisible ? 1 : 0,
        transform: msgVisible ? 'translateY(0)' : 'translateY(4px)',
      }}
    >
      {message}
    </div>
  );

  return (
    <>
      <style>{`
        .hakim-presence-idle { animation: hpFloat 4s ease-in-out infinite; }
        .hakim-presence-interact { animation: hpBounce 2s ease-in-out infinite; }
        .hakim-presence-celebrate { animation: hpCelebrate 1.2s ease-in-out 3; }
        @keyframes hpFloat {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes hpBounce {
          0%, 100% { transform: translateY(0) scale(1); }
          25% { transform: translateY(-5px) scale(1.02); }
          50% { transform: translateY(0) scale(1); }
          75% { transform: translateY(-3px) scale(1.01); }
        }
        @keyframes hpCelebrate {
          0%, 100% { transform: scale(1) rotate(0deg); }
          15% { transform: scale(1.08) rotate(-3deg); }
          30% { transform: scale(1.12) rotate(3deg); }
          45% { transform: scale(1.08) rotate(-2deg); }
          60% { transform: scale(1.05) rotate(2deg); }
          75% { transform: scale(1.02) rotate(-1deg); }
        }
      `}</style>
      <div
        className={`inline-flex flex-col items-center gap-1.5 select-none ${positionClass} ${className}`}
        dir="rtl"
      >
        {messagePosition === 'top' && msgBubble}
        <div
          className={`${animClass} cursor-pointer transition-opacity duration-500 ${imgLoaded ? 'opacity-100' : 'opacity-0'}`}
          onClick={onClick}
        >
          <img
            src={poseUrl}
            alt="حكيم"
            className={`${sc.img} object-contain drop-shadow-lg`}
            draggable={false}
            onLoad={() => setImgLoaded(true)}
          />
        </div>
        {messagePosition === 'bottom' && msgBubble}
      </div>
    </>
  );
};

export default HakimPresence;
