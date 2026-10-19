import { useEffect } from "react";
import { useStore } from "../store";

/**
 * Hook pour gérer les bases de données avec nettoyage stale et guards race
 * Utilisé pour garantir cohérence lors changement rapide de contexte
 */
export function useDatabases() {
  const { dbs, dbsLoading, dbsError, fetchDatabases } = useStore();

  useEffect(() => {
    fetchDatabases();
  }, [fetchDatabases]);

  return { dbs, loading: dbsLoading, error: dbsError, refresh: fetchDatabases };
}
