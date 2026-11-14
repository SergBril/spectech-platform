/**
 * Единая граница перехода ставки НДС ОСНО: документы до 2026 года — 20%,
 * начиная с 2026-01-01 — 22%. Синхронизировано с backend vat_rate_for_date
 * (app/core/constants.py). Не размазывать границу по компонентам.
 */
export const VAT_22_FROM_DATE = '2026-01-01';

/**
 * Ставка НДС ОСНО по дате документа (ISO YYYY-MM-DD).
 * Пустая дата трактуется как текущая эпоха (22).
 */
export const vatRateForDate = (date: string | null | undefined): '20' | '22' =>
  date && date < VAT_22_FROM_DATE ? '20' : '22';

/**
 * Дефолт ставки компании при смене системы налогообложения.
 * ОСНО с 2026 года — 22%; ненулевую выбранную ставку не перетираем.
 */
export const vatRateOnSystemChange = (newSystem: string, prevRate: number): number => {
  if (newSystem !== 'osno') return 0;
  return prevRate === 0 ? 22 : prevRate;
};
