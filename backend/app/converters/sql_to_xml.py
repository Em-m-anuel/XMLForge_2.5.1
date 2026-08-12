"""
Converter SQL -> XML
Module réutilisable, aucune dépendance Flask
- Lit du SQL (CREATE TABLE, INSERT INTO)
- Reconstruit XML au format XMLForge

Supporte:
CREATE TABLE client (
  id INT(11) NOT NULL AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL UNIQUE,
  INDEX idx_name (nom),
  UNIQUE KEY uk_email (email),
  PRIMARY KEY (id)
);

INSERT INTO client (id, email, nom) VALUES (1, 'nyx@ex.com', 'Nyx'), (2, 'luna@ex.com', 'Luna');

Génère:
<database name="imported_db" description="" version="2.0" generator="XMLForge" created_at="..." author="">
  <table name="client" description="" protected="false" file_identifier="" archived="false">
    <columns>
      <column name="id" type="INT" length="11" ... index="false" />
      <column name="email" type="VARCHAR" length="255" ... unique="true" />
      <column name="nom" type="VARCHAR" length="100" ... index="true" />
    </columns>
    <rows>
      <row>
        <cell column="id">1</cell>
        <cell column="email">nyx@ex.com</cell>
        <cell column="nom">Nyx</cell>
      </row>
      ...
    </rows>
  </table>
</database>
"""
import re
from lxml import etree
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# ---------- helpers existants (inchangés) ----------
def _strip_comments(sql: str) -> str:
    sql = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    return sql

def _split_sql_statements(sql: str) -> List[str]:
    parts = sql.split(';')
    return [p.strip() for p in parts if p.strip()]

def _extract_table_name_and_body(create_stmt: str):
    m = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?\s*\(', create_stmt, re.IGNORECASE)
    if not m:
        return None, None
    table_name = m.group(1)
    start = create_stmt.find('(', m.end() - 1)
    if start == -1:
        return table_name, None
    depth = 0
    end = -1
    for i in range(start, len(create_stmt)):
        if create_stmt[i] == '(':
            depth += 1
        elif create_stmt[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return table_name, None
    body = create_stmt[start+1:end]
    return table_name, body

def _split_columns(body: str) -> List[str]:
    cols = []
    current = ''
    depth = 0
    in_single = False
    in_double = False
    for ch in body:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ',' and depth == 0:
                cols.append(current.strip())
                current = ''
                continue
        current += ch
    if current.strip():
        cols.append(current.strip())
    return cols

def _parse_column_def(col_def: str) -> Dict | None:
    col_def = col_def.strip()
    if not col_def:
        return None
    upper = col_def.upper()
    if upper.startswith('PRIMARY KEY') or upper.startswith('FOREIGN KEY') or upper.startswith('UNIQUE KEY') or upper.startswith('KEY ') or upper.startswith('CONSTRAINT') or upper.startswith('INDEX'):
        return {'__constraint__': col_def}
    m = re.match(r'`?(\w+)`?\s+([A-Z]+)(?:\(([^)]+)\))?\s*(.*)', col_def, re.IGNORECASE)
    if not m:
        return None
    name = m.group(1)
    col_type = m.group(2).upper()
    length = m.group(3) if m.group(3) else '-'
    rest = m.group(4) or ''
    rest_upper = rest.upper()
    nullable = 'NOT NULL' not in rest_upper
    auto_inc = 'AUTO_INCREMENT' in rest_upper
    unique = 'UNIQUE' in rest_upper and 'PRIMARY' not in rest_upper
    primary = 'PRIMARY KEY' in rest_upper
    default = None
    # Capture tout ce qui suit DEFAULT (quotes ou non)
    dm = re.search(r"DEFAULT\s+(?:(?:'([^']*)')|(?:\"([^\"]*)\")|(\S+))", rest, re.IGNORECASE)
    if dm:
        default = dm.group(1) or dm.group(2) or dm.group(3)
        if default:
            default = default.strip("'\"")
    return {
        'name': name,
        'type': col_type,
        'length': length,
        'nullable': nullable,
        'primary_key': primary,
        'foreign_key': False,
        'unique': unique,
        'auto_increment': auto_inc,
        'default': default,
        'references': None,
        'index': False  # sera mis à jour par les contraintes INDEX
    }

# ---------- nouveaux helpers pour INSERT ----------
def _split_top_level(text: str, delimiter: str = ',') -> List[str]:
    """Split sans tenir compte des parenthèses, guillemets, etc."""
    parts = []
    current = ''
    depth = 0
    in_single = False
    in_double = False
    for ch in text:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == delimiter and depth == 0:
                parts.append(current.strip())
                current = ''
                continue
        current += ch
    if current.strip():
        parts.append(current.strip())
    return parts

def _parse_values_tuple(tuple_str: str) -> List[str]:
    """Parse une ligne de VALUES, retourne la liste des valeurs brutes."""
    # Enlève les parenthèses extérieures
    tuple_str = tuple_str.strip()
    if tuple_str.startswith('(') and tuple_str.endswith(')'):
        tuple_str = tuple_str[1:-1]
    # Split par virgule top-level
    return _split_top_level(tuple_str)

def _parse_insert_statement(insert_stmt: str) -> Tuple[Optional[str], List[str], List[List[str]]]:
    """
    Extrait le nom de la table, la liste des colonnes, et la liste des tuples de valeurs.
    Retourne (table_name, columns, list_of_tuples)
    """
    insert_stmt = insert_stmt.strip()
    # Normaliser les guillemets
    insert_stmt = re.sub(r'`', '', insert_stmt)  # on enlève les backticks pour simplifier

    # Pattern: INSERT INTO table_name (col1, col2) VALUES ...
    m = re.match(r'INSERT\s+INTO\s+(\w+)\s*(?:\(([^)]*)\))?\s+VALUES\s+(.*)', insert_stmt, re.IGNORECASE | re.DOTALL)
    if not m:
        return None, [], []
    table_name = m.group(1)
    columns_part = m.group(2) if m.group(2) else ''
    values_part = m.group(3).strip()

    # Colonnes
    columns = [c.strip() for c in _split_top_level(columns_part) if c.strip()] if columns_part else []

    # Découper les tuples VALUES
    # On cherche les tuples entre parenthèses, mais attention aux parenthèses imbriquées (fonctions)
    # On utilise un parser simple : on extrait tout ce qui est entre parenthèses au niveau 0
    tuples = []
    depth = 0
    current = ''
    for ch in values_part:
        if ch == '(':
            if depth == 0:
                current = ''
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                tuples.append(current.strip())
                current = ''
        else:
            if depth > 0:
                current += ch
    # Si pas de parenthèses, on traite comme une seule valeur ?
    if not tuples and values_part:
        # peut-être une simple ligne
        tuples = [values_part]

    values_list = []
    for tup in tuples:
        values = _parse_values_tuple(tup)
        values_list.append(values)

    return table_name, columns, values_list

# ---------- parse_sql modifié ----------
def parse_sql(sql_content: str) -> List[Dict]:
    """
    Parse SQL en structure tables.
    Chaque table contient : name, description, protected, archived, file_identifier, columns, rows.
    Les rows sont peuplées à partir des INSERT INTO.
    """
    sql = _strip_comments(sql_content)
    statements = _split_sql_statements(sql)

    tables_dict = {}
    tables = []

    # Première passe : CREATE TABLE
    for stmt in statements:
        if not re.search(r'CREATE\s+TABLE', stmt, re.IGNORECASE):
            continue

        table_name, body = _extract_table_name_and_body(stmt)
        if not table_name or not body:
            continue

        col_defs_raw = _split_columns(body)

        columns = []
        constraints = []

        for cd in col_defs_raw:
            parsed = _parse_column_def(cd)
            if not parsed:
                continue
            if '__constraint__' in parsed:
                constraints.append(parsed['__constraint__'])
            else:
                columns.append(parsed)

        # Traiter les contraintes (PK, FK, UNIQUE, INDEX)
        for constr in constraints:
            upper = constr.upper()
            # PRIMARY KEY
            if 'PRIMARY KEY' in upper:
                m = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', constr, re.IGNORECASE)
                if m:
                    pk_cols = [c.strip(' `') for c in m.group(1).split(',')]
                    for col in columns:
                        if col['name'] in pk_cols:
                            col['primary_key'] = True
            # FOREIGN KEY
            if 'FOREIGN KEY' in upper:
                m = re.search(r'FOREIGN\s+KEY\s*\(`?(\w+)`?\)\s*REFERENCES\s*`?(\w+)`?\s*\(`?(\w+)`?\)', constr, re.IGNORECASE)
                if m:
                    fk_col = m.group(1)
                    ref_table = m.group(2)
                    ref_col = m.group(3)
                    for col in columns:
                        if col['name'] == fk_col:
                            col['foreign_key'] = True
                            col['references'] = f"{ref_table}.{ref_col}"
            # UNIQUE KEY ou CONSTRAINT UNIQUE
            if 'UNIQUE' in upper and 'PRIMARY' not in upper:
                m = re.search(r'(?:UNIQUE\s+KEY|CONSTRAINT\s+\w+\s+UNIQUE)\s*\(([^)]+)\)', constr, re.IGNORECASE)
                if not m:
                    m = re.search(r'UNIQUE\s*\(([^)]+)\)', constr, re.IGNORECASE)
                if m:
                    unique_cols = [c.strip(' `') for c in m.group(1).split(',')]
                    for col in columns:
                        if col['name'] in unique_cols:
                            col['unique'] = True
            # INDEX ou KEY (sans UNIQUE)
            if ('INDEX' in upper or ('KEY' in upper and 'UNIQUE' not in upper and 'PRIMARY' not in upper and 'FOREIGN' not in upper)):
                # on ignore les contraintes de type KEY sans parenthèses ?
                m = re.search(r'(?:INDEX|KEY)\s+\w+\s*\(([^)]+)\)', constr, re.IGNORECASE)
                if not m:
                    m = re.search(r'(?:INDEX|KEY)\s*\(([^)]+)\)', constr, re.IGNORECASE)
                if m:
                    index_cols = [c.strip(' `') for c in m.group(1).split(',')]
                    for col in columns:
                        if col['name'] in index_cols:
                            col['index'] = True

        tables_dict[table_name] = {
            'name': table_name,
            'description': '',
            'protected': False,
            'archived': False,
            'file_identifier': '',
            'columns': columns,
            'rows': []
        }

    # Deuxième passe : INSERT INTO
    for stmt in statements:
        if not re.search(r'INSERT\s+INTO', stmt, re.IGNORECASE):
            continue
        table_name, columns_list, values_tuples = _parse_insert_statement(stmt)
        if not table_name or table_name not in tables_dict:
            continue
        table = tables_dict[table_name]
        # Si columns_list est vide, on utilise l'ordre des colonnes de la table
        if not columns_list:
            columns_list = [col['name'] for col in table['columns']]
        # Pour chaque tuple de valeurs, construire un dict
        for val_tuple in values_tuples:
            if len(val_tuple) != len(columns_list):
                # Mismatch : on ignore cette ligne
                continue
            row = {}
            for i, col_name in enumerate(columns_list):
                # La valeur peut être une fonction ou un littéral
                raw_val = val_tuple[i].strip()
                # Si c'est une chaîne entre guillemets, on enlève les guillemets
                if raw_val.startswith("'") and raw_val.endswith("'"):
                    raw_val = raw_val[1:-1].replace("''", "'")
                elif raw_val.startswith('"') and raw_val.endswith('"'):
                    raw_val = raw_val[1:-1].replace('""', '"')
                # Sinon, on garde tel quel (NULL, NOW(), etc.)
                row[col_name] = raw_val if raw_val != 'NULL' else None
            table['rows'].append(row)

    return list(tables_dict.values())

# ---------- convert_sql_to_xml modifié ----------
def convert_sql_to_xml(sql_content: str, database_name: str = "imported_db", author: str = "") -> str:
    """
    Fonction principale réutilisable
    Input: SQL string
    Output: XML string au format XMLForge
    """
    tables = parse_sql(sql_content)

    # Élément racine avec attributs XMLForge
    db_elem = etree.Element('database',
                            name=database_name,
                            description='',
                            version='2.0',
                            generator='XMLForge',
                            created_at=datetime.now().isoformat(),
                            author=author)

    for table in tables:
        # Attributs table XMLForge
        t_elem = etree.SubElement(db_elem, 'table',
                                  name=table['name'],
                                  description=table['description'],
                                  protected=str(table['protected']).lower(),
                                  archived=str(table['archived']).lower(),
                                  file_identifier=table['file_identifier'])

        # Colonnes
        cols_elem = etree.SubElement(t_elem, 'columns')
        for col in table['columns']:
            attrs = {
                'name': col['name'],
                'type': col['type'],
                'length': col['length'],
                'nullable': str(col['nullable']).lower(),
                'primaryKey': str(col['primary_key']).lower(),
                'foreignKey': str(col['foreign_key']).lower(),
                'unique': str(col['unique']).lower(),
                'autoIncrement': str(col['auto_increment']).lower(),
                'index': str(col.get('index', False)).lower()
            }
            if col['default'] is not None:
                attrs['default'] = str(col['default'])
            if col['references']:
                # Transformer table.col en table(col)
                ref = col['references']
                if '.' in ref:
                    ref_table, ref_col = ref.split('.', 1)
                    ref = f"{ref_table}({ref_col})"
                attrs['references'] = ref
            etree.SubElement(cols_elem, 'column', **attrs)

        # Lignes
        rows_elem = etree.SubElement(t_elem, 'rows')
        for row in table['rows']:
            row_elem = etree.SubElement(rows_elem, 'row')
            for col_name, value in row.items():
                if value is not None:
                    cell = etree.SubElement(row_elem, 'cell', column=col_name)
                    cell.text = str(value)

    # Pretty print
    xml_str = etree.tostring(db_elem, pretty_print=True, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str


if __name__ == '__main__':
    sample_sql = """
    CREATE TABLE client (
      id INT(11) NOT NULL AUTO_INCREMENT,
      email VARCHAR(255) NOT NULL,
      nom VARCHAR(100) NOT NULL,
      PRIMARY KEY (id),
      UNIQUE KEY uk_email (email),
      INDEX idx_nom (nom)
    );
    INSERT INTO client (id, email, nom) VALUES (1, 'nyx@ex.com', 'Nyx'), (2, 'luna@ex.com', 'Luna');
    """
    print(convert_sql_to_xml(sample_sql, "test_db", "John Doe"))