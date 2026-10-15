import React from 'react';

const EMAIL_REGEX = /^[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}$/;

interface EmailInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  className?: string;
  showError?: boolean;
}

export const isValidEmail = (email: string): boolean => {
  if (!email) return true; // пустой = валидный (опциональное поле)
  return EMAIL_REGEX.test(email.toLowerCase());
};

export const EmailInput: React.FC<EmailInputProps> = ({
  value, onChange, placeholder = 'name@example.com', label, disabled, className = '', showError = true,
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toLowerCase().replace(/[^a-z0-9@._-]/g, '');
    onChange(val);
  };

  const isInvalid = value.length > 0 && !isValidEmail(value);

  return (
    <div>
      {label && <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>}
      <input
        type="email"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        className={`w-full px-3 py-2 border rounded text-sm focus:ring-2 focus:ring-blue-500 outline-none ${
          isInvalid && showError ? 'border-red-400 bg-red-50' : 'border-gray-300'
        } ${className}`}
      />
      {isInvalid && showError && (
        <p className="text-xs text-red-500 mt-1">Формат: name@domain.xx (латиница)</p>
      )}
    </div>
  );
};