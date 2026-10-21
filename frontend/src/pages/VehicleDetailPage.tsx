import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { RequestFormModal } from '../components/RequestFormModal';
import apiClient from '../api/client';

interface Vehicle {
  id: number;
  name: string;
  category_name: string;
  year: number;
  status: string;
  hourly_rate: number | null;
  shift_rate: number | null;
  is_available_for_rent: boolean;
  owner_company_id: number;
  owner_company_name: string;
  description?: string;
  photos: string[] | null;
  marketplace_commission_agreed?: boolean;
  marketplace_commission_rate?: number;
}

interface Company {
  id: number;
  name: string;
  description: string | null;
  city: string | null;
  phone: string | null;
  average_rating: number | null;
  total_reviews: number;
}

interface Review {
  id: number;
  rating: number;
  comment: string;
  reviewer_contractor_name?: string;
  reviewer_name?: string;
  created_at: string;
}

export const VehicleDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [availability, setAvailability] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [showRequestForm, setShowRequestForm] = useState(false);

  useEffect(() => {
    fetchVehicle();
  }, [id]);

  const fetchVehicle = async () => {
    try {
      const response = await apiClient.get(`/public/vehicles/${id}`);
      setVehicle(response.data);

      // Загружаем информацию о компании
      if (response.data.owner_company_id) {
        try {
          const companyRes = await apiClient.get(
            `/public/companies/${response.data.owner_company_id}/rating`
          );
          setCompany(companyRes.data);
        } catch (e) {
          console.warn('Failed to load company rating:', e);
        }

        // 🆕 Загружаем отзывы о компании
        try {
          const reviewsRes = await apiClient.get(
            `/public/companies/${response.data.owner_company_id}/reviews?limit=5`
          );
          const reviewsData = reviewsRes.data;
          setReviews(
            Array.isArray(reviewsData) ? reviewsData : reviewsData?.items || []
          );
        } catch (e) {
          console.warn('Failed to load reviews:', e);
        }
      }

      // 🆕 Загружаем календарь доступности
      try {
        const availRes = await apiClient.get(
          `/public/vehicles/${response.data.id}/availability?months=2`
        );
        if (availRes.data && typeof availRes.data === 'object') {
          setAvailability(availRes.data);
        }
      } catch (e) {
        console.warn('Failed to load availability:', e);
      }
    } catch (error) {
      console.error('Error fetching vehicle:', error);
      navigate('/marketplace');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      free: 'bg-green-100 text-green-800',
      busy: 'bg-red-100 text-red-800',
      maintenance: 'bg-yellow-100 text-yellow-800',
    };
    const labels: Record<string, string> = {
      free: 'Свободна',
      busy: 'Занята',
      maintenance: 'На ТО',
    };
    return (
      <span
        className={`px-3 py-1 rounded-full text-sm font-medium ${
          colors[status] || 'bg-gray-100'
        }`}
      >
        {labels[status] || status}
      </span>
    );
  };

  // 🆕 Генерация дней для календаря (2 месяца вперёд)
  const generateCalendarDays = () => {
    const days: Array<{
      dayNumber: number | string;
      date: string;
      isCurrentMonth: boolean;
    }> = [];
    const today = new Date();

    for (let monthOffset = 0; monthOffset < 2; monthOffset++) {
      const month = new Date(today.getFullYear(), today.getMonth() + monthOffset, 1);
      const daysInMonth = new Date(
        month.getFullYear(),
        month.getMonth() + 1,
        0
      ).getDate();
      const firstDayOfWeek = (month.getDay() + 6) % 7; // Понедельник = 0

      // Пустые ячейки до начала месяца
      for (let i = 0; i < firstDayOfWeek; i++) {
        days.push({ dayNumber: '', date: '', isCurrentMonth: false });
      }

      // Дни месяца
      for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        days.push({ dayNumber: day, date: dateStr, isCurrentMonth: true });
      }
    }

    return days;
  };

  // 🆕 Обработчик сохранения заявки
  const handleSaveRequest = async (data: any) => {
    try {
      await apiClient.post('/requests', data);
      setShowRequestForm(false);
      alert(
        '✅ Заявка успешно создана! Владелец свяжется с вами в ближайшее время.'
      );
      navigate('/requests');
    } catch (error: any) {
      console.error('Failed to create request:', error);
      const message =
        error.response?.data?.detail || 'Ошибка при создании заявки';
      alert(`❌ ${message}`);
      throw error;
    }
  };

  // Состояние загрузки
  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  // Техника не найдена
  if (!vehicle) {
    return (
      <Layout>
        <div className="max-w-7xl mx-auto px-4 py-8">
          <p className="text-center text-gray-500">Техника не найдена</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Хлебные крошки */}
        <nav className="mb-6">
          <button
            onClick={() => navigate('/marketplace')}
            className="text-blue-600 hover:text-blue-700 text-sm"
          >
            ← Назад к маркетплейсу
          </button>
        </nav>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Левая колонка: фото и описание */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              {/* Фото */}
              <div className="h-96 bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center">
                {vehicle.photos && vehicle.photos.length > 0 ? (
                  <img
                    src={vehicle.photos[0]}
                    alt={vehicle.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-9xl">🚜</span>
                )}
              </div>

              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h1 className="text-3xl font-bold text-gray-900 mb-2">
                      {vehicle.name}
                    </h1>
                    <p className="text-gray-600">
                      {vehicle.category_name} • {vehicle.year} год
                    </p>

                    {/* Marketplace Commission Banner */}
                    {!vehicle.marketplace_commission_agreed ? (
                      <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
                        <span className="text-lg">⚠️</span>
                        <div>
                          <p className="text-sm font-semibold text-amber-900">Не участвует в маркетплейсе</p>
                          <p className="text-xs text-amber-800 mt-0.5">
                            Собственник не дал согласие на комиссию. Техника недоступна для заказов из маркетплейса.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-3 flex items-start gap-2">
                        <span className="text-lg">✅</span>
                        <div>
                          <p className="text-sm font-semibold text-green-900">Участвует в маркетплейсе</p>
                          <p className="text-xs text-green-800 mt-0.5">
                            Комиссия платформы: {vehicle.marketplace_commission_rate || 10}% от marketplace-заказов.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                  {getStatusBadge(vehicle.status)}
                </div>

                {vehicle.description && (
                  <div className="mb-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-2">
                      Описание
                    </h2>
                    <p className="text-gray-700">{vehicle.description}</p>
                  </div>
                )}

                {/* Стоимость аренды */}
                <div className="border-t border-gray-200 pt-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">
                    Стоимость аренды
                  </h2>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Почасовая</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {vehicle.hourly_rate
                          ? `${vehicle.hourly_rate} ₽/час`
                          : '—'}
                      </p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Посменная</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {vehicle.shift_rate
                          ? `${vehicle.shift_rate} ₽/смена`
                          : '—'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* 🆕 КАЛЕНДАРЬ ДОСТУПНОСТИ */}
                <div className="border-t border-gray-200 pt-6 mt-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">
                    📅 Доступность на ближайшие 2 месяца
                  </h2>
                  <div className="grid grid-cols-7 gap-1 text-xs">
                    {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => (
                      <div
                        key={day}
                        className="text-center font-medium text-gray-500 py-2"
                      >
                        {day}
                      </div>
                    ))}
                    {generateCalendarDays().map((day, idx) => {
                      if (!day.isCurrentMonth) {
                        return <div key={idx} className="py-2" />;
                      }
                      const isBusy = availability[day.date] === false;
                      return (
                        <div
                          key={idx}
                          className={`text-center py-2 rounded ${
                            isBusy
                              ? 'bg-red-100 text-red-700'
                              : 'bg-green-100 text-green-700'
                          }`}
                          title={`${day.date}: ${
                            isBusy ? 'Занято' : 'Свободно'
                          }`}
                        >
                          {day.dayNumber}
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex items-center space-x-4 mt-4 text-xs text-gray-600">
                    <div className="flex items-center space-x-1">
                      <div className="w-3 h-3 bg-green-100 rounded"></div>
                      <span>Свободно</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <div className="w-3 h-3 bg-red-100 rounded"></div>
                      <span>Занято</span>
                    </div>
                  </div>
                </div>

                {/* 🆕 ОТЗЫВЫ О КОМПАНИИ */}
                {reviews.length > 0 && (
                  <div className="border-t border-gray-200 pt-6 mt-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">
                      ⭐ Отзывы о компании ({reviews.length})
                    </h2>
                    <div className="space-y-4">
                      {reviews.slice(0, 3).map((review) => (
                        <div
                          key={review.id}
                          className="border-b border-gray-100 pb-4 last:border-0"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center space-x-2">
                              <span className="font-medium text-gray-900">
                                {review.reviewer_contractor_name ||
                                  review.reviewer_name ||
                                  'Клиент'}
                              </span>
                              <div className="flex">
                                {[1, 2, 3, 4, 5].map((star) => (
                                  <span
                                    key={star}
                                    className={
                                      star <= review.rating
                                        ? 'text-yellow-400'
                                        : 'text-gray-300'
                                    }
                                  >
                                    ★
                                  </span>
                                ))}
                              </div>
                            </div>
                            <span className="text-xs text-gray-500">
                              {new Date(review.created_at).toLocaleDateString(
                                'ru-RU'
                              )}
                            </span>
                          </div>
                          <p className="text-sm text-gray-700">
                            {review.comment}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {reviews.length === 0 && company && (
                  <div className="border-t border-gray-200 pt-6 mt-6 text-center">
                    <p className="text-gray-500 text-sm">
                      Пока нет отзывов об этой компании
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Правая колонка: информация о компании и кнопка заявки */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 sticky top-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Владелец
              </h2>

              <div className="mb-6">
                <button
                  onClick={() => navigate(`/companies/${vehicle.owner_company_id}`)}
                  className="text-xl font-bold text-blue-600 hover:text-blue-700 mb-2 text-left hover:underline"
                >
                  {vehicle.owner_company_name} →
                </button>
                {company && (
                  <div className="space-y-2">
                    {company.average_rating !== null && (
                      <div className="flex items-center space-x-2">
                        <span className="text-yellow-500">⭐</span>
                        <span className="font-medium">
                          {company.average_rating.toFixed(1)}
                        </span>
                        <span className="text-gray-500 text-sm">
                          ({company.total_reviews} отзывов)
                        </span>
                      </div>
                    )}
                    {company.city && (
                      <div className="flex items-center text-gray-600 text-sm">
                        <span className="mr-2">📍</span>
                        {company.city}
                      </div>
                    )}
                    {company.phone && (
                      <div className="flex items-center text-gray-600 text-sm">
                        <span className="mr-2">📞</span>
                        {company.phone}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {vehicle.is_available_for_rent ? (
                <button
                  onClick={() => setShowRequestForm(true)}
                  className="w-full bg-blue-600 text-white py-3 rounded-md hover:bg-blue-700 font-medium"
                >
                  Создать заявку
                </button>
              ) : (
                <button
                  disabled
                  className="w-full bg-gray-300 text-gray-500 py-3 rounded-md font-medium cursor-not-allowed"
                >
                  Техника недоступна
                </button>
              )}

              <p className="text-xs text-gray-500 mt-4 text-center">
                После создания заявки владелец свяжется с вами
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 🆕 Модальное окно заявки с правильными пропсами */}
      {showRequestForm && (
        <RequestFormModal
          request={null}
          onClose={() => setShowRequestForm(false)}
          onSave={handleSaveRequest}
          vehicleId={vehicle.id}
          vehicleName={vehicle.name}
        />
      )}
    </Layout>
  );
};

export default VehicleDetailPage;