import React from 'react';

const StudentSwitcher = ({ children, selectedIndex, onSelect }) => {
  if (!children || children.length <= 1) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide -mx-1 px-1">
      {children.map((child, index) => {
        const isSelected = index === selectedIndex;
        const initials = child.name?.charAt(0) || '?';

        return (
          <button
            key={child.id}
            onClick={() => onSelect(index)}
            className={`flex items-center gap-2.5 px-4 py-2.5 rounded-2xl whitespace-nowrap transition-all duration-200 text-sm font-medium min-w-0
              ${isSelected
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-200 scale-[1.02]'
                : 'bg-white text-gray-700 border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 hover:shadow-sm'
              }`}
            data-testid={`student-switcher-${index}`}
          >
            {child.profile_picture || child.photo_url ? (
              <img
                src={child.profile_picture || child.photo_url}
                alt={child.name}
                className={`w-7 h-7 rounded-full object-cover border-2 ${isSelected ? 'border-white/40' : 'border-indigo-100'}`}
              />
            ) : (
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                ${isSelected ? 'bg-white/20 text-white' : 'bg-indigo-100 text-indigo-600'}`}>
                {initials}
              </div>
            )}
            <div className="flex flex-col items-start">
              <span className="leading-tight">{child.name?.split(' ')[0]}</span>
              {child.grade && (
                <span className={`text-[10px] leading-tight ${isSelected ? 'text-indigo-200' : 'text-gray-400'}`}>
                  {child.grade}
                </span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default StudentSwitcher;
