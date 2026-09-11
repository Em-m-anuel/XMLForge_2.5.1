"""
Converter XML -> SQL
Module réutilisable, aucune dépendance Flask
- Lit XML représentant une base ou table
- Génère CREATE TABLE avec PK, FK, contraintes
- Génère INSERT INTO pour les données
"""
from lxml import etree
from typing import List, Dict
from datetime import datetime
import re  # <-- CORRECTION 1 : Import manquant


def _bool_from_attr(elem, attr, default=False):
    """Convertit un attribut booléen (true/false/1/yes)"""
    v = elem.get(attr)
    if v is None:
        # essayer l'autre casse
        alt = {
            'primaryKey': 'primary_key', 'primary_key': 'primaryKey',
            'foreignKey': 'foreign_key', 'foreign_key': 'foreignKey',
            'autoIncrement': 'auto_increment', 'auto_increment': 'autoIncrement'
        }
        if attr in alt:
            v = elem.get(alt[attr])
    if v is None:
        return default
    return str(v).lower() in ('true', '1', 'yes')


def _parse_column_element(col_elem) -> Dict:
    """Parse un élément <column> en dict normalisé enrichi"""
    name = col_elem.get('name')
    if not name:
        raise ValueError("Column sans attribut name")

    col_type = col_elem.get('type', 'VARCHAR')
    length = col_elem.get('length', '-')

    # nullable : par défaut true si absent
    nullable_attr = col_elem.get('nullable')
    if nullable_attr is not None:
        nullable = nullable_attr.lower() in ('true', '1', 'yes')
    else:
        nullable = True

    # Gestion references : support table.col ou table(col)
    ref = col_elem.get('references') or col_elem.get('foreignKeyRef')
    if ref:
        # Si format table(col) -> transformer en table.col
        m = re.match(r'^(\w+)\((\w+)\)$', ref)
        if m:
            ref = f"{m.group(1)}.{m.group(2)}"

    return {
        'name': name,
        'type': col_type.upper(),
        'length': length,
        'nullable': nullable,
        'primary_key': _bool_from_attr(col_elem, 'primaryKey'),
        'foreign_key': _bool_from_attr(col_elem, 'foreignKey'),
        'unique': _bool_from_attr(col_elem, 'unique'),
        'auto_increment': _bool_from_attr(col_elem, 'autoIncrement'),
        'default': col_elem.get('default'),
        'references': ref,
        # Nouveaux attributs XMLForge
        'comment': col_elem.get('comment'),
        'displayName': col_elem.get('displayName'),
        'required': _bool_from_attr(col_elem, 'required', default=False),
        'index': _bool_from_attr(col_elem, 'index', default=False),
    }


def _parse_rows(table_elem) -> List[Dict]:
    """Parse <rows> et retourne une liste de dict {col_name: value}"""
    rows_elem = table_elem.find('rows')
    if rows_elem is None:
        return []
    rows = []
    for row_elem in rows_elem.findall('row'):
        row_data = {}
        for cell in row_elem.findall('cell'):
            col = cell.get('column')
            if col is not None:
                is_null = str(cell.get('null', 'false')).lower() in ('true', '1', 'yes')
                row_data[col] = None if is_null else (cell.text if cell.text is not None else '')
        rows.append(row_data)
    return rows


def parse_database(xml_content: str) -> Dict:
    """Parse complet du XML, retourne un dict structuré"""
    try:
        root = etree.fromstring(xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content)
    except Exception as e:
        raise ValueError(f"XML invalide: {e}")

    db_info = {
        'name': root.get('name', ''),
        'description': root.get('description', ''),
        'version': root.get('version', '1.0'),
        'author': root.get('author', ''),
        'created_at': root.get('created_at', datetime.now().isoformat()),
        'tables': []
    }

    if root.tag.lower() == 'database':
        table_elems = root.findall('.//table')
    elif root.tag.lower() == 'table':
        table_elems = [root]
    elif root.tag.lower() in ('tables', 'root'):
        table_elems = root.findall('.//table')
    else:
        table_elems = root.findall('.//table')
        if not table_elems:
            raise ValueError("Aucune table trouvée dans XML. Attendu <table name='...'>")

    for t_elem in table_elems:
        t_name = t_elem.get('name')
        if not t_name:
            continue

        cols = []
        columns_container = t_elem.find('columns')
        if columns_container is not None:
            col_elems = columns_container.findall('column')
        else:
            col_elems = t_elem.findall('column')

        for col_elem in col_elems:
            try:
                cols.append(_parse_column_element(col_elem))
            except Exception:
                continue

        rows = _parse_rows(t_elem)

        table_dict = {
            'name': t_name,
            'description': t_elem.get('description', ''),
            'protected': _bool_from_attr(t_elem, 'protected', default=False),
            'file_identifier': t_elem.get('file_identifier', ''),
            'archived': _bool_from_attr(t_elem, 'archived', default=False),
            'columns': cols,
            'rows': rows,
            'constraints': [],
            'indexes': []
        }
        constraints_parent = t_elem.find('constraints')
        if constraints_parent is not None:
            for constraint in constraints_parent:
                item = {
                    'kind': constraint.tag,
                    'name': constraint.get('name'),
                    'columns': [c.get('name') for c in constraint.findall('column')]
                }
                if constraint.tag == 'foreign-key':
                    item.update({
                        'references_table': constraint.get('references_table'),
                        'references_columns': [c.strip() for c in constraint.get('references_columns', '').split(',') if c.strip()],
                        'on_delete': constraint.get('on_delete', 'NO ACTION'),
                        'on_update': constraint.get('on_update', 'NO ACTION')
                    })
                table_dict['constraints'].append(item)
        indexes_parent = t_elem.find('indexes')
        if indexes_parent is not None:
            for index in indexes_parent.findall('index'):
                table_dict['indexes'].append({
                    'name': index.get('name'),
                    'unique': _bool_from_attr(index, 'unique', False),
                    'columns': [c.get('name') for c in index.findall('column')]
                })
        db_info['tables'].append(table_dict)

    if not db_info['tables']:
        raise ValueError("Aucune table valide trouvée")

    return db_info


def parse_xml(xml_content: str) -> List[Dict]:
    """Retourne uniquement la liste des tables (compatibilité)"""
    db = parse_database(xml_content)
    return db['tables']


def _column_to_sql(col: Dict) -> str:
    """Convertit un dict colonne en définition SQL"""
    col_type = col['type']
    length = col['length']
    if length and length != '-' and '(' not in col_type:
        type_sql = f"{col_type}({length})"
    else:
        type_sql = col_type

    parts = [f"  `{col['name']}` {type_sql}"]

    if not col['nullable']:
        parts.append("NOT NULL")
    if col['auto_increment']:
        parts.append("AUTO_INCREMENT")
    if col['unique']:
        parts.append("UNIQUE")
    if col['default'] is not None and col['default'] != '':
        d = col['default']
        if d.upper() in ('CURRENT_TIMESTAMP', 'NULL') or d.isdigit():
            parts.append(f"DEFAULT {d}")
        else:
            d_esc = d.replace("'", "''")
            parts.append(f"DEFAULT '{d_esc}'")
    return " ".join(parts)


def convert_xml_to_sql(xml_content: str, database_name: str = None) -> str:
    """
    Fonction principale réutilisable
    Input: XML string
    Output: SQL string complet (CREATE DATABASE, CREATE TABLE, INSERT INTO)
    """
    db = parse_database(xml_content)
    db_name = database_name or db['name'] or 'mydb'

    sql_parts = []
    sql_parts.append(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
    sql_parts.append(f"USE `{db_name}`;")
    sql_parts.append("")

    for table in db['tables']:
        t_name = table['name']
        cols = table['columns']
        rows = table['rows']

        if not cols:
            continue

        col_defs = []
        pk_cols = []
        fk_defs = []

        for col in cols:
            col_defs.append(_column_to_sql(col))
            if col['primary_key']:
                pk_cols.append(col['name'])
            if col['foreign_key']:
                ref = col['references']
                if ref:
                    if '.' in ref:
                        ref_table, ref_col = ref.split('.', 1)
                    else:
                        ref_table, ref_col = ref, 'id'  # fallback
                    fk_defs.append(f"  FOREIGN KEY (`{col['name']}`) REFERENCES `{ref_table}`(`{ref_col}`)")

        # Les contraintes composites canoniques remplacent/complètent les flags colonne.
        for constraint in table.get('constraints', []):
            if constraint['kind'] == 'primary-key':
                pk_cols = constraint['columns']
            elif constraint['kind'] == 'unique':
                col_defs.append("  UNIQUE (" + ', '.join(f"`{c}`" for c in constraint['columns']) + ")")
            elif constraint['kind'] == 'foreign-key':
                fk_defs.append(
                    "  FOREIGN KEY (" + ', '.join(f"`{c}`" for c in constraint['columns']) + ") REFERENCES " +
                    f"`{constraint['references_table']}` (" + ', '.join(f"`{c}`" for c in constraint['references_columns']) + ") " +
                    f"ON DELETE {constraint.get('on_delete', 'NO ACTION')} ON UPDATE {constraint.get('on_update', 'NO ACTION')}"
                )
        if pk_cols:
            pk_def = f"  PRIMARY KEY ({', '.join([f'`{c}`' for c in pk_cols])})"
            col_defs.append(pk_def)

        col_defs.extend(fk_defs)

        create_stmt = (f"CREATE TABLE `{t_name}` (\n"
                       + ",\n".join(col_defs)
                       + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
        sql_parts.append(create_stmt)
        indexes = list(table.get('indexes', []))
        for col in cols:
            if col.get('index'):
                indexes.append({'name': f"idx_{t_name}_{col['name']}", 'columns': [col['name']], 'unique': False})
        for index in indexes:
            unique = 'UNIQUE ' if index.get('unique') else ''
            sql_parts.append(
                f"CREATE {unique}INDEX `{index['name']}` ON `{t_name}` (" +
                ', '.join(f"`{c}`" for c in index.get('columns', [])) + ");"
            )

        # Insertions
        if rows:
            col_names = [col['name'] for col in cols]
            for row in rows:
                values = {k: row.get(k) for k in col_names if k in row}
                if not values:
                    continue
                
                cols_str = ', '.join([f'`{k}`' for k in values.keys()])
                vals = []
                for v in values.values():
                    if v is None:
                        vals.append('NULL')
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    else:
                        # CORRECTION 2 : Formatage propre hors de l'expression f-string
                        v_escaped = str(v).replace("'", "''")
                        vals.append(f"'{v_escaped}'")
                        
                vals_str = ', '.join(vals)
                insert_stmt = f"INSERT INTO `{t_name}` ({cols_str}) VALUES ({vals_str});"
                sql_parts.append(insert_stmt)

    return "\n\n".join(sql_parts)


if __name__ == '__main__':
    sample = '''
    <database name="test_db" description="Test XMLForge">
      <table name="client" description="Clients" protected="true" file_identifier="CLI-001" archived="false">
        <columns>
          <column name="id" type="INT" length="11" primaryKey="true" autoIncrement="true" nullable="false" />
          <column name="email" type="VARCHAR" length="255" unique="true" nullable="false" />
          <column name="nom" type="VARCHAR" length="100" nullable="false" />
        </columns>
        <rows>
          <row><cell column="id">1</cell><cell column="email">nyx@example.com</cell><cell column="nom">Nyx</cell></row>
          <row><cell column="id">2</cell><cell column="email">luna@example.com</cell><cell column="nom">Luna</cell></row>
        </rows>
      </table>
    </database>
    '''
    print(convert_xml_to_sql(sample))