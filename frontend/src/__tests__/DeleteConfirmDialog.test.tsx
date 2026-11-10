import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';

describe('DeleteConfirmDialog', () => {
  it('renders with vehicle name', () => {
    const { container } = render(
      <DeleteConfirmDialog
        vehicleName="Test Vehicle"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );
    expect(container.textContent).toContain('Test Vehicle');
  });

  it('renders custom title and message', () => {
    const { container } = render(
      <DeleteConfirmDialog
        title="Custom Title"
        message="Custom Message"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );
    expect(container.textContent).toContain('Custom Title');
    expect(container.textContent).toContain('Custom Message');
  });

  it('calls onConfirm when delete button clicked', async () => {
    const onConfirm = vi.fn();
    const { container } = render(
      <DeleteConfirmDialog
        onConfirm={onConfirm}
        onCancel={() => {}}
      />
    );
    // Find the red delete button (last button in dialog)
    const buttons = container.querySelectorAll('button');
    const deleteButton = buttons[buttons.length - 1];
    await userEvent.click(deleteButton);
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it('calls onCancel when cancel button clicked', async () => {
    const onCancel = vi.fn();
    const { container } = render(
      <DeleteConfirmDialog
        onConfirm={() => {}}
        onCancel={onCancel}
      />
    );
    // Cancel is the first button
    const buttons = container.querySelectorAll('button');
    await userEvent.click(buttons[0]);
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
