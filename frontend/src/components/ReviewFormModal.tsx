import React, { useState } from 'react';
import { apiClient } from '../api/client';
import { showToast } from '../utils/toast';

interface Props {
  companyId: number;
  companyName: string;
  contractorId?: number;
  onClose: () => void;
  onSuccess: () => void;
}

export const ReviewFormModal: React.FC<Props> = ({
  companyId,
  companyName,
  contractorId,
  onClose,
  onSuccess,
}) => {
  const [rating, setRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [reviewerName, setReviewerName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (comment.trim().length < 10) {
      showToast.error('Комментарий должен содержать минимум 10 символов');
      return;
    }

    try {
      setLoading(true);
      await apiClient.post(`/public/companies/${companyId}/marketplace-reviews`, {
        rating,
        comment: comment.trim(),
        reviewer_name: reviewerName || undefined,
        reviewer_contractor_id: contractorId || undefined,
      });
      showToast.success('Отзыв успешно опубликован!');
      onSuccess();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      showToast.error('Ошибка: ' + (detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const ratingLabels = ['', 'Ужасно', 'Плохо', 'Нормально', 'Хорошо', 'Отлично'];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Заголовок */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900">
            ⭐ Оставить отзыв о {companyName}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl"
            disabled={loading}
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Рейтинг звёздами */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Оценка
            </label>
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoverRating(star)}
                  onMouseLeave={() => setHoverRating(0)}
                  className="text-4xl transition-transform hover:scale-110 focus:outline-none"
                  disabled={loading}
                >
                  <span
                    className={
                      star <= (hoverRating || rating)
                        ? 'text-yellow-400'
                        : 'text-gray-300'
                    }
                  >
                    ★
                  </span>
                </button>
              ))}
              <span className="ml-4 text-lg font-semibold text-gray-900">
                {ratingLabels[hoverRating || rating]}
              </span>
            </div>
          </div>

          {/* Имя (для анонимных) */}
          {!contractorId && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ваше имя (необязательно)
              </label>
              <input
                type="text"
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                placeholder="Аноним"
                maxLength={255}
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Комментарий */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Ваш отзыв <span className="text-red-500">*</span>
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Расскажите о вашем опыте работы с компанией..."
              rows={6}
              maxLength={2000}
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>
                {comment.length < 10
                  ? `Минимум 10 символов (ещё ${10 - comment.length})`
                  : '✓'}
              </span>
              <span>{comment.length}/2000</span>
            </div>
          </div>
        </div>

        {/* Футер */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || comment.trim().length < 10}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 font-semibold"
          >
            {loading ? 'Отправка...' : 'Опубликовать отзыв'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReviewFormModal;