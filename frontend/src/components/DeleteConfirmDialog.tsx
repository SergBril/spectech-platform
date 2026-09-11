import React from 'react';

interface Props {
  vehicleName: string;
  onConfirm: () => void;
  onCancel: () => void;
}

const DeleteConfirmDialog: React.FC<Props> = ({ vehicleName, onConfirm, onCancel }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          Удалить технику?
        </h2>
        <p className="text-gray-600 mb-6">
          Вы уверены, что хотите удалить <strong>"{vehicleName}"</strong>? Это действие нельзя отменить.
        </p>

        <div className="flex justify-end space-x-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50 transition"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition"
          >
            Удалить
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteConfirmDialog;
