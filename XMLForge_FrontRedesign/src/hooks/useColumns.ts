import { useEffect } from "react";
import { useStore } from "../store";

export function useColumns(tableId?: number) {
  const { columns, columnsLoading, columnsError, fetchColumns } = useStore();

  useEffect(() => {
    if (tableId) {
      fetchColumns(tableId);
    }
  }, [tableId, fetchColumns]);

  // Écouter event refresh après édition colonne
  useEffect(() => {
    if (!tableId) return;
    const h = () => fetchColumns(tableId);
    window.addEventListener("xf-refresh-columns", h);
    return () => window.removeEventListener("xf-refresh-columns", h);
  }, [tableId, fetchColumns]);

  return { columns, loading: columnsLoading, error: columnsError, refresh: () => tableId && fetchColumns(tableId) };
}
