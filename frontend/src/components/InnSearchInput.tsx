import React, { useState } from 'react';
import { contractorsApi } from '../api/contractors';

interface InnSearchInputProps {
  inn: string;
  onInnChange: (inn: string) => void;
  onFound: (data: any) => void;
  onDuplicateFound?: (existingId: number, existingName: string) => void;
  disabled?: boolean;
}

export const InnSearchInput: React.FC<InnSearchInputProps> = ({
  inn,
  onInnChange,
  onFound,
  onDuplicateFound,
  disabled = false,
}) => {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning'; text: string } | null>(null);

  const handleSearch = async () => {
    if (!inn || inn.length < 10) {
      setMessage({ type: 'error', text: 'Введите ИНН (10 или 12 цифр)' });
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const result = await contractorsApi.suggestByInn(inn);

      if (result.duplicate && result.existing_id) {
        setMessage({
          type: 'warning',
          text: `⚠️ ${result.message}`,
        });
        onDuplicateFound?.(result.existing_id, result.existing_name || '');
      } else if (result.found && result.data) {
        setMessage({
          type: 'success',
          text: `✅ ${result.message}`,
        });
        onFound(result.data);
      } else {
        setMessage({
          type: 'error',
          text: `❌ ${result.message}`,
        });
      }
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: 'Ошибка поиска: ' + (err?.response?.data?.detail || err.message),
      });
    } finally {
      setLoading(false);
    }
  };

  const isValidInn = inn && (inn.length === 10 || inn.length === 12) && /^\d+$/.test(inn);

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        ИНН
      </label>
      <div className="flex gap-2 items-stretch">
        <input
          type="text"
          value={inn}
          onChange={(e) => {
            const value = e.target.value.replace(/\D/g, '').slice(0, 12);
            onInnChange(value);
            setMessage(null);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleSearch();
            }
          }}
          placeholder="7707083893"
          disabled={disabled || loading}
          className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100 h-[42px]"
        />
        <button
          type="button"
          onClick={handleSearch}
          disabled={disabled || loading || !isValidInn}
          className="shrink-0 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 whitespace-nowrap h-[42px]"
        >
          {loading ? (
            <>
              <span className="animate-spin">⏳</span>
              <span>Поиск...</span>
            </>
          ) : (
            <>
              <span>🔍</span>
              <span>Найти в ЕГРЮЛ</span>
            </>
          )}
        </button>
      </div>

      {/* Подсказка о формате */}
      {inn && !isValidInn && (
        <div className="mt-1 text-xs text-orange-600">
          ИНН должен содержать 10 (юр. лицо) или 12 (ИП) цифр
        </div>
      )}

      {/* Сообщение */}
      {message && (
        <div
          className={`mt-2 p-2 rounded text-sm ${
            message.type === 'success'
              ? 'bg-green-50 border border-green-200 text-green-800'
              : message.type === 'warning'
              ? 'bg-yellow-50 border border-yellow-200 text-yellow-800'
              : 'bg-red-50 border border-red-200 text-red-800'
          }`}
        >
          {message.text}
        </div>
      )}
    </div>
  );
};

export default InnSearchInput;
