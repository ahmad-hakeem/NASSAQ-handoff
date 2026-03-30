import React from 'react';

export function FormGrid({ children, columns = 2, className = '' }) {
  const colClass = columns === 3
    ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
    : columns === 1
    ? 'grid-cols-1'
    : 'grid-cols-1 md:grid-cols-2';

  return (
    <div className={`grid ${colClass} gap-4 ${className}`}>
      {children}
    </div>
  );
}

export function FormGridItem({ children, colSpan = 1, className = '' }) {
  const spanClass = colSpan === 2 ? 'md:col-span-2' : colSpan === 3 ? 'md:col-span-3' : '';
  return (
    <div className={`${spanClass} ${className}`}>
      {children}
    </div>
  );
}
