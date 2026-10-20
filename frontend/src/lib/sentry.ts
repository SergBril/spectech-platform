import * as Sentry from '@sentry/react';

// Инициализация Sentry для отслеживания ошибок в production
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;

if (SENTRY_DSN && SENTRY_DSN.trim() !== '') {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: false,
        blockAllMedia: false,
      }),
    ],
    // Производительность
    tracesSampleRate: 0.1, // 10% транзакций
    // Сессии
    replaysSessionSampleRate: 0.1, // 10% сессий
    replaysOnErrorSampleRate: 1.0, // 100% при ошибке
    // Фильтрация
    beforeSend(event) {
      // Игнорируем ошибки от расширений браузера
      if (event.exception?.values?.some(v => v.value?.includes('extension'))) {
        return null;
      }
      return event;
    },
  });

  console.log('✅ Sentry initialized');
} else {
  console.log('⚠️  Sentry DSN not configured, skipping initialization');
}

export { Sentry };
