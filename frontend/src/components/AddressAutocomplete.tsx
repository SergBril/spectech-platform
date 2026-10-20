import React, { useState, useEffect, useRef } from 'react';

interface AddressSuggestion {
  value: string;
  unrestricted_value: string;
  data: {
    city_with_type?: string;
    street_with_type?: string;
    house?: string;
    region_with_type?: string;
  };
}

interface AddressAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

const AddressAutocomplete: React.FC<AddressAutocompleteProps> = ({
  value,
  onChange,
  placeholder = 'Введите адрес...',
}) => {
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const DADATA_TOKEN = import.meta.env.VITE_DADATA_TOKEN;
  const DADATA_API_URL = 'https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address';

  useEffect(() => {
    if (value.length < 3) {
      setSuggestions([]);
      return;
    }

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(async () => {
      setIsLoading(true);
      try {
        console.log('[AddressAutocomplete] Fetching suggestions for:', value);
        const response = await fetch(DADATA_API_URL, {
          method: 'POST',
          mode: 'cors',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': Token ,
          },
          body: JSON.stringify({
            query: value,
            count: 5,
            from_bound: { value: 'city' },
            to_bound: { value: 'house' },
          }),
        });

        if (!response.ok) {
          throw new Error(HTTP );
        }

        const data = await response.json();
        console.log('[AddressAutocomplete] Response:', data);
        setSuggestions(data.suggestions || []);
        setShowSuggestions(true);
      } catch (error) {
        console.error('[AddressAutocomplete] Error:', error);
        setSuggestions([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [value, DADATA_TOKEN]);

  const handleSelect = (suggestion: AddressSuggestion) => {
    onChange(suggestion.unrestricted_value);
    setShowSuggestions(false);
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
        onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
        placeholder={placeholder}
        className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
      />

      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded shadow-lg max-h-60 overflow-y-auto">
          {suggestions.map((suggestion, index) => (
            <div
              key={index}
              onClick={() => handleSelect(suggestion)}
              className="px-3 py-2 cursor-pointer hover:bg-blue-50 border-b border-gray-100 last:border-b-0"
            >
              <div className="text-sm font-medium text-gray-900">
                {suggestion.value}
              </div>
              {suggestion.data.region_with_type && (
                <div className="text-xs text-gray-500">
                  {suggestion.data.region_with_type}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {isLoading && (
        <div className="absolute right-2 top-2">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
        </div>
      )}
    </div>
  );
};

export default AddressAutocomplete;
