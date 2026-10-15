import React from 'react';

interface PhoneInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  className?: string;
}

export const PhoneInput: React.FC<PhoneInputProps> = ({
  value, onChange, placeholder = '+79991234567', label, disabled, className = '',
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let digits = e.target.value.replace(/\D/g, '');
    if (digits.startsWith('8')) digits = '7' + digits.slice(1);
    if (digits.startsWith('7')) digits = digits.slice(0, 11);
    else if (digits.length > 0 && !digits.startsWith('7')) digits = '7' + digits.slice(0, 10);
    const formatted = digits.length > 0 ? '+' + digits : '';
    onChange(formatted);
  };

  return (
    <div>
      {label && <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>}
      <input
        type="tel"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        maxLength={12}
        disabled={disabled}
        className={`w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none ${className}`}
      />
    </div>
  );
};