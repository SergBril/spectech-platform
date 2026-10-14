import React, { useState, useRef } from 'react';
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

  // DaData live suggestions
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = async () => {
    if (!inn || inn.length < 10) {
      setMessage({ type: 'error', text: 'Введите ИНН (10 или 12 цифр)' });
      return;
    }

    setLoading(true);
    setMessage(null);
    setShowSuggestions(false);

    try {
      const result = await contractorsApi.suggestByInn(inn);

      if (result.duplicate && result.existing_id) {
        setMessage({ type: 'warning', text: `⚠️ ${result.message}` });
        onDuplicateFound?.(result.existing_id, result.existing_name || '');
      } else if (result.found && result.data) {
        setMessage({ type: 'success', text: `✅ ${result.message}` });
        onFound(result.data);
      } else {
        setMessage({ type: 'error', text: `❌ ${result.message}` });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: 'Ошибка поиска: ' + (err?.response?.data?.detail || err.message) });
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (value: string) => {
    const cleaned = value.replace(/\D/g, '').slice(0, 12);
    onInnChange(cleaned);
    setMessage(null);

    // Live DaData suggestions
    if (timerRef.current) clearTimeout(timerRef.current);
    if (cleaned.length < 3) {
      setShowSuggestions(false);
      setSuggestions([]);
      return;
    }

    timerRef.current = setTimeout(async () => {
      try {
        const token = localStorage.getItem('access_token');
        const apiUrl = import.meta.env.VITE_API_URL;
        const response = await fetch(`${apiUrl}/companies/dadata/suggest/party`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ query: cleaned, count: 5 }),
        });
        const data = await response.json();
        if (data.suggestions?.length > 0) {
          setSuggestions(data.suggestions);
          setShowSuggestions(true);
        } else {
          setShowSuggestions(false);
        }
      } catch {
        setShowSuggestions(false);
      }
    }, 300);
  };

  const applySuggestion = (suggestion: any) => {
    const p = suggestion.data;
    onFound({
      name: p.name?.short_with_opf || p.name?.full_with_opf || suggestion.value,
      inn: p.inn || '',
      kpp: p.kpp || '',
      ogrn: p.ogrn || '',
      address: p.address?.value || '',
      bank_name: p.finance?.bank_name || '',
      bank_bik: p.finance?.bank_bik || '',
      bank_account: p.finance?.bank_account || '',
      bank_correspondent_account: p.finance?.bank_correspondent_account || '',
      management_name: p.management?.name || '',
      management_post: p.management?.post || '',
    });
    onInnChange(p.inn || inn);
    setShowSuggestions(false);
    setSuggestions([]);
    setMessage({ type: 'success', text: `✅ ${suggestion.value}` });
  };

  const isValidInn = inn && (inn.length === 10 || inn.length === 12) && /^\d+$/.test(inn);

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">ИНН</label>
      <div className="flex gap-2 items-stretch">
        <input
          type="text"
          value={inn}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleSearch();
            }
          }}
          onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
          placeholder="7707083893"
          disabled={disabled || loading}
          autoComplete="off"
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

      {/* Живые подсказки DaData */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-xl max-h-48 overflow-y-auto">
          {suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                applySuggestion(s);
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors border-b border-gray-100 last:border-0"
            >
              <div className="font-medium text-gray-900">{s.value}</div>
              {s.data?.inn && <div className="text-xs text-gray-500">ИНН: {s.data.inn}</div>}
              {s.data?.address?.value && (
                <div className="text-xs text-gray-500 truncate">{s.data.address.value}</div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Сообщение от кнопки поиска */}
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