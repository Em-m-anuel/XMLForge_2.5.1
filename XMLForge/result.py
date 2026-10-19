"""Structure de résultat stable du client XMLForge (Phase 7)."""


class Result:
    """Résultat d'une requête exécutée via TCP.

    Champs selon l'opération :
    - SELECT : ``columns``, ``rows``, ``row_count`` ;
    - INSERT : ``affected_rows``, ``last_insert_id`` ;
    - UPDATE / DELETE : ``affected_rows`` ;
    - DDL / USE / transaction : ``metadata``.
    """

    def __init__(self, raw=None, operation=None):
        self.raw = raw if isinstance(raw, dict) else {}
        self.operation = operation or ""
        self.columns = self._columns()
        self.rows = self._rows()
        self.row_count = self._row_count()
        self.affected_rows = self._affected_rows()
        self.last_insert_id = self._last_insert_id()
        self.metadata = {k: v for k, v in self.raw.items()
                         if k not in ("rows", "total", "pagination")}

    def _columns(self):
        rows = self._rows()
        if rows and isinstance(rows[0], dict):
            return list(rows[0].keys())
        if "count" in self.raw:
            return ["count"]
        return []

    def _rows(self):
        rows = self.raw.get("rows")
        if isinstance(rows, list):
            return rows
        if "count" in self.raw:
            return [{"count": self.raw["count"]}]
        if "row" in self.raw and isinstance(self.raw["row"], dict):
            data = self.raw["row"].get("data")
            if isinstance(data, dict):
                return [data]
        return []

    def _row_count(self):
        if "total" in self.raw:
            return int(self.raw["total"])
        if "count" in self.raw:
            return int(self.raw["count"])
        return len(self._rows())

    def _affected_rows(self):
        for key in ("inserted", "updated", "deleted"):
            if key in self.raw and isinstance(self.raw[key], int):
                return self.raw[key]
        return None

    def _last_insert_id(self):
        row = self.raw.get("row")
        if isinstance(row, dict):
            data = row.get("data")
            if isinstance(data, dict) and data.get("id") is not None:
                return data["id"]
            if row.get("internal_id") is not None:
                return row["internal_id"]
        return None

    def __repr__(self):
        return (f"<XmlforgeResult op={self.operation!r} columns={self.columns!r} "
                f"row_count={self.row_count} affected_rows={self.affected_rows}>")
