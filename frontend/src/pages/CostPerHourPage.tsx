import React, { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const CostPerHourPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));
  const [showRates, setShowRates] = useState(false);
  const [ratesForm, setRatesForm] = useState({ fuel_price_per_liter: 65, hourly_wage: 500, amortization_per_hour: 300 });
  const [forecast, setForecast] = useState<any>(null);

  useEffect(() => {
    setLoading(true);
    apiClient.get('/shifts/stats/cost-per-hour', { params: { date_from: dateFrom, date_to: dateTo } })
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  useEffect(() => {
    apiClient.get('/shifts/cost-rates').then(res => setRatesForm(res.data)).catch(() => {});
    apiClient.get('/shifts/stats/cost-forecast').then(res => setForecast(res.data)).catch(() => {});
  }, []);

  const saveRates = async () => {
    try {
      await apiClient.put('/shifts/cost-rates', ratesForm);
      alert('✅ Ставки сохранены');
      setShowRates(false);
      // Reload data
      apiClient.get('/shifts/stats/cost-per-hour', { params: { date_from: dateFrom, date_to: dateTo } })
        .then(res => setData(res.data)).catch(() => {});
      apiClient.get('/shifts/stats/cost-forecast').then(res => setForecast(res.data)).catch(() => {});
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
  };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold text-gray-900">💰 Себестоимость моточаса</h1>
          <div className="flex gap-3 items-center">
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            <span className="text-gray-400">—</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            <button onClick={() => window.open(`/api/v1/shifts/stats/cost-per-hour/export?date_from=${dateFrom}&date_to=${dateTo}`, '_blank')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium">📥 Excel</button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div></div>
        ) : data ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
                <p className="text-sm text-gray-500">Общая стоимость</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.total_cost.toLocaleString('ru-RU')} ₽</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-purple-500">
                <p className="text-sm text-gray-500">Всего часов</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.total_hours}ч</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-orange-500">
                <p className="text-sm text-gray-500">Ср. ₽/час</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.avg_cost_per_hour} ₽</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
                <p className="text-sm text-gray-500">Техники</p>
                <p className="text-2xl font-bold text-gray-900">{data.summary.vehicles_count}</p>
              </div>
            </div>

            <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 flex gap-4 flex-wrap">
              <span>⛽ Топливо: {data.rates.fuel_price} ₽/л</span>
              <span>👤 Зарплата: {data.rates.hourly_wage} ₽/ч</span>
              <span>🔧 Амортизация: {data.rates.amortization} ₽/ч</span>
            </div>

            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Техника</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Водитель</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Часов</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Топливо</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Зарплата</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Амортизация</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Итого</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">₽/час</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {data.vehicles.filter((v: any) => v.hours > 0).map((v: any) => (
                    <tr key={v.vehicle_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{v.vehicle_name}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{v.driver_name || '—'}</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{v.hours}</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{v.fuel_cost.toLocaleString('ru-RU')} ₽</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{v.wage_cost.toLocaleString('ru-RU')} ₽</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-600">{v.amortization_cost.toLocaleString('ru-RU')} ₽</td>
                      <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">{v.total_cost.toLocaleString('ru-RU')} ₽</td>
                      <td className="px-4 py-3 text-sm text-right font-bold text-orange-600">{v.cost_per_hour} ₽</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : <p className="text-gray-400 text-center py-8">Нет данных</p>}

        {/* Rates Editor */}
        <div className="bg-white rounded-xl shadow-sm border p-5">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-lg font-bold text-gray-900">⚙️ Ставки себестоимости</h2>
            <button onClick={() => setShowRates(!showRates)} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
              {showRates ? '✕ Закрыть' : '✏️ Редактировать'}
            </button>
          </div>
          {showRates ? (
            <div className="grid grid-cols-3 gap-4">
              <label className="block"><span className="text-xs text-gray-500">Топливо (₽/литр)</span>
                <input type="number" step="0.5" value={ratesForm.fuel_price_per_liter} onChange={e => setRatesForm({...ratesForm, fuel_price_per_liter: parseFloat(e.target.value)})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
              <label className="block"><span className="text-xs text-gray-500">Зарплата (₽/час)</span>
                <input type="number" step="10" value={ratesForm.hourly_wage} onChange={e => setRatesForm({...ratesForm, hourly_wage: parseFloat(e.target.value)})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
              <label className="block"><span className="text-xs text-gray-500">Амортизация (₽/час)</span>
                <input type="number" step="10" value={ratesForm.amortization_per_hour} onChange={e => setRatesForm({...ratesForm, amortization_per_hour: parseFloat(e.target.value)})}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
              <div className="col-span-3"><button onClick={saveRates} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium">💾 Сохранить ставки</button></div>
            </div>
          ) : (
            <div className="flex gap-6 text-sm text-gray-600">
              <span>⛽ {ratesForm.fuel_price_per_liter} ₽/л</span>
              <span>👤 {ratesForm.hourly_wage} ₽/ч</span>
              <span>🔧 {ratesForm.amortization_per_hour} ₽/ч</span>
            </div>
          )}
        </div>

        {/* Forecast */}
        {forecast && (
          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl border p-5 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">📈 Прогноз на {new Date(forecast.period.forecast_from).toLocaleDateString('ru-RU', {month:'long'})}</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg p-3 shadow-sm">
                <p className="text-xs text-gray-500">Прогноз расходов</p>
                <p className="text-xl font-bold text-indigo-700">{forecast.forecast.total_cost.toLocaleString('ru-RU')} ₽</p>
                <p className={`text-xs ${forecast.forecast.change_pct > 0 ? 'text-red-500' : 'text-green-500'}`}>
                  {forecast.forecast.change_pct > 0 ? '↑' : '↓'} {Math.abs(forecast.forecast.change_pct)}% vs факт
                </p>
              </div>
              <div className="bg-white rounded-lg p-3 shadow-sm">
                <p className="text-xs text-gray-500">Топливо</p>
                <p className="text-lg font-bold text-orange-600">{forecast.forecast.fuel_liters} л</p>
                <p className="text-xs text-gray-400">{forecast.forecast.fuel_cost.toLocaleString('ru-RU')} ₽</p>
              </div>
              <div className="bg-white rounded-lg p-3 shadow-sm">
                <p className="text-xs text-gray-500">Зарплата</p>
                <p className="text-lg font-bold text-blue-600">{forecast.forecast.wage_cost.toLocaleString('ru-RU')} ₽</p>
              </div>
              <div className="bg-white rounded-lg p-3 shadow-sm">
                <p className="text-xs text-gray-500">Амортизация</p>
                <p className="text-lg font-bold text-purple-600">{forecast.forecast.amortization_cost.toLocaleString('ru-RU')} ₽</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default CostPerHourPage;
