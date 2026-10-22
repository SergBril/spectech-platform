import React, { useState } from 'react';
import Layout from '../components/Layout';
import apiClient from '../api/client';

const OnboardingWizardPage: React.FC = () => {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ company_name: '', inn: '', address: '', contact_phone: '', fuel_price: 65, hourly_wage: 500, amortization: 300 });
  const [saving, setSaving] = useState(false);

  const steps = [
    { num: 1, title: 'Компания', icon: '🏢' },
    { num: 2, title: 'Ставки', icon: '💰' },
    { num: 3, title: 'Готово', icon: '✅' },
  ];

  const saveOnboarding = async () => {
    setSaving(true);
    try {
      // Save cost rates
      await apiClient.put('/shifts/cost-rates', {
        fuel_price_per_liter: form.fuel_price,
        hourly_wage: form.hourly_wage,
        amortization_per_hour: form.amortization,
      });
      alert('✅ Настройки сохранены! Добро пожаловать в Spectech.');
      window.location.href = '/overview';
    } catch (err: any) { alert('Ошибка: ' + (err.response?.data?.detail || '')); }
    finally { setSaving(false); }
  };

  return (
    <Layout>
      <div className="p-6 max-w-2xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 text-center">🚀 Настройка платформы</h1>

        {/* Progress */}
        <div className="flex justify-between items-center">
          {steps.map(s => (
            <div key={s.num} className={`flex items-center gap-2 ${step >= s.num ? 'text-indigo-600' : 'text-gray-300'}`}>
              <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${step >= s.num ? 'bg-indigo-600 text-white' : 'bg-gray-200'}`}>{s.icon}</span>
              <span className="text-sm font-medium hidden sm:inline">{s.title}</span>
            </div>
          ))}
        </div>

        {/* Step 1: Company Info */}
        {step === 1 && (
          <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
            <h2 className="text-lg font-bold">🏢 Информация о компании</h2>
            <label className="block"><span className="text-xs text-gray-500">Название компании</span>
              <input value={form.company_name} onChange={e => setForm({...form, company_name: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="ООО Спецтехника" /></label>
            <label className="block"><span className="text-xs text-gray-500">ИНН</span>
              <input value={form.inn} onChange={e => setForm({...form, inn: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="7700000000" /></label>
            <label className="block"><span className="text-xs text-gray-500">Адрес</span>
              <input value={form.address} onChange={e => setForm({...form, address: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <label className="block"><span className="text-xs text-gray-500">Контактный телефон</span>
              <input value={form.contact_phone} onChange={e => setForm({...form, contact_phone: e.target.value})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <button onClick={() => setStep(2)} disabled={!form.company_name} className="w-full py-3 bg-indigo-600 text-white rounded-xl font-bold disabled:opacity-50">Далее →</button>
          </div>
        )}

        {/* Step 2: Cost Rates */}
        {step === 2 && (
          <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
            <h2 className="text-lg font-bold">💰 Ставки себестоимости</h2>
            <p className="text-sm text-gray-500">Эти значения используются для расчёта маржинальности</p>
            <label className="block"><span className="text-xs text-gray-500">⛽ Стоимость топлива (₽/литр)</span>
              <input type="number" step="0.5" value={form.fuel_price} onChange={e => setForm({...form, fuel_price: parseFloat(e.target.value)})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <label className="block"><span className="text-xs text-gray-500">👤 Зарплата водителя (₽/час)</span>
              <input type="number" step="10" value={form.hourly_wage} onChange={e => setForm({...form, hourly_wage: parseFloat(e.target.value)})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <label className="block"><span className="text-xs text-gray-500">🔧 Амортизация техники (₽/час)</span>
              <input type="number" step="10" value={form.amortization} onChange={e => setForm({...form, amortization: parseFloat(e.target.value)})} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" /></label>
            <div className="flex gap-3">
              <button onClick={() => setStep(1)} className="flex-1 py-3 border rounded-xl font-medium text-gray-600">← Назад</button>
              <button onClick={() => setStep(3)} className="flex-1 py-3 bg-indigo-600 text-white rounded-xl font-bold">Далее →</button>
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {step === 3 && (
          <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4 text-center">
            <div className="text-4xl mb-2">🎉</div>
            <h2 className="text-lg font-bold">Всё готово!</h2>
            <p className="text-sm text-gray-500">Проверьте настройки и завершите настройку</p>
            <div className="bg-gray-50 rounded-lg p-4 text-left text-sm space-y-1">
              <p><strong>Компания:</strong> {form.company_name}</p>
              <p><strong>Топливо:</strong> {form.fuel_price} ₽/л</p>
              <p><strong>Зарплата:</strong> {form.hourly_wage} ₽/ч</p>
              <p><strong>Амортизация:</strong> {form.amortization} ₽/ч</p>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setStep(2)} className="flex-1 py-3 border rounded-xl font-medium text-gray-600">← Назад</button>
              <button onClick={saveOnboarding} disabled={saving} className="flex-1 py-3 bg-green-600 text-white rounded-xl font-bold disabled:opacity-50">
                {saving ? '⏳ Сохранение...' : '✅ Завершить настройку'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default OnboardingWizardPage;
