import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/principal/communication' }),
}), { virtual: true });

const mockApi = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
};

const mockUser = { id: 'u1', role: 'school_principal', school_id: 'sch1' };

// Mock dependencies
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, isDark: false }),
  useTranslation: () => ({
    t: (key) => {
      const dict = {
        communicationCenter: 'مركز التواصل',
        sent: 'المرسلة',
        sent2: 'تم الإرسال',
        sentMessages2: 'الرسائل المرسلة',
        recipients3: 'مستلم',
        recipients2: 'المستلمون:',
        audience: 'الجمهور:',
        sentAt: 'أرسلت في:',
      };
      return dict[key] || key;
    },
  }),
}));

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    hasRole: () => true,
    api: mockApi,
  }),
}));

jest.mock('@/shared/contexts/WebSocketContext', () => ({
  useWebSocket: () => ({
    isConnected: true,
    lastMessage: null,
    on: jest.fn(() => () => {}),
  }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqConfirm: jest.fn(),
    nassaqSuccess: jest.fn(),
    nassaqError: jest.fn(),
    nassaqWarning: jest.fn(),
  }),
}));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar-wrapper">{children}</div>,
}));

import { CommunicationCenterPage } from '../pages/CommunicationCenterPage';

const CONTINUOUS_LONG_TEXT = 'test1test1test1test1test1test1test1test1test1test1test1test1test1test1test1test1test1test1test1test1';

describe('CommunicationCenterPage — Message Details Modal Text Wrapping', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi.get.mockImplementation((url) => {
      if (url === '/communication/stats') {
        return Promise.resolve({ data: { total_sent: 1, total_scheduled: 0, total_drafts: 0 } });
      }
      if (url.startsWith('/communication?limit=100')) {
        return Promise.resolve({
          data: {
            messages: [
              {
                id: 'msg_1',
                title: 'رسالة تجريبية بنص طويل جداً',
                content: CONTINUOUS_LONG_TEXT,
                audience: 'all',
                status: 'sent',
                recipient_count: 25,
                sent_at: '2026-08-27T10:00:00Z',
                created_at: '2026-08-27T10:00:00Z',
              },
            ],
          },
        });
      }
      if (url === '/communication/received') {
        return Promise.resolve({ data: { messages: [] } });
      }
      if (url === '/communication/audience') {
        return Promise.resolve({
          data: [
            { id: 'all', name: 'الجميع', name_en: 'All' },
            { id: 'teachers', name: 'المعلمون', name_en: 'Teachers' },
          ],
        });
      }
      if (url === '/notifications/sent-circulars?limit=50') {
        return Promise.resolve({ data: { circulars: [] } });
      }
      if (url === '/communication/notifications') {
        return Promise.resolve({ data: { notifications: [], total: 0, unread: 0 } });
      }
      if (url === '/absence-excuses/pending-count') {
        return Promise.resolve({ data: { count: 0 } });
      }
      return Promise.resolve({ data: [] });
    });
  });

  test('opens details modal on sent message click and applies word-wrap classes to prevent overflow', async () => {
    render(<CommunicationCenterPage />);

    // Wait for initial data fetch and page render
    await waitFor(() => {
      expect(screen.getByTestId('tab-sent')).toBeInTheDocument();
    });

    // Switch to 'sent' tab
    const sentTab = screen.getByTestId('tab-sent');
    fireEvent.click(sentTab);

    // Find the sent message card
    const messageTitle = await screen.findByText('رسالة تجريبية بنص طويل جداً');
    expect(messageTitle).toBeInTheDocument();

    // Click on the message card to open the details modal
    fireEvent.click(messageTitle);

    // Verify modal content is rendered
    const modalContent = await screen.findByTestId('view-message-content');
    expect(modalContent).toBeInTheDocument();
    expect(modalContent.textContent).toBe(CONTINUOUS_LONG_TEXT);

    // Verify critical CSS classes for containing long unbroken strings
    expect(modalContent.className).toContain('break-words');
    expect(modalContent.className).toContain('whitespace-pre-wrap');
    expect(modalContent.className).toContain('[overflow-wrap:anywhere]');
  });
});
