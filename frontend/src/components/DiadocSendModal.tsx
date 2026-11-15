import React, { useCallback, useEffect, useRef, useState } from 'react';
import { financeApi, type DiadocCounterparty, type DiadocSendResult } from '../api/finance';

interface DiadocSendModalProps {
  actId: number;
  onClose: () => void;
  onSent: (result: DiadocSendResult) => void;
}

const errorDetail = (err: unknown, fallback: string): string => {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: unknown };
  if (typeof e?.response?.data?.detail === 'string') return e.response.data.detail;
  if (typeof e?.message === 'string') return e.message;
  return fallback;
};

/**
 * Общая модалка отправки акта через Diadoc (живой роут /shifts/diadoc/send-act).
 * Контрагент выбирается из /shifts/diadoc/counterparties; без выбора отправка запрещена.
 * После успеха показывает message из ответа и вызывает onSent (родитель обновляет данные).
 */
const DiadocSendModal: React.FC<DiadocSendModalProps> = ({ actId, onClose, onSent }) => {
  const [counterparties, setCounterparties] = useState<DiadocCounterparty[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [selectedBoxId, setSelectedBoxId] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState('');
  const [sentResult, setSentResult] = useState<DiadocSendResult | null>(null);
  const selectRef = useRef<HTMLSelectElement>(null);

  const loadCounterparties = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const list = await financeApi.getDiadocCounterparties();
      setCounterparties(list);
    } catch (err) {
      setLoadError(errorDetail(err, 'Не удалось загрузить контрагентов Diadoc'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCounterparties();
  }, [loadCounterparties]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!loading && !sentResult) selectRef.current?.focus();
  }, [loading, sentResult]);

  const handleSend = async () => {
    if (!selectedBoxId || sending) return;
    setSending(true);
    setSendError('');
    try {
      const result = await financeApi.sendToDiadoc(actId, selectedBoxId);
      setSentResult(result);
      onSent(result);
    } catch (err) {
      setSendError(errorDetail(err, 'Не удалось отправить акт'));
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="diadoc-send-modal-title"
        className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="diadoc-send-modal-title" className="text-lg font-bold text-gray-900">
            📤 Отправить акт в Diadoc
          </h2>
          <button
            onClick={onClose}
            aria-label="Закрыть"
            className="text-gray-400 hover:text-gray-600 transition leading-none text-lg"
          >
            ✕
          </button>
        </div>

        {sentResult ? (
          <div className="space-y-4">
            <div
              role="status"
              className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800"
            >
              ✅ <span>{sentResult.message}</span>
            </div>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
              >
                Готово
              </button>
            </div>
          </div>
        ) : (
          <>
            <div>
              <label htmlFor="diadoc-counterparty" className="block text-xs text-gray-500">
                Контрагент
              </label>
              <select
                id="diadoc-counterparty"
                ref={selectRef}
                value={selectedBoxId}
                onChange={(e) => setSelectedBoxId(e.target.value)}
                disabled={loading || sending}
                className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
              >
                <option value="">
                  {loading ? 'Загрузка контрагентов…' : 'Выберите контрагента...'}
                </option>
                {counterparties.map((c) => (
                  <option key={c.box_id} value={c.box_id}>
                    {c.name} (ИНН: {c.inn})
                  </option>
                ))}
              </select>
            </div>

            {loadError && (
              <div
                role="alert"
                className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-xs text-orange-700"
              >
                ⚠️ {loadError}{' '}
                <button onClick={loadCounterparties} className="underline hover:no-underline">
                  Повторить
                </button>
              </div>
            )}

            {!loading && !loadError && counterparties.length === 0 && (
              <p className="text-xs text-orange-600">
                ⚠️ Контрагенты не загружены. Проверьте настройки Diadoc.
              </p>
            )}

            {sendError && (
              <div
                role="alert"
                className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                ❌ {sendError}
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button
                onClick={onClose}
                disabled={sending}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 text-sm disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                onClick={handleSend}
                disabled={!selectedBoxId || sending || loading || counterparties.length === 0}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition"
              >
                {sending ? '⏳ Отправка...' : '📤 Отправить'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default DiadocSendModal;
