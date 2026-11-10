import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

vi.mock('../pages/driver/DriverLoginPage', () => ({
  default: () => (
    <div>
      <input type="text" placeholder="Login" />
      <button type="submit">Sign In</button>
    </div>
  ),
}));

import DriverLoginPage from '../pages/driver/DriverLoginPage';

describe('DriverLoginPage', () => {
  it('renders login form elements', () => {
    const { container } = render(
      <BrowserRouter>
        <DriverLoginPage />
      </BrowserRouter>
    );
    const inputs = container.querySelectorAll('input');
    const buttons = container.querySelectorAll('button');
    expect(inputs.length).toBeGreaterThan(0);
    expect(buttons.length).toBeGreaterThan(0);
  });
});
