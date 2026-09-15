import React, { useRef, useState } from 'react';
import { filesApi, type FileUploadResponse } from '../api/files';
import { showToast } from '../utils/toast';

interface FileUploadButtonProps {
  fileCategory: string;
  options?: {
    vehicle_id?: number;
    invoice_id?: number;
    act_id?: number;
    contractor_id?: number;
  };
  accept?: string; // например, ".pdf,.jpg,.png"
  onUploadSuccess?: (file: FileUploadResponse) => void;
  label?: string;
  icon?: string;
  className?: string;
}

export const FileUploadButton: React.FC<FileUploadButtonProps> = ({
  fileCategory,
  options,
  accept = '*/*',
  onUploadSuccess,
  label = 'Загрузить файл',
  icon = '📎',
  className = '',
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Проверка размера (макс 50 МБ)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      showToast.error('Файл слишком большой (макс. 50 МБ)');
      return;
    }

    setUploading(true);
    setProgress(0);

    try {
      const result = await filesApi.upload(file, fileCategory, options, (percent) => {
        setProgress(percent);
      });

      showToast.success(`✅ Файл "${file.name}" успешно загружен`);
      onUploadSuccess?.(result);
    } catch (error: any) {
      console.error('Upload error:', error);
      showToast.error('Ошибка загрузки: ' + (error?.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
      setProgress(0);
      // Сбрасываем input, чтобы можно было загрузить тот же файл снова
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="inline-block">
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={handleFileChange}
        className="hidden"
        disabled={uploading}
      />

      <button
        onClick={handleClick}
        disabled={uploading}
        className={`
          relative overflow-hidden px-4 py-2 text-sm font-medium rounded
          transition-all duration-200
          ${uploading
            ? 'bg-gray-400 text-white cursor-not-allowed'
            : 'bg-indigo-600 text-white hover:bg-indigo-700 active:scale-95'
          }
          ${className}
        `}
      >
        {/* Прогресс-бар внутри кнопки */}
        {uploading && (
          <div
            className="absolute left-0 top-0 h-full bg-indigo-400 opacity-50 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        )}

        <span className="relative z-10 flex items-center gap-2">
          {uploading ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>{progress}%</span>
            </>
          ) : (
            <>
              <span>{icon}</span>
              <span>{label}</span>
            </>
          )}
        </span>
      </button>
    </div>
  );
};
