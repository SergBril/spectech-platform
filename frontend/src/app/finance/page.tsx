"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getAccessToken } from "@/lib/api";

const API_URL = "http://localhost:8000/api/v1";

type Tab = "dashboard" | "invoices" | "acts" | "payouts";

interface Invoice {
  id: number;
  document_number: string;
  client_id: number;
  total: string;
  paid_amount: string;
  invoice_date: string;
  due_date: string | null;
  status: string;
  created_at: string;
}

interface Act {
  id: number;
  document_number: string;
  client_id: number;
  total_amount: string;
  act_date: string;
  status: string;
  signed_by_client_at: string | null;
  signed_by_executor_at: string | null;
  created_at: string;
}

interface Payout {
  id: number;
  document_number: string;
  owner_id: number;
  vehicle_id: number;
  gross_amount: string;
  platform_commission: string;
  net_amount: string;
  commission_rate: string;
  payout_date: string;
  status: string;
  created_at: string;
}

interface Dashboard {
  total_revenue: string;
  total_paid: string;
  total_outstanding: string;
  total_commission_earned: string;
  invoices_count: number;
  acts_count: number;
  payouts_count: number;
}

const statusConfig: Record<string, { label: string; color: string }> = {
  draft: { label: "Черновик", color: "bg-slate-100 text-slate-700" },
  sent: { label: "Отправлен", color: "bg-blue-100 text-blue-700" },
  paid: { label: "Оплачен", color: "bg-green-100 text-green-700" },
  partially_paid: { label: "Частично оплачен", color: "bg-yellow-100 text-yellow-700" },
  overdue: { label: "Просрочен", color: "bg-red-100 text-red-700" },
  cancelled: { label: "Отменён", color: "bg-slate-200 text-slate-500" },
};

export default function FinancePage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [mounted, setMounted] = useState(false);

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [acts, setActs] = useState<Act[]>([]);
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setMounted(true);
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }
    loadAll();
  }, [router]);

  async function loadAll() {
    setLoading(true);
    try {
      const [inv, act, pay, dash] = await Promise.all([
        apiFetch<Invoice[]>("/invoices"),
        apiFetch<Act[]>("/acts"),
        apiFetch<Payout[]>("/payouts"),
        apiFetch<Dashboard>("/payments/dashboard"),
      ]);
      setInvoices(inv);
      setActs(act);
      setPayouts(pay);
      setDashboard(dash);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function downloadPdf(url: string, filename: string) {
    const token = getAccessToken();
    const response = await fetch(`${API_URL}${url}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to download PDF");
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
  }

  async function sendInvoice(id: number) {
    if (!confirm("Отправить счёт клиенту?")) return;
    await apiFetch(`/invoices/${id}/send`, { method: "POST" });
    loadAll();
  }

  async function signAct(id: number, signedBy: "client" | "executor") {
    await apiFetch(`/acts/${id}/sign`, {
      method: "POST",
      body: JSON.stringify({ signed_by: signedBy }),
    });
    loadAll();
  }

  async function approvePayout(id: number) {
    if (!confirm("Одобрить выплату?")) return;
    await apiFetch(`/payouts/${id}/approve`, { method: "POST" });
    loadAll();
  }

  const tabs = [
    { id: "dashboard" as Tab, label: "📊 Дашборд" },
    { id: "invoices" as Tab, label: `📄 Счета (${invoices.length})` },
    { id: "acts" as Tab, label: `📋 Акты (${acts.length})` },
    { id: "payouts" as Tab, label: `💸 Выплаты (${payouts.length})` },
  ];

  const fmt = (n: string | number) => {
    const num = typeof n === "string" ? parseFloat(n) : n;
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: "RUB",
      minimumFractionDigits: 2,
    }).format(num);
  };

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Финансы</h1>
            <p className="text-sm text-slate-500 mt-1">
              Управление счетами, актами и выплатами
            </p>
          </div>
          <button
            onClick={() => router.push("/dashboard")}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
          >
            ← На дашборд
          </button>
        </div>

        {/* Tabs */}
        <div className="mb-6 border-b border-slate-200">
          <nav className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition ${
                  activeTab === tab.id
                    ? "bg-white text-blue-600 border-b-2 border-blue-600"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <p className="text-slate-500">Загрузка...</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            {/* === DASHBOARD === */}
            {activeTab === "dashboard" && dashboard && (
              <div>
                <h2 className="text-lg font-medium text-slate-900 mb-6">
                  Финансовая сводка
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                  <div className="rounded-xl border border-slate-200 p-5 bg-gradient-to-br from-blue-50 to-white">
                    <div className="text-xs text-slate-500 uppercase tracking-wide">
                      Общая выручка
                    </div>
                    <div className="text-2xl font-semibold text-slate-900 mt-2">
                      {fmt(dashboard.total_revenue)}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      {dashboard.invoices_count} счетов
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 p-5 bg-gradient-to-br from-green-50 to-white">
                    <div className="text-xs text-slate-500 uppercase tracking-wide">
                      Оплачено
                    </div>
                    <div className="text-2xl font-semibold text-green-700 mt-2">
                      {fmt(dashboard.total_paid)}
                    </div>
                    <div className="text-xs text-green-600 mt-1">
                      {dashboard.total_revenue !== "0"
                        ? `${(
                            (parseFloat(dashboard.total_paid) /
                              parseFloat(dashboard.total_revenue)) *
                            100
                          ).toFixed(1)}% от выручки`
                        : "—"}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 p-5 bg-gradient-to-br from-orange-50 to-white">
                    <div className="text-xs text-slate-500 uppercase tracking-wide">
                      Задолженность
                    </div>
                    <div className="text-2xl font-semibold text-orange-700 mt-2">
                      {fmt(dashboard.total_outstanding)}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Ожидает оплаты
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 p-5 bg-gradient-to-br from-purple-50 to-white">
                    <div className="text-xs text-slate-500 uppercase tracking-wide">
                      Комиссия платформы
                    </div>
                    <div className="text-2xl font-semibold text-purple-700 mt-2">
                      {fmt(dashboard.total_commission_earned)}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Заработано
                    </div>
                  </div>
                </div>

                <h3 className="text-md font-medium text-slate-900 mb-3">
                  Документы
                </h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="rounded-lg border border-slate-200 p-4 text-center">
                    <div className="text-3xl font-semibold text-blue-600">
                      {dashboard.invoices_count}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">Счетов</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 p-4 text-center">
                    <div className="text-3xl font-semibold text-green-600">
                      {dashboard.acts_count}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">Актов</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 p-4 text-center">
                    <div className="text-3xl font-semibold text-purple-600">
                      {dashboard.payouts_count}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">Выплат</div>
                  </div>
                </div>
              </div>
            )}

            {/* === INVOICES === */}
            {activeTab === "invoices" && (
              <div>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-medium text-slate-900">
                    Счета клиентам
                  </h2>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                      <th className="px-3 py-2">Номер</th>
                      <th className="px-3 py-2">Дата</th>
                      <th className="px-3 py-2">Срок</th>
                      <th className="px-3 py-2 text-right">Сумма</th>
                      <th className="px-3 py-2 text-right">Оплачено</th>
                      <th className="px-3 py-2">Статус</th>
                      <th className="px-3 py-2 text-right">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.length === 0 ? (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-3 py-8 text-center text-slate-400"
                        >
                          Нет счетов
                        </td>
                      </tr>
                    ) : (
                      invoices.map((inv) => {
                        const st = statusConfig[inv.status] || statusConfig.draft;
                        return (
                          <tr
                            key={inv.id}
                            className="border-b border-slate-100 hover:bg-slate-50"
                          >
                            <td className="px-3 py-3 font-mono text-xs">
                              {inv.document_number}
                            </td>
                            <td className="px-3 py-3 text-slate-600">
                              {new Date(inv.invoice_date).toLocaleDateString("ru-RU")}
                            </td>
                            <td className="px-3 py-3 text-slate-600">
                              {inv.due_date
                                ? new Date(inv.due_date).toLocaleDateString("ru-RU")
                                : "—"}
                            </td>
                            <td className="px-3 py-3 text-right font-medium">
                              {fmt(inv.total)}
                            </td>
                            <td className="px-3 py-3 text-right text-green-600">
                              {fmt(inv.paid_amount)}
                            </td>
                            <td className="px-3 py-3">
                              <span
                                className={`rounded-full px-2 py-0.5 text-xs ${st.color}`}
                              >
                                {st.label}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-right">
                              <div className="flex gap-1 justify-end">
                                <button
                                  onClick={() =>
                                    downloadPdf(
                                      `/invoices/${inv.id}/pdf`,
                                      `${inv.document_number}.pdf`
                                    )
                                  }
                                  className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
                                >
                                  📥 PDF
                                </button>
                                {inv.status === "draft" && (
                                  <button
                                    onClick={() => sendInvoice(inv.id)}
                                    className="rounded border border-blue-300 bg-blue-50 px-2 py-1 text-xs text-blue-700 hover:bg-blue-100"
                                  >
                                    📨 Отправить
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* === ACTS === */}
            {activeTab === "acts" && (
              <div>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-medium text-slate-900">
                    Акты выполненных работ
                  </h2>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                      <th className="px-3 py-2">Номер</th>
                      <th className="px-3 py-2">Дата</th>
                      <th className="px-3 py-2 text-right">Сумма</th>
                      <th className="px-3 py-2 text-center">Заказчик</th>
                      <th className="px-3 py-2 text-center">Исполнитель</th>
                      <th className="px-3 py-2 text-right">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {acts.length === 0 ? (
                      <tr>
                        <td
                          colSpan={6}
                          className="px-3 py-8 text-center text-slate-400"
                        >
                          Нет актов
                        </td>
                      </tr>
                    ) : (
                      acts.map((act) => (
                        <tr
                          key={act.id}
                          className="border-b border-slate-100 hover:bg-slate-50"
                        >
                          <td className="px-3 py-3 font-mono text-xs">
                            {act.document_number}
                          </td>
                          <td className="px-3 py-3 text-slate-600">
                            {new Date(act.act_date).toLocaleDateString("ru-RU")}
                          </td>
                          <td className="px-3 py-3 text-right font-medium">
                            {fmt(act.total_amount)}
                          </td>
                          <td className="px-3 py-3 text-center">
                            {act.signed_by_client_at ? (
                              <span className="text-green-600">✅</span>
                            ) : (
                              <button
                                onClick={() => signAct(act.id, "client")}
                                className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100"
                              >
                                Подписать
                              </button>
                            )}
                          </td>
                          <td className="px-3 py-3 text-center">
                            {act.signed_by_executor_at ? (
                              <span className="text-green-600">✅</span>
                            ) : (
                              <button
                                onClick={() => signAct(act.id, "executor")}
                                className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100"
                              >
                                Подписать
                              </button>
                            )}
                          </td>
                          <td className="px-3 py-3 text-right">
                            <button
                              onClick={() =>
                                downloadPdf(
                                  `/acts/${act.id}/pdf`,
                                  `${act.document_number}.pdf`
                                )
                              }
                              className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
                            >
                              📥 PDF
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* === PAYOUTS === */}
            {activeTab === "payouts" && (
              <div>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-medium text-slate-900">
                    Выплаты собственникам
                  </h2>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                      <th className="px-3 py-2">Номер</th>
                      <th className="px-3 py-2">Дата</th>
                      <th className="px-3 py-2 text-right">Сумма работ</th>
                      <th className="px-3 py-2 text-right">Комиссия</th>
                      <th className="px-3 py-2 text-right">К выплате</th>
                      <th className="px-3 py-2">Статус</th>
                      <th className="px-3 py-2 text-right">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payouts.length === 0 ? (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-3 py-8 text-center text-slate-400"
                        >
                          Нет выплат
                        </td>
                      </tr>
                    ) : (
                      payouts.map((p) => {
                        const st = statusConfig[p.status] || statusConfig.draft;
                        return (
                          <tr
                            key={p.id}
                            className="border-b border-slate-100 hover:bg-slate-50"
                          >
                            <td className="px-3 py-3 font-mono text-xs">
                              {p.document_number}
                            </td>
                            <td className="px-3 py-3 text-slate-600">
                              {new Date(p.payout_date).toLocaleDateString("ru-RU")}
                            </td>
                            <td className="px-3 py-3 text-right">
                              {fmt(p.gross_amount)}
                            </td>
                            <td className="px-3 py-3 text-right text-orange-600">
                              {fmt(p.platform_commission)} ({p.commission_rate}%)
                            </td>
                            <td className="px-3 py-3 text-right font-semibold text-green-700">
                              {fmt(p.net_amount)}
                            </td>
                            <td className="px-3 py-3">
                              <span
                                className={`rounded-full px-2 py-0.5 text-xs ${st.color}`}
                              >
                                {st.label}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-right">
                              <div className="flex gap-1 justify-end">
                                <button
                                  onClick={() =>
                                    downloadPdf(
                                      `/payouts/${p.id}/pdf`,
                                      `${p.document_number}.pdf`
                                    )
                                  }
                                  className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
                                >
                                  📥 PDF
                                </button>
                                {p.status === "draft" && (
                                  <button
                                    onClick={() => approvePayout(p.id)}
                                    className="rounded border border-green-300 bg-green-50 px-2 py-1 text-xs text-green-700 hover:bg-green-100"
                                  >
                                    ✓ Одобрить
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
