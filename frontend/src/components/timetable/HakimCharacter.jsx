import React, { useState, useEffect } from 'react';

const HAKIM_MESSAGES = {
  idle: [
    'مرحباً! أنا حكيم، مساعدك الذكي 🤖',
    'هل تحتاج مساعدة في الجدول؟',
    'اضغط على الزر لأبدأ العمل!',
    'جاهز لتوليد أفضل جدول ممكن ✨',
  ],
  generating: [
    'أعمل على تحليل البيانات...',
    'أبحث عن أفضل توزيع للحصص...',
    'أتأكد من عدم وجود تعارضات...',
    'أوشكت على الانتهاء! 🎯',
    'أراعي توازن حصص المعلمين...',
  ],
  success: [
    'تم بنجاح! الجدول جاهز 🎉',
    'أنجزت المهمة! راجع الجدول الآن',
  ],
  error: [
    'واجهت مشكلة، حاول مرة أخرى',
    'لا تقلق، يمكننا المحاولة مجدداً',
  ],
};

const HakimCharacter = ({
  state = 'idle',
  size = 'md',
  showMessage = true,
  className = '',
  onClick,
}) => {
  const [messageIndex, setMessageIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);
  const [eyeBlink, setEyeBlink] = useState(false);

  const messages = HAKIM_MESSAGES[state] || HAKIM_MESSAGES.idle;

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex(prev => (prev + 1) % messages.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [messages.length, state]);

  useEffect(() => {
    const blinkInterval = setInterval(() => {
      setEyeBlink(true);
      setTimeout(() => setEyeBlink(false), 200);
    }, 3500 + Math.random() * 2000);
    return () => clearInterval(blinkInterval);
  }, []);

  const sizeMap = {
    sm: { container: 64, img: 58 },
    md: { container: 96, img: 88 },
    lg: { container: 120, img: 110 },
    xl: { container: 160, img: 148 },
  };
  const s = sizeMap[size] || sizeMap.md;

  const stateClasses = {
    idle: 'hakim-idle',
    generating: 'hakim-generating',
    success: 'hakim-success',
    error: 'hakim-error',
  };

  return (
    <div className={`hakim-wrapper ${className}`} dir="rtl">
      <style>{`
        .hakim-wrapper {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .hakim-container {
          position: relative;
          cursor: pointer;
          flex-shrink: 0;
        }

        .hakim-glow {
          position: absolute;
          inset: -4px;
          border-radius: 50%;
          opacity: 0.4;
          transition: opacity 0.3s ease;
        }

        .hakim-container:hover .hakim-glow {
          opacity: 0.7;
        }

        .hakim-idle .hakim-glow {
          background: radial-gradient(circle, rgba(124,58,237,0.3) 0%, transparent 70%);
          animation: hakimPulse 3s ease-in-out infinite;
        }

        .hakim-generating .hakim-glow {
          background: radial-gradient(circle, rgba(27,147,164,0.4) 0%, transparent 70%);
          animation: hakimPulse 1.5s ease-in-out infinite;
        }

        .hakim-success .hakim-glow {
          background: radial-gradient(circle, rgba(34,197,94,0.4) 0%, transparent 70%);
          animation: hakimPulse 2s ease-in-out infinite;
        }

        .hakim-error .hakim-glow {
          background: radial-gradient(circle, rgba(239,68,68,0.3) 0%, transparent 70%);
          animation: hakimPulse 2s ease-in-out infinite;
        }

        .hakim-avatar-ring {
          position: relative;
          border-radius: 50%;
          overflow: hidden;
          transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .hakim-container:hover .hakim-avatar-ring {
          transform: scale(1.08);
        }

        .hakim-idle .hakim-avatar-ring {
          animation: hakimFloat 4s ease-in-out infinite;
          box-shadow: 0 4px 20px rgba(124,58,237,0.2);
        }

        .hakim-generating .hakim-avatar-ring {
          animation: hakimWork 2s ease-in-out infinite;
          box-shadow: 0 4px 24px rgba(27,147,164,0.3);
        }

        .hakim-success .hakim-avatar-ring {
          animation: hakimCelebrate 1.5s ease-in-out 3;
          box-shadow: 0 4px 20px rgba(34,197,94,0.25);
        }

        .hakim-error .hakim-avatar-ring {
          animation: hakimShake 0.5s ease-in-out 2;
          box-shadow: 0 4px 20px rgba(239,68,68,0.2);
        }

        .hakim-avatar-ring img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          border-radius: 50%;
          transition: filter 0.3s ease;
        }

        .hakim-blink img {
          filter: brightness(0.97);
        }

        .hakim-ring-border {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          pointer-events: none;
        }

        .hakim-idle .hakim-ring-border {
          border: 2.5px solid rgba(124,58,237,0.4);
        }

        .hakim-generating .hakim-ring-border {
          border: 2.5px solid transparent;
          border-top-color: rgba(27,147,164,0.7);
          border-right-color: rgba(124,58,237,0.5);
          animation: hakimSpin 2s linear infinite;
        }

        .hakim-success .hakim-ring-border {
          border: 2.5px solid rgba(34,197,94,0.5);
        }

        .hakim-error .hakim-ring-border {
          border: 2.5px solid rgba(239,68,68,0.4);
        }

        .hakim-status-dot {
          position: absolute;
          bottom: 2px;
          left: 2px;
          width: 14px;
          height: 14px;
          border-radius: 50%;
          border: 2.5px solid white;
          z-index: 2;
        }

        .hakim-idle .hakim-status-dot {
          background: #7C3AED;
          animation: hakimDotPulse 2s ease-in-out infinite;
        }

        .hakim-generating .hakim-status-dot {
          background: #1B93A4;
          animation: hakimDotPulse 1s ease-in-out infinite;
        }

        .hakim-success .hakim-status-dot {
          background: #22c55e;
        }

        .hakim-error .hakim-status-dot {
          background: #ef4444;
        }

        .hakim-bubble {
          position: relative;
          background: white;
          border-radius: 14px;
          padding: 8px 14px;
          box-shadow: 0 2px 12px rgba(0,0,0,0.08);
          border: 1px solid rgba(0,0,0,0.06);
          max-width: 220px;
          animation: hakimBubbleIn 0.3s ease-out;
        }

        .hakim-bubble::after {
          content: '';
          position: absolute;
          right: -6px;
          top: 14px;
          width: 12px;
          height: 12px;
          background: white;
          border-right: 1px solid rgba(0,0,0,0.06);
          border-bottom: 1px solid rgba(0,0,0,0.06);
          transform: rotate(-45deg);
        }

        .hakim-idle .hakim-bubble {
          border-color: rgba(124,58,237,0.15);
        }
        .hakim-idle .hakim-bubble::after {
          border-color: rgba(124,58,237,0.15);
        }

        .hakim-generating .hakim-bubble {
          border-color: rgba(27,147,164,0.2);
        }
        .hakim-generating .hakim-bubble::after {
          border-color: rgba(27,147,164,0.2);
        }

        .hakim-success .hakim-bubble {
          border-color: rgba(34,197,94,0.2);
        }
        .hakim-success .hakim-bubble::after {
          border-color: rgba(34,197,94,0.2);
        }

        .hakim-generating .hakim-dots {
          display: inline-flex;
          gap: 3px;
          margin-inline-start: 6px;
        }

        .hakim-generating .hakim-dots span {
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: #1B93A4;
          animation: hakimDotBounce 1.2s ease-in-out infinite;
        }

        .hakim-generating .hakim-dots span:nth-child(2) {
          animation-delay: 0.2s;
        }

        .hakim-generating .hakim-dots span:nth-child(3) {
          animation-delay: 0.4s;
        }

        .hakim-hand {
          position: absolute;
          font-size: 18px;
          z-index: 3;
        }

        .hakim-idle .hakim-hand {
          bottom: -2px;
          right: -8px;
          animation: hakimWave 3s ease-in-out infinite;
        }

        .hakim-generating .hakim-hand {
          bottom: -2px;
          right: -8px;
          animation: hakimThinking 2s ease-in-out infinite;
        }

        .hakim-success .hakim-hand {
          bottom: -2px;
          right: -8px;
          animation: hakimThumbsUp 1s ease-in-out 3;
        }

        @keyframes hakimFloat {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          50% { transform: translateY(-4px) rotate(1deg); }
        }

        @keyframes hakimWork {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          25% { transform: translateY(-3px) rotate(-1.5deg); }
          75% { transform: translateY(-2px) rotate(1.5deg); }
        }

        @keyframes hakimCelebrate {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-6px) scale(1.05); }
        }

        @keyframes hakimShake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-3px); }
          75% { transform: translateX(3px); }
        }

        @keyframes hakimPulse {
          0%, 100% { transform: scale(1); opacity: 0.4; }
          50% { transform: scale(1.1); opacity: 0.6; }
        }

        @keyframes hakimDotPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.3); }
        }

        @keyframes hakimSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        @keyframes hakimBubbleIn {
          from { opacity: 0; transform: translateX(8px) scale(0.95); }
          to { opacity: 1; transform: translateX(0) scale(1); }
        }

        @keyframes hakimWave {
          0%, 60%, 100% { transform: rotate(0deg); }
          10% { transform: rotate(14deg); }
          20% { transform: rotate(-8deg); }
          30% { transform: rotate(14deg); }
          40% { transform: rotate(-4deg); }
          50% { transform: rotate(10deg); }
        }

        @keyframes hakimThinking {
          0%, 100% { transform: rotate(0deg) translateY(0); }
          50% { transform: rotate(8deg) translateY(-2px); }
        }

        @keyframes hakimThumbsUp {
          0%, 100% { transform: scale(1) rotate(0deg); }
          50% { transform: scale(1.3) rotate(-10deg); }
        }

        @keyframes hakimDotBounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-5px); }
        }
      `}</style>

      <div
        className={`hakim-container ${stateClasses[state] || 'hakim-idle'}`}
        onClick={onClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ width: s.container, height: s.container }}
      >
        <div className="hakim-glow" />
        <div
          className={`hakim-avatar-ring ${eyeBlink ? 'hakim-blink' : ''}`}
          style={{ width: s.img, height: s.img, margin: 'auto', marginTop: (s.container - s.img) / 2 }}
        >
          <img
            src={state === 'generating' ? '/hakim-poses/ai-thinking.png' : state === 'success' ? '/hakim-poses/positive-feedback.png' : state === 'error' ? '/hakim-poses/attention-gesture.png' : '/hakim-poses/friendly-greeting.png'}
            alt="حكيم - المساعد الذكي"
            draggable={false}
            style={{ objectFit: 'contain' }}
          />
          <div className="hakim-ring-border" />
        </div>
        <div className="hakim-status-dot" />
        {size !== 'sm' && (
          <div className="hakim-hand">
            {state === 'success' ? '👍' : state === 'generating' ? '🤔' : '👋'}
          </div>
        )}
      </div>

      {showMessage && (
        <div className="hakim-bubble">
          <p style={{
            fontSize: size === 'sm' ? 10 : 12,
            fontWeight: 500,
            color: state === 'generating' ? '#0F2C59' : state === 'success' ? '#166534' : state === 'error' ? '#991b1b' : '#374151',
            lineHeight: 1.5,
            margin: 0,
          }}>
            {messages[messageIndex]}
            {state === 'generating' && (
              <span className="hakim-dots">
                <span /><span /><span />
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  );
};

export default HakimCharacter;
