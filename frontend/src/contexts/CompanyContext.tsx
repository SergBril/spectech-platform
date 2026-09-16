import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import apiClient from "../api/client";

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
  const [companies, setCompanies] = useState<Company[]>([]);
  const [currentCompanyId, setCurrentCompanyIdState] = useState<number | null>(
    () => {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? parseInt(stored, 10) : null;
    }
  );
  const [isLoading, setIsLoading] = useState(true);

  const fetchCompanies = useCallback(async () => {
    try {
      setIsLoading(true);
      const token = localStorage.getItem("access_token");
      if (!token) {
        setCompanies([]);
        return;
      }

      const response = await apiClient.get("/me/companies");
      const data: Company[] = response.data;
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
      console.error("Failed to fetch companies:", error);
      setCompanies([]);
    } finally {
      setIsLoading(false);
    }
  }, [currentCompanyId]);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  const setCurrentCompanyId = useCallback((id: number) => {
    setCurrentCompanyIdState(id);
    localStorage.setItem(STORAGE_KEY, String(id));
    // Перезагружаем страницу для обновления всех данных
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
