"""
Converter SQL -> XML
Module réutilisable, aucune dépendance Flask
- Lit du SQL (CREATE TABLE)
- Reconstruit XML

Supporte:
CREATE TABLE client (
  id INT(11) NOT NULL AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL UNIQUE,
  PRIMARY KEY (id)
);
"""
import re
from lxml import etree
from typing import List, Dict

def _strip_comments(sql: str) -> str:
    # Supprimer -- commentaires et /* */
    sql = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    return sql

def _split_sql_statements(sql: str) -> List[str]:
    # Split par ; mais pas si dans parenthèses? Simplifié: split par ; et filtrer
    # On garde les statements non vides contenant CREATE
    parts = sql.split(';')
    return [p.strip() for p in parts if p.strip()]

def _extract_table_name_and_body(create_stmt: str):
    """
    Extrait nom table et body entre parenthèses principales
    Retourne (table_name, body_inside_parentheses)
    """
    # Regex pour CREATE TABLE `name` (
    m = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?\s*\(', create_stmt, re.IGNORECASE)
    if not m:
        return None, None
    table_name = m.group(1)

    # Trouver le contenu entre parenthèses en comptant
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
    """
    Split columns definitions by comma, mais pas à l'intérieur de parenthèses (ex DECIMAL(10,2))
    """
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
    """
    Parse une définition de colonne ou contrainte
    Retourne dict colonne ou None si c'est une contrainte PK/FK qu'on traitera ailleurs
    """
    col_def = col_def.strip()
    if not col_def:
        return None

    upper = col_def.upper()

    # Contraintes à ignorer ici (traitées séparément)
    if upper.startswith('PRIMARY KEY') or upper.startswith('FOREIGN KEY') or upper.startswith('UNIQUE KEY') or upper.startswith('KEY ') or upper.startswith('CONSTRAINT'):
        return {'__constraint__': col_def}

    # Colonne: `name` TYPE...
    # Regex: optional backticks, name, type
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
    primary = False  # sera déterminé par contrainte ou inline PRIMARY KEY
    if 'PRIMARY KEY' in rest_upper:
        primary = True

    # default
    default = None
    dm = re.search(r"DEFAULT\s+(?:'([^']*)'|\"([^\"]*)\"|(\S+))", rest, re.IGNORECASE)
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
        'foreign_key': False,  # sera mis à jour si FK trouvée
        'unique': unique,
        'auto_increment': auto_inc,
        'default': default,
        'references': None
    }

def parse_sql(sql_content: str) -> List[Dict]:
    """
    Parse SQL en structure tables
    Returns list of tables dict
    """
    sql = _strip_comments(sql_content)
    statements = _split_sql_statements(sql)

    tables = []

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

        # Traiter contraintes PK et FK
        for constr in constraints:
            upper = constr.upper()
            # PK: PRIMARY KEY (id, ...)
            if 'PRIMARY KEY' in upper:
                m = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', constr, re.IGNORECASE)
                if m:
                    pk_cols = [c.strip(' `') for c in m.group(1).split(',')]
                    for col in columns:
                        if col['name'] in pk_cols:
                            col['primary_key'] = True
            # FK: FOREIGN KEY (col) REFERENCES other_table(other_col)
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

        tables.append({
            'name': table_name,
            'columns': columns
        })

    return tables

def convert_sql_to_xml(sql_content: str, database_name: str = "imported_db") -> str:
    """
    Fonction principale réutilisable
    Input: SQL string
    Output: XML string
    """
    tables = parse_sql(sql_content)

    # Construire XML avec lxml
    db_elem = etree.Element('database', name=database_name)

    for table in tables:
        t_elem = etree.SubElement(db_elem, 'table', name=table['name'])
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
            }
            if col['default'] is not None:
                attrs['default'] = str(col['default'])
            if col['references']:
                attrs['references'] = col['references']
            etree.SubElement(t_elem, 'column', **attrs)

    # Pretty print
    xml_str = etree.tostring(db_elem, pretty_print=True, encoding='unicode', xml_declaration=False)
    # Ajouter déclaration
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

if __name__ == '__main__':
    sample_sql = """
    CREATE TABLE client (
      id INT(11) NOT NULL AUTO_INCREMENT,
      email VARCHAR(255) NOT NULL UNIQUE,
      nom VARCHAR(100) NOT NULL,
      PRIMARY KEY (id)
    );
    CREATE TABLE commande (
      id INT(11) NOT NULL AUTO_INCREMENT,
      client_id INT(11) NOT NULL,
      total DECIMAL(10,2) NOT NULL,
      PRIMARY KEY (id),
      FOREIGN KEY (client_id) REFERENCES client(id)
    );
    """
    print(convert_sql_to_xml(sample_sql, "test_db"))
