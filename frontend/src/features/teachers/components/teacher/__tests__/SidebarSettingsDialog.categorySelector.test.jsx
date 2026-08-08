/**
 * أنماط التقييم — every column row must expose a category selector
 * (أعمال السنة / الاختبارات) exactly like كشف المتابعة's إضافة عمود modal.
 *
 * Regression under test: the pattern editor silently classified every new
 * column as coursework (أعمال السنة) — there was no way to mark a column as
 * an exam column from Session Settings, while the monitoring sheet offered
 * the choice. Shared dialog: applies to School Teacher and Independent
 * Teacher alike.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

jest.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
}));
jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, onClick, ...p }) => <button onClick={onClick} {...p}>{children}</button>,
}));

import SidebarSettingsDialog from '../SidebarSettingsDialog';

const COLUMNS = [
  { id: 'part', name: 'المشاركة', group: 'coursework', maxGrade: 5, type: 'grade' },
  { id: 'quiz', name: 'اختبار قصير', group: 'exams', maxGrade: 10, type: 'grade' },
];

function renderPatternsTab(overrides = {}) {
  const onFollowupColumnsChange = jest.fn();
  render(
    <SidebarSettingsDialog
      open
      onOpenChange={() => {}}
      t={(k) => k}
      sessionConfig={{
        followupColumns: COLUMNS,
        onFollowupColumnsChange,
        showAddOtherItems: true,
        onShowAddOtherItemsChange: () => {},
        onSave: jest.fn(),
        ...overrides,
      }}
    />
  );
  // Navigate to the أنماط التقييم tab.
  fireEvent.click(screen.getByText('evaluationPatterns'));
  return { onFollowupColumnsChange };
}

describe('SidebarSettingsDialog — أنماط التقييم category selector', () => {
  test('each column row renders a category select with coursework/exams options', () => {
    renderPatternsTab();
    const partSelect = screen.getByTestId('col-group-part');
    const optionValues = Array.from(partSelect.querySelectorAll('option')).map((o) => o.value);
    expect(optionValues).toEqual(['coursework', 'exams']);
    expect(partSelect.value).toBe('coursework');
    // Existing exam column shows its stored category, not a silent default.
    expect(screen.getByTestId('col-group-quiz').value).toBe('exams');
  });

  test('changing the category fires onFollowupColumnsChange with the new group', () => {
    const { onFollowupColumnsChange } = renderPatternsTab();
    fireEvent.change(screen.getByTestId('col-group-part'), { target: { value: 'exams' } });
    expect(onFollowupColumnsChange).toHaveBeenCalledTimes(1);
    const updated = onFollowupColumnsChange.mock.calls[0][0];
    expect(updated.find((c) => c.id === 'part').group).toBe('exams');
    // Other columns untouched.
    expect(updated.find((c) => c.id === 'quiz').group).toBe('exams');
    expect(updated.find((c) => c.id === 'quiz').name).toBe('اختبار قصير');
  });
});
