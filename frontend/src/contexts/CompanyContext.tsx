import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import apiClient from "../api/client";
import { useAuth } from "./AuthContext";

export interface Company {
  id: number;
  name: string;
  legal_name?: string | null;
  inn?: string | null;
  default_tax_system?: string | null;
}

interface CompanyContextType {
  companies: Company[];
  currentCompanyId: number | null;
  currentCompany: Company | null;
  setCurrentCompanyId: (id: number) => void;
  isLoading: boolean;
  refetchCompanies: () => Promise<void>;
}

const CompanyContext = createContext<CompanyContextType | undefined>(undefined);

const STORAGE_KEY = "spectech_current_company_id";

export function CompanyProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth();  // 🆕 Получаем статус авторизации
  const [companies, setCompanies] = useState<Company[]>([]);
  const [currentCompanyId, setCurrentCompanyIdState] = useState<number | null>(
    () => {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? parseInt(stored, 10) : null;
    }
  );
  const [isLoading, setIsLoading] = useState(true);

  const fetchCompanies = useCallback(async () => {
    // 🆕 Не делаем запрос, пока пользователь не залогинен
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      console.log("🔄 Fetching companies...");

      const response = await apiClient.get("/me/companies");
      const data: Company[] = response.data;

      console.log("✅ Companies loaded:", data);
      setCompanies(data);

      if (data.length > 0) {
        if (
          !currentCompanyId ||
          !data.find((c) => c.id === currentCompanyId)
        ) {
          const defaultId = data[0].id;
          setCurrentCompanyIdState(defaultId);
          localStorage.setItem(STORAGE_KEY, String(defaultId));
        }
      }
    } catch (error) {
      console.error("❌ Failed to fetch companies:", error);
      setCompanies([]);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, currentCompanyId]);

  // 🆕 Перезагружаем при изменении статуса авторизации
  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies, isAuthenticated]);

  const setCurrentCompanyId = useCallback(async (id: number) => {
    setCurrentCompanyIdState(id);
    localStorage.setItem(STORAGE_KEY, String(id));

    // Обновляем активную компанию на сервере
    try {
      await apiClient.post('/me/active-company', { company_id: id });
      console.log('Active company updated on server:', id);
    } catch (error) {
      console.error('Failed to update active company:', error);
    }

    window.location.reload();
  }, []);

  const currentCompany =
    companies.find((c) => c.id === currentCompanyId) || null;

  return (
    <CompanyContext.Provider
      value={{
        companies,
        currentCompanyId,
        currentCompany,
        setCurrentCompanyId,
        isLoading,
        refetchCompanies: fetchCompanies,
      }}
    >
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const context = useContext(CompanyContext);
  if (context === undefined) {
    throw new Error("useCompany must be used within a CompanyProvider");
  }
  return context;
}
