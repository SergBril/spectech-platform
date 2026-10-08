import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import apiClient from '../api/client';

interface Company {
  id: number;
  name: string;
  legal_name?: string;
  description: string | null;
  city: string | null;
  phone: string | null;
  email?: string | null;
  website: string | null;
  logo_url?: string | null;
  rating: number | null;
  total_reviews?: number;
  total_deals?: number;
  vehicles_count: number;
  is_verified: boolean;
  created_at: string;
}

interface Vehicle {
  id: number;
  name: string;
  category_name: string;
  year: number;
  status: string;
  hourly_rate: number | null;
  shift_rate: number | null;
  is_available_for_rent: boolean;
}

interface Review {
  id: number;
  rating: number;
  comment: string;
  reviewer_contractor_name?: string;
  reviewer_name?: string;
  created_at: string;
}

export const CompanyProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [company, setCompany] = useState<Company | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'vehicles' | 'reviews'>('vehicles');

  useEffect(() => {
    fetchCompanyData();
  }, [id]);

  const fetchCompanyData = async () => {
    try {
      // Параллельно загружаем все данные
      const [companyRes, ratingRes, vehiclesRes, reviewsRes] = await Promise.allSettled([
        apiClient.get(`/public/companies/${id}`),
        apiClient.get(`/public/companies/${id}/rating`),
        apiClient.get(`/public/companies/${id}/vehicles`),
        apiClient.get(`/public/companies/${id}/reviews?limit=20`),
      ]);

      // Основная информация о компании
      if (companyRes.status === 'fulfilled') {
        setCompany(companyRes.value.data);
      }

      // Рейтинг (дополняет company)
      if (ratingRes.status === 'fulfilled') {
        const ratingData = ratingRes.value.data;
        setCompany((prev) =>
          prev
            ? {
                ...prev,
                rating: ratingData.average_rating ?? prev.rating,
                total_reviews: ratingData.total_reviews ?? prev.total_reviews ?? 0,
              }
            : null
        );
      }

      // Техника компании
      if (vehiclesRes.status === 'fulfilled') {
        const data = vehiclesRes.value.data;
        setVehicles(Array.isArray(data) ? data : []);
      }

      // Отзывы
      if (reviewsRes.status === 'fulfilled') {
        const data = reviewsRes.value.data;
        setReviews(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('Error fetching company data:', error);
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
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>
        {labels[status] || status}
      </span>
    );
  };

  const renderStars = (rating: number) => (
    <div className="flex">
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          className={`text-lg ${star <= Math.round(rating) ? 'text-yellow-400' : 'text-gray-300'}`}
        >
          ★
        </span>
      ))}
    </div>
  );

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  if (!company) {
    return (
      <Layout>
        <div className="max-w-7xl mx-auto px-4 py-8 text-center">
          <p className="text-gray-500 text-lg">Компания не найдена</p>
          <button
            onClick={() => navigate('/marketplace')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            ← Вернуться на маркетплейс
          </button>
        </div>
      </Layout>
    );
  }

  const rating = company.rating ?? 0;
  const totalReviews = company.total_reviews ?? reviews.length;

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

        {/* Шапка компании */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Левая часть: название и описание */}
            <div className="lg:col-span-2">
              <div className="flex items-start space-x-3 mb-4">
                <span className="text-5xl">🏢</span>
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-1 flex-wrap">
                    <h1 className="text-3xl font-bold text-gray-900">{company.name}</h1>
                    {company.is_verified && (
                      <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                        ✓ Проверено
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-4 text-sm flex-wrap gap-y-2">
                    <div className="flex items-center space-x-1">
                      <span className="text-yellow-500 text-lg">⭐</span>
                      <span className="font-bold text-lg text-gray-900">
                        {rating > 0 ? rating.toFixed(1) : '—'}
                      </span>
                      <span className="text-gray-500">
                        ({totalReviews} {totalReviews === 1 ? 'отзыв' : totalReviews < 5 ? 'отзыва' : 'отзывов'})
                      </span>
                    </div>
                    {company.city && (
                      <div className="flex items-center text-gray-600">
                        <span className="mr-1">📍</span>
                        {company.city}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {company.description && (
                <p className="text-gray-700 leading-relaxed">{company.description}</p>
              )}
            </div>

            {/* Правая часть: контакты */}
            <div className="border-t lg:border-t-0 lg:border-l lg:pl-6 pt-6 lg:pt-0">
              <h3 className="text-sm font-semibold text-gray-900 mb-3 uppercase">
                Контакты
              </h3>
              <div className="space-y-2">
                {company.phone && (
                  <a
                    href={`tel:${company.phone}`}
                    className="flex items-center text-gray-700 hover:text-blue-600"
                  >
                    <span className="mr-2">📞</span>
                    {company.phone}
                  </a>
                )}
                {company.email && (
                  <a
                    href={`mailto:${company.email}`}
                    className="flex items-center text-gray-700 hover:text-blue-600"
                  >
                    <span className="mr-2">📧</span>
                    {company.email}
                  </a>
                )}
                {company.website && (
                  <a
                    href={company.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center text-gray-700 hover:text-blue-600"
                  >
                    <span className="mr-2">🌐</span>
                    {company.website.replace(/^https?:\/\//, '')}
                  </a>
                )}
              </div>

              <button
                onClick={() => {
                  setActiveTab('vehicles');
                  window.scrollTo({ top: 400, behavior: 'smooth' });
                }}
                className="mt-4 w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 font-medium text-sm"
              >
                🚜 Посмотреть технику ({vehicles.length})
              </button>
            </div>
          </div>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
            <div className="text-3xl font-bold text-blue-600 mb-1">
              {vehicles.length}
            </div>
            <div className="text-sm text-gray-600">Единиц техники</div>
          </div>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
            <div className="text-3xl font-bold text-green-600 mb-1">
              {rating > 0 ? rating.toFixed(1) : '—'}
            </div>
            <div className="text-sm text-gray-600">Средний рейтинг</div>
          </div>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
            <div className="text-3xl font-bold text-yellow-600 mb-1">
              {totalReviews}
            </div>
            <div className="text-sm text-gray-600">Отзывов</div>
          </div>
        </div>

        {/* Табы */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('vehicles')}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'vehicles'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              🚜 Техника ({vehicles.length})
            </button>
            <button
              onClick={() => setActiveTab('reviews')}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'reviews'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              ⭐ Отзывы ({totalReviews})
            </button>
          </nav>
        </div>

        {/* Контент табов */}
        {activeTab === 'vehicles' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {vehicles.map((vehicle) => (
              <div
                key={vehicle.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/marketplace/${vehicle.id}`)}
              >
                <div className="h-48 bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center">
                  <span className="text-6xl">🚜</span>
                </div>
                <div className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-lg font-semibold text-gray-900 flex-1 mr-2">
                      {vehicle.name}
                    </h3>
                    {getStatusBadge(vehicle.status)}
                  </div>
                  <p className="text-sm text-gray-600 mb-3">
                    {vehicle.category_name} • {vehicle.year} год
                  </p>
                  <div className="border-t border-gray-200 pt-3">
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <p className="text-gray-500 text-xs">Почасовая:</p>
                        <p className="font-semibold text-gray-900">
                          {vehicle.hourly_rate ? `${vehicle.hourly_rate} ₽/час` : '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500 text-xs">Посменная:</p>
                        <p className="font-semibold text-gray-900">
                          {vehicle.shift_rate ? `${vehicle.shift_rate} ₽/смена` : '—'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {vehicles.length === 0 && (
              <div className="col-span-full text-center py-12">
                <p className="text-gray-500">У компании пока нет техники на маркетплейсе</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'reviews' && (
          <div className="space-y-4">
            {reviews.map((review) => (
              <div
                key={review.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold">
                      {(review.reviewer_contractor_name || review.reviewer_name || 'К')[0].toUpperCase()}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">
                        {review.reviewer_contractor_name || review.reviewer_name || 'Клиент'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(review.created_at).toLocaleDateString('ru-RU', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </div>
                    </div>
                  </div>
                  {renderStars(review.rating)}
                </div>
                <p className="text-gray-700">{review.comment}</p>
              </div>
            ))}
            {reviews.length === 0 && (
              <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
                <p className="text-gray-500 text-lg">Пока нет отзывов</p>
                <p className="text-sm text-gray-400 mt-2">Будьте первым, кто оставит отзыв о компании</p>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default CompanyProfilePage;