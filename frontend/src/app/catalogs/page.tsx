"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getAccessToken } from "@/lib/api";

type Tab = "categories" | "contractors" | "roles" | "permissions";

interface Contractor {
  id: number;
  type: string;
  name: string;
  inn: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  is_active: boolean;
}

interface Category {
  id: number;
  name: string;
  code: string;
  level: number;
  parent_id: number | null;
  is_active: boolean;
}

interface Role {
  id: number;
  code: string;
  name: string;
  description: string | null;
  is_system: boolean;
}

interface Permission {
  id: number;
  entity: string;
  action: string;
  description: string | null;
}

export default function CatalogsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("contractors");
  const [mounted, setMounted] = useState(false);

  // Данные
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [userRoles, setUserRoles] = useState<string[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setMounted(true);

    const token = getAccessToken();
    if (!token) {
      router.push("/login");
      return;
    }

    loadAll();
  }, [router]);

  async function loadAll() {
    setLoading(true);
    try {
      const [cont, cats, r, p, myRoles] = await Promise.all([
        apiFetch<Contractor[]>("/contractors"),
        apiFetch<Category[]>("/categories"),
        apiFetch<Role[]>("/rbac/roles"),
        apiFetch<Permission[]>("/rbac/permissions"),
        apiFetch<string[]>("/me/roles"),
      ]);
      
      setContractors(cont);
      setCategories(cats);
      setRoles(r);
      setPermissions(p);
      setUserRoles(myRoles);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "contractors", label: "Контрагенты", icon: "👥" },
    { id: "categories", label: "Категории", icon: "📁" },
    { id: "roles", label: "Роли", icon: "🎭" },
    { id: "permissions", label: "Права", icon: "🔐" },
  ];

  const contractorTypeLabels: Record<string, string> = {
    client: "Клиент",
    owner: "Собственник",
    employee: "Сотрудник",
  };

  if (!mounted) return null;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-500">Загрузка...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              Справочники
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Ваши роли: {userRoles.join(", ") || "—"}
            </p>
          </div>
          <button
            onClick={() => router.push("/dashboard")}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
          >
            ← На дашборд
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

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
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          {/* CONTRACTORS */}
          {activeTab === "contractors" && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-medium text-slate-900">
                  Контрагенты ({contractors.length})
                </h2>
                <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
                  + Добавить
                </button>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                    <th className="px-3 py-2">ID</th>
                    <th className="px-3 py-2">Тип</th>
                    <th className="px-3 py-2">Название</th>
                    <th className="px-3 py-2">ИНН</th>
                    <th className="px-3 py-2">Контакт</th>
                    <th className="px-3 py-2">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {contractors.map((c) => (
                    <tr
                      key={c.id}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="px-3 py-3">{c.id}</td>
                      <td className="px-3 py-3">
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">
                          {contractorTypeLabels[c.type] || c.type}
                        </span>
                      </td>
                      <td className="px-3 py-3 font-medium">{c.name}</td>
                      <td className="px-3 py-3 text-slate-500">
                        {c.inn || "—"}
                      </td>
                      <td className="px-3 py-3 text-slate-600">
                        {c.contact_name || "—"}
                        {c.contact_phone && (
                          <div className="text-xs text-slate-400">
                            {c.contact_phone}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs ${
                            c.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          {c.is_active ? "Активен" : "Неактивен"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* CATEGORIES */}
          {activeTab === "categories" && (
            <div>
              <h2 className="text-lg font-medium text-slate-900 mb-4">
                Категории техники ({categories.length})
              </h2>
              <div className="space-y-2">
                {categories.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3"
                    style={{ marginLeft: `${(c.level - 1) * 20}px` }}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-slate-400">
                        {c.parent_id ? "└─" : "📁"}
                      </span>
                      <div>
                        <div className="font-medium">{c.name}</div>
                        <div className="text-xs text-slate-500">{c.code}</div>
                      </div>
                    </div>
                    <span className="text-xs text-slate-500">
                      Уровень {c.level}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ROLES */}
          {activeTab === "roles" && (
            <div>
              <h2 className="text-lg font-medium text-slate-900 mb-4">
                Роли ({roles.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {roles.map((r) => (
                  <div
                    key={r.id}
                    className="rounded-lg border border-slate-200 p-4"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-medium text-slate-900">{r.name}</div>
                      {r.is_system && (
                        <span className="rounded bg-blue-100 text-blue-700 px-2 py-0.5 text-xs">
                          системная
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 mb-1">
                      Код: <code className="bg-slate-100 px-1">{r.code}</code>
                    </div>
                    {r.description && (
                      <div className="text-sm text-slate-600">
                        {r.description}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* PERMISSIONS */}
          {activeTab === "permissions" && (
            <div>
              <h2 className="text-lg font-medium text-slate-900 mb-4">
                Права доступа ({permissions.length})
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                    <th className="px-3 py-2">Сущность</th>
                    <th className="px-3 py-2">Действие</th>
                    <th className="px-3 py-2">Полное право</th>
                  </tr>
                </thead>
                <tbody>
                  {permissions.map((p) => (
                    <tr
                      key={p.id}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="px-3 py-3">
                        <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs">
                          {p.entity}
                        </code>
                      </td>
                      <td className="px-3 py-3">
                        <code className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-xs">
                          {p.action}
                        </code>
                      </td>
                      <td className="px-3 py-3 text-slate-500 font-mono text-xs">
                        {p.entity}:{p.action}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}