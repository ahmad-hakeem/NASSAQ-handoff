import { useState, useEffect, useRef, useMemo } from 'react';
import { getPose, getRandomPoseFromCategory } from './hakimPoses';

const ANIMATION_LEVEL = {
  IDLE: 'idle',
  INTERACTION: 'interaction',
  CELEBRATION: 'celebration',
};

const HakimReaction = ({
  pose = null,
  category = null,
  animationLevel = ANIMATION_LEVEL.IDLE,
  size = 'md',
  message = '',
  showMessage = true,
  className = '',
  onClick,
  messagePosition = 'top',
  rotatePoses = false,
  rotateInterval = 8000,
}) => {
  const [currentPose, setCurrentPose] = useState(null);
  const [fadeIn, setFadeIn] = useState(true);
  const rotationRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (pose) {
      setCurrentPose(getPose(pose));
    } else if (category) {
      setCurrentPose(getRandomPoseFromCategory(category));
    } else {
      setCurrentPose(getPose('friendly-greeting'));
    }
  }, [pose, category]);

  useEffect(() => {
    if (!rotatePoses || !category) return;
    rotationRef.current = setInterval(() => {
      if (!mountedRef.current) return;
      setFadeIn(false);
      setTimeout(() => {
        if (!mountedRef.current) return;
        setCurrentPose(getRandomPoseFromCategory(category));
        setFadeIn(true);
      }, 300);
    }, rotateInterval);
    return () => clearInterval(rotationRef.current);
  }, [rotatePoses, category, rotateInterval]);

  const sizeConfig = useMemo(() => ({
    xs: { imgClass: 'w-12 h-12', msgClass: 'text-xs max-w-[140px]' },
    sm: { imgClass: 'w-20 h-20', msgClass: 'text-sm max-w-[180px]' },
    md: { imgClass: 'w-[120px] h-[120px]', msgClass: 'text-sm max-w-[220px]' },
    lg: { imgClass: 'w-[180px] h-[180px]', msgClass: 'text-base max-w-[280px]' },
    xl: { imgClass: 'w-[260px] h-[260px]', msgClass: 'text-base max-w-[320px]' },
    '2xl': { imgClass: 'w-[360px] h-[360px]', msgClass: 'text-lg max-w-[380px]' },
    hero: { imgClass: 'w-[480px] h-[480px]', msgClass: 'text-lg max-w-[440px]' },
  }), []);

  const sc = sizeConfig[size] || sizeConfig.md;

  const animClass = animationLevel === ANIMATION_LEVEL.CELEBRATION
    ? 'hakim-celebrate-anim'
    : animationLevel === ANIMATION_LEVEL.INTERACTION
    ? 'hakim-interact-anim'
    : 'hakim-idle-anim';

  if (!currentPose) return null;

  return (
    <div className={`inline-flex flex-col items-center gap-2 relative ${className}`} dir="rtl">
      <style>{`
        .hakim-idle-anim {
          animation: hakimRxFloat 4s ease-in-out infinite;
        }
        .hakim-interact-anim {
          animation: hakimRxBounce 2s ease-in-out infinite;
        }
        .hakim-celebrate-anim {
          animation: hakimRxCelebrate 1.2s ease-in-out 3;
        }
        .hakim-pose-fade-in {
          opacity: 1;
          transition: opacity 0.3s ease-in-out;
        }
        .hakim-pose-fade-out {
          opacity: 0;
          transition: opacity 0.3s ease-in-out;
        }
        @keyframes hakimRxFloat {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        @keyframes hakimRxBounce {
          0%, 100% { transform: translateY(0) scale(1); }
          25% { transform: translateY(-6px) scale(1.02); }
          50% { transform: translateY(0) scale(1); }
          75% { transform: translateY(-3px) scale(1.01); }
        }
        @keyframes hakimRxCelebrate {
          0%, 100% { transform: scale(1) rotate(0deg); }
          15% { transform: scale(1.08) rotate(-3deg); }
          30% { transform: scale(1.12) rotate(3deg); }
          45% { transform: scale(1.08) rotate(-2deg); }
          60% { transform: scale(1.05) rotate(2deg); }
          75% { transform: scale(1.02) rotate(-1deg); }
        }
        @keyframes hakimRxMsgFade {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {showMessage && message && messagePosition === 'top' && (
        <div
          className={`${sc.msgClass} font-cairo text-center rounded-2xl px-4 py-2.5`}
          style={{
            background: 'linear-gradient(135deg, rgba(124,58,237,0.08) 0%, rgba(27,147,164,0.08) 100%)',
            border: '1px solid rgba(124,58,237,0.15)',
            animation: 'hakimRxMsgFade 0.4s ease-out both',
          }}
        >
          {message}
        </div>
      )}

      <div
        className={`${animClass} cursor-pointer select-none ${fadeIn ? 'hakim-pose-fade-in' : 'hakim-pose-fade-out'}`}
        onClick={onClick}
      >
        <img
          src={currentPose}
          alt="حكيم"
          className={`${sc.imgClass} object-contain drop-shadow-lg`}
          draggable={false}
        />
      </div>

      {showMessage && message && messagePosition === 'bottom' && (
        <div
          className={`${sc.msgClass} font-cairo text-center rounded-2xl px-4 py-2.5`}
          style={{
            background: 'linear-gradient(135deg, rgba(124,58,237,0.08) 0%, rgba(27,147,164,0.08) 100%)',
            border: '1px solid rgba(124,58,237,0.15)',
            animation: 'hakimRxMsgFade 0.4s ease-out both',
          }}
        >
          {message}
        </div>
      )}
    </div>
  );
};

export { ANIMATION_LEVEL };
export default HakimReaction;
