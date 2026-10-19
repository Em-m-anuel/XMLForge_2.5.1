import { useEffect } from "react";
import { useStore } from "../store";

export function useTables(dbId?: string) {
  const { tables, tablesLoading, tablesError, fetchTables } = useStore();

  useEffect(() => {
    if (dbId) {
      fetchTables(dbId);
    }
  }, [dbId, fetchTables]);

  return { tables, loading: tablesLoading, error: tablesError, refresh: () => fetchTables(dbId) };
}
