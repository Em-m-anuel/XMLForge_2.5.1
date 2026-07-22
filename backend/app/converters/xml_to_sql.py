"""
Converter XML -> SQL
Module réutilisable, aucune dépendance Flask
- Lit XML représentant une base ou table
- Génère CREATE TABLE avec PK, FK, contraintes

Format XML supporté:
<database name="ma_base">
  <table name="client">
    <column name="id" type="INT" length="11" primaryKey="true" autoIncrement="true" nullable="false" />
    <column name="email" type="VARCHAR" length="255" unique="true" nullable="false" />
  </table>
</database>

OU simplement:
<table name="client">...</table>

OU multiple:
<tables>
  <table>...</table>
</tables>
"""
from lxml import etree
from typing import List, Dict

def _parse_column_element(col_elem) -> Dict:
    """Parse un élément <column> en dict normalisé"""
    def _bool(attr, default=False):
        v = col_elem.get(attr)
        if v is None:
            # support camelCase primaryKey etc.
            # Try alternative naming
            alt_map = {
                'primaryKey': 'primary_key',
                'primary_key': 'primaryKey',
                'foreignKey': 'foreign_key',
                'foreign_key': 'foreignKey',
                'autoIncrement': 'auto_increment',
                'auto_increment': 'autoIncrement'
            }
            # check both versions
            for k in [attr, alt_map.get(attr, '')]:
                if k and col_elem.get(k) is not None:
                    v = col_elem.get(k)
                    break
        if v is None:
            return default
        return str(v).lower() in ('true', '1', 'yes')

    name = col_elem.get('name')
    if not name:
        raise ValueError("Column sans attribut name")

    col_type = col_elem.get('type', 'VARCHAR')
    length = col_elem.get('length', '-')
    nullable = not _bool('nullable', default=False) if col_elem.get('nullable') is not None else _bool('nullable', default=True)  # careful
    # Actually logic: nullable true = can be null, so NOT NULL if nullable false
    # In original XML, nullable="false" means NOT NULL
    # So we need to parse correctly
    nullable_attr = col_elem.get('nullable')
    if nullable_attr is not None:
        nullable = nullable_attr.lower() in ('true', '1', 'yes')
    else:
        nullable = True

    return {
        'name': name,
        'type': col_type.upper(),
        'length': length,
        'nullable': nullable,
        'primary_key': _bool('primaryKey') or _bool('primary_key'),
        'foreign_key': _bool('foreignKey') or _bool('foreign_key'),
        'unique': _bool('unique'),
        'auto_increment': _bool('autoIncrement') or _bool('auto_increment'),
        'default': col_elem.get('default'),
        'references': col_elem.get('references') or col_elem.get('foreignKeyRef') or None
    }

def _column_to_sql(col: Dict) -> str:
    """Convertit un dict colonne en définition SQL"""
    # Type + length
    col_type = col['type']
    length = col['length']
    if length and length != '-' and '(' not in col_type:
        # Si type déjà contient (), ne pas ajouter
        # Gérer DECIMAL avec 10,2
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
        # Gérer default string vs number
        d = col['default']
        # Si déjà quoté, garder
        if d.upper() in ('CURRENT_TIMESTAMP', 'NULL') or d.isdigit():
            parts.append(f"DEFAULT {d}")
        else:
            # échapper simple quotes
            d_esc = d.replace("'", "''")
            parts.append(f"DEFAULT '{d_esc}'")

    return " ".join(parts)

def parse_xml(xml_content: str) -> List[Dict]:
    """
    Parse XML content en structure interne:
    Returns list of tables: [{"name": "...", "columns": [col_dict,...]}, ...]
    """
    try:
        root = etree.fromstring(xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content)
    except Exception as e:
        raise ValueError(f"XML invalide: {e}")

    tables = []

    # Cas 1: root est <database> contenant <table>
    if root.tag.lower() == 'database':
        table_elems = root.findall('.//table')
    elif root.tag.lower() == 'table':
        table_elems = [root]
    elif root.tag.lower() in ('tables', 'root'):
        table_elems = root.findall('.//table')
    else:
        # Chercher toutes les tables dans le document
        table_elems = root.findall('.//table')
        if not table_elems:
            # Peut-être root contient directement des column?
            # Si root est table implicite?
            raise ValueError("Aucune table trouvée dans XML. Attendu <table name='...'>")

    for t_elem in table_elems:
        t_name = t_elem.get('name')
        if not t_name:
            continue
        cols = []
        for col_elem in t_elem.findall('./column'):
            try:
                cols.append(_parse_column_element(col_elem))
            except Exception as ex:
                # skip colonne invalide mais log
                continue
        tables.append({
            'name': t_name,
            'description': t_elem.get('description', ''),
            'columns': cols
        })

    if not tables:
        raise ValueError("Aucune table valide trouvée")

    return tables

def convert_xml_to_sql(xml_content: str, database_name: str = None) -> str:
    """
    Fonction principale réutilisable
    Input: XML string
    Output: SQL string complet
    """
    tables = parse_xml(xml_content)

    sql_parts = []

    if database_name:
        # Optionnel: CREATE DATABASE
        sql_parts.append(f"CREATE DATABASE IF NOT EXISTS `{database_name}`;")
        sql_parts.append(f"USE `{database_name}`;")
        sql_parts.append("")

    for table in tables:
        t_name = table['name']
        cols = table['columns']

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
                # Si references fourni, utiliser, sinon générique
                ref = col['references']
                if ref and '.' in ref:
                    ref_table, ref_col = ref.split('.', 1)
                    fk_defs.append(f"  FOREIGN KEY (`{col['name']}`) REFERENCES `{ref_table}`(`{ref_col}`)")
                else:
                    # Commentaire si pas de référence
                    # On ajoute pas de FK sans ref pour éviter erreur SQL, mais on pourrait commenter
                    # Ici on génère juste un commentaire SQL
                    pass

        # PK
        if pk_cols:
            pk_def = f"  PRIMARY KEY ({', '.join([f'`{c}`' for c in pk_cols])})"
            col_defs.append(pk_def)

        # FKs
        col_defs.extend(fk_defs)

        create_stmt = f"CREATE TABLE `{t_name}` (\n" + ",\n".join(col_defs) + "\n);"
        sql_parts.append(create_stmt)

    return "\n\n".join(sql_parts)

# Fonction utilitaire pour usage CLI/test
if __name__ == '__main__':
    sample = '''
    <database name="test">
      <table name="client">
        <column name="id" type="INT" length="11" primaryKey="true" autoIncrement="true" nullable="false" />
        <column name="email" type="VARCHAR" length="255" unique="true" nullable="false" />
        <column name="nom" type="VARCHAR" length="100" nullable="false" />
      </table>
    </database>
    '''
    print(convert_xml_to_sql(sample, "test_db"))
