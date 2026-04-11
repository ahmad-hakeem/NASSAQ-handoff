import React from 'react';
import { useTranslation } from '../../contexts/ThemeContext';

const StudentSwitcher = ({ children, selectedIndex, onSelect }) => {
  const { t } = useTranslation();

  if (!children || children.length <= 1) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      {children.map((child, index) => (
        <button
          key={child.id}
          onClick={() => onSelect(index)}
          className={`flex items-center gap-2 px-4 py-2 rounded-full whitespace-nowrap transition-all text-sm font-medium
            ${index === selectedIndex
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200'
              : 'bg-white text-gray-700 border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50'
            }`}
        >
          <span className="text-lg">{child.emoji || '👦'}</span>
          <span>{child.name}</span>
        </button>
      ))}
    </div>
  );
};

export default StudentSwitcher;
