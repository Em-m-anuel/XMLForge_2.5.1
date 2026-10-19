import { useEffect, useState, useCallback } from "react";
import { useStore } from "../store";

export function useRows(tableId?: number) {
  const { rows, rowsTotal, rowsLoading, rowsError, fetchRows } = useStore();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState("");
  const [sortDir, setSortDir] = useState<"ASC" | "DESC">("ASC");

  const load = useCallback((opts: any = {}) => {
    if (!tableId) return;
    fetchRows(tableId, {
      limit: opts.limit ?? pageSize,
      offset: opts.offset ?? (page - 1) * pageSize,
      search: opts.search ?? search,
      sort: opts.sort ?? sortCol,
      order: opts.order ?? sortDir,
      filters: opts.filters ?? {},
    });
  }, [tableId, page, pageSize, search, sortCol, sortDir, fetchRows]);

  useEffect(() => {
    load();
  }, [load]);

  return {
    rows,
    total: rowsTotal,
    loading: rowsLoading,
    error: rowsError,
    page,
    setPage,
    pageSize,
    setPageSize,
    search,
    setSearch,
    sortCol,
    setSortCol,
    sortDir,
    setSortDir,
    refresh: load,
  };
}
