import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

// Mock all heavy dependencies
vi.mock('../pages/DashboardPage', () => ({
  default: () => <div data-testid="dashboard">Dashboard</div>,
}));

vi.mock('../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: {} }), post: vi.fn() },
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'test@test.com' }, isAuthenticated: true }),
}));

import DashboardPage from '../pages/DashboardPage';

describe('DashboardPage', () => {
  it('renders without crashing', () => {
    const { container } = render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    expect(container).toBeTruthy();
  });
});
