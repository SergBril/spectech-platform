import React, { useEffect, useState } from 'react';
import { filesApi, type UploadedFile } from '../api/files';
import { showToast } from '../utils/toast';

interface FileListProps {
  fileCategory?: string;
  actId?: number;
  invoiceId?: number;
  vehicleId?: number;
  refreshTrigger?: number; // увеличивайте, чтобы обновить список
}

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const getFileIcon = (contentType: string): string => {
  if (contentType.includes('pdf')) return '📄';
  if (contentType.includes('image')) return '🖼️';
  if (contentType.includes('word') || contentType.includes('document')) return '📝';
  if (contentType.includes('excel') || contentType.includes('sheet')) return '📊';
  return '📎';
};

export const FileList: React.FC<FileListProps> = ({
  fileCategory,
  actId,
  invoiceId,
  vehicleId,
  refreshTrigger = 0,
}) => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadFiles();
  }, [fileCategory, actId, invoiceId, vehicleId, refreshTrigger]);

  const loadFiles = async () => {
    try {
      setLoading(true);
      const result = await filesApi.list({
        file_category: fileCategory,
        act_id: actId,
        invoice_id: invoiceId,
        vehicle_id: vehicleId,
        limit: 50,
      });
      setFiles(result);
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (file: UploadedFile) => {
    try {
      await filesApi.download(file.id, file.original_filename);
    } catch (error: any) {
      showToast.error('Ошибка скачивания: ' + (error?.response?.data?.detail || error.message));
    }
  };

  const handleDelete = async (file: UploadedFile) => {
    if (!window.confirm(`Удалить файл "${file.original_filename}"?`)) return;

    try {
      await filesApi.delete(file.id);
      showToast.success('Файл удалён');
      loadFiles();
    } catch (error: any) {
      showToast.error('Ошибка удаления: ' + (error?.response?.data?.detail || error.message));
    }
  };

  if (loading) {
    return (
      <div className="text-center py-4 text-gray-500">
        <div className="animate-pulse">Загрузка файлов...</div>
      </div>
    );
  }

  if (files.length === 0) {
    return null; // Не показываем блок, если файлов нет
  }

  return (
    <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
        <h4 className="text-sm font-semibold text-gray-700">
          📁 Прикреплённые файлы ({files.length})
        </h4>
      </div>
      <ul className="divide-y divide-gray-200">
        {files.map((file) => (
          <li
            key={file.id}
            className="px-4 py-3 hover:bg-gray-50 transition-colors flex items-center justify-between gap-3"
          >
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <span className="text-2xl flex-shrink-0">{getFileIcon(file.content_type)}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {file.original_filename}
                </p>
                <p className="text-xs text-gray-500">
                  {formatSize(file.size_bytes)} •{' '}
                  {new Date(file.created_at).toLocaleDateString('ru-RU')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => handleDownload(file)}
                className="p-2 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                title="Скачать"
              >
                ⬇️
              </button>
              <button
                onClick={() => handleDelete(file)}
                className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
                title="Удалить"
              >
                🗑️
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};
