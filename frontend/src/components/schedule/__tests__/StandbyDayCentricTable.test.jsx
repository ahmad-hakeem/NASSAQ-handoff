/**
 * StandbyDayCentricTable — multi-teacher standby affordance regression guard.
 *
 * Task: Let principals assign multiple teachers to one waiting period.
 *
 * The day-centric grid renders exactly `slot_count` sub-rows per day, where
 * `slot_count` = the max teachers already assigned to any single period that
 * day. When every period holds at most one teacher, only one row rendered — so
 * there was no empty "+" cell under a filled period to add a second teacher.
 *
 * These tests lock in the fix: the table always renders ONE trailing empty
 * "add another" row (slot_index = slot_count + 1), so every period — including
 * one that already shows a teacher — exposes a "+" cell that opens the picker
 * anchored to (day, period, next slot_index).
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

import StandbyDayCentricTable from '../StandbyDayCentricTable';

const PERIODS = [1, 2];

// Sunday has one teacher on period 1 (slot 1); every period holds at most one
// teacher, so the backend projects slot_count = 1.
const DAY_CENTRIC = {
  days: [
    {
      day: 'sunday',
      slot_count: 1,
      rows: [
        {
          slot_index: 1,
          cells: {
            1: {
              teacher_id: 't-1',
              teacher_name: 'أحمد',
              subject: 'رياضيات',
              source: 'auto',
            },
            2: null,
          },
        },
      ],
    },
  ],
  warnings: [],
};

const renderTable = (props = {}) =>
  render(
    <StandbyDayCentricTable
      loading={false}
      error=""
      dayCentric={DAY_CENTRIC}
      periods={PERIODS}
      busyCellKey={null}
      onCellClick={() => {}}
      {...props}
    />,
  );

describe('StandbyDayCentricTable — trailing "add another" row', () => {
  test('renders one trailing empty row beyond slot_count for every day', () => {
    renderTable();
    // slot_count = 1, so the trailing row is slot_index = 2. Its cells for
    // BOTH periods must be empty "+" buttons.
    expect(screen.getByTestId('standby-cell-sunday-1-2')).toBeInTheDocument();
    expect(screen.getByTestId('standby-cell-sunday-2-2')).toBeInTheDocument();
    // Never renders a second trailing row (slot 3).
    expect(screen.queryByTestId('standby-cell-sunday-1-3')).toBeNull();
  });

  test('period that already holds a teacher still exposes a "+" cell in the trailing row', () => {
    const onCellClick = jest.fn();
    renderTable({ onCellClick });

    // Period 1 already shows أحمد in slot 1. The trailing row gives period 1
    // an empty "+" cell anchored to the next slot_index (2).
    const addSecond = screen.getByTestId('standby-cell-sunday-1-2');
    fireEvent.click(addSecond);

    expect(onCellClick).toHaveBeenCalledTimes(1);
    expect(onCellClick.mock.calls[0][0]).toMatchObject({
      day: 'sunday',
      period: 1,
      slot_index: 2,
    });
    // It's an add (no existing cell), so the payload carries no filled cell.
    expect(onCellClick.mock.calls[0][0].cell).toBeFalsy();
  });

  test('the filled period cell still opens its remove/reset flow (unchanged)', () => {
    const onCellClick = jest.fn();
    renderTable({ onCellClick });

    // Clicking the filled teacher cell passes the existing cell through so the
    // page can offer remove/reset — this behavior must be unchanged.
    fireEvent.click(screen.getByRole('button', { name: /أحمد/ }));
    expect(onCellClick).toHaveBeenCalledTimes(1);
    expect(onCellClick.mock.calls[0][0]).toMatchObject({
      day: 'sunday',
      period: 1,
      slot_index: 1,
    });
    expect(onCellClick.mock.calls[0][0].cell.teacher_id).toBe('t-1');
  });
});
