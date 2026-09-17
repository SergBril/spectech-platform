import { Building2, ChevronDown, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useCompany } from "../contexts/CompanyContext";

export function CompanySwitcher() {
  // ✅ ВАЖНО: добавлен currentCompanyId в деструктуризацию!
  const { companies, currentCompanyId, currentCompany, setCurrentCompanyId, isLoading } =
    useCompany();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Закрытие dropdown при клике вне
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-gray-500">
        <Building2 className="h-4 w-4 animate-pulse" />
        <span>Загрузка...</span>
      </div>
    );
  }

  if (companies.length <= 1) {
    // Если только одна компания — показываем без dropdown
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700">
        <Building2 className="h-4 w-4 text-blue-600" />
        <span className="font-medium">{currentCompany?.name || "Компания"}</span>
      </div>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors shadow-sm"
      >
        <Building2 className="h-4 w-4 text-blue-600" />
        <span className="font-medium text-gray-700 max-w-[180px] truncate">
          {currentCompany?.name || "Выберите компанию"}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-gray-500 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg z-50 overflow-hidden">
          <div className="p-2 border-b border-gray-100 bg-gray-50">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Доступные компании
            </p>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {companies.map((company) => {
              // ✅ Теперь currentCompanyId доступен!
              const isSelected = company.id === currentCompanyId;
              return (
                <button
                  key={company.id}
                  onClick={() => {
                    setCurrentCompanyId(company.id);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-blue-50 transition-colors ${
                    isSelected ? "bg-blue-50" : ""
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-medium truncate ${
                          isSelected ? "text-blue-700" : "text-gray-900"
                        }`}
                      >
                        {company.name}
                      </span>
                      {isSelected && (
                        <Check className="h-4 w-4 text-blue-600 flex-shrink-0" />
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                      {company.inn && <span>ИНН: {company.inn}</span>}
                      {company.default_tax_system && (
                        <>
                          <span>•</span>
                          <span className="font-medium">
                            {getTaxSystemLabel(company.default_tax_system)}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function getTaxSystemLabel(taxSystem: string): string {
  const labels: Record<string, string> = {
    osno: "ОСНО",
    usn_6: 'УСН "Доходы"',
    usn_15: 'УСН "Доходы-Расходы"',
    patent: "Патент",
    npd: "НПД",
  };
  return labels[taxSystem] || taxSystem;
}
