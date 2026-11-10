import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EmptyState } from '../components/EmptyState';

describe('EmptyState', () => {
  it('renders icon and title', () => {
    render(<EmptyState icon="🚜" title="Нет техники" />);
    expect(screen.getByText('🚜')).toBeTruthy();
    expect(screen.getByText('Нет техники')).toBeTruthy();
  });

  it('renders description when provided', () => {
    render(
      <EmptyState
        icon="📋"
        title="Нет заявок"
        description="Создайте первую заявку"
      />
    );
    expect(screen.getByText('Создайте первую заявку')).toBeTruthy();
  });

  it('renders action button and calls handler', async () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        icon="➕"
        title="Пусто"
        actionLabel="Добавить"
        onAction={onAction}
      />
    );
    const button = screen.getByText('Добавить');
    await userEvent.click(button);
    expect(onAction).toHaveBeenCalledOnce();
  });

  it('renders both primary and secondary actions', () => {
    render(
      <EmptyState
        icon="🔍"
        title="Не найдено"
        actionLabel="Поискать"
        onAction={() => {}}
        secondaryActionLabel="Сбросить"
        onSecondaryAction={() => {}}
      />
    );
    expect(screen.getByText('Поискать')).toBeTruthy();
    expect(screen.getByText('Сбросить')).toBeTruthy();
  });
});
