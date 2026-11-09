"""MySQL workflow namespaces for the existing pilot API.

Only application-owned SQL is accepted. SQLGlot parses the SQLite dialect used
by the pilot modules and emits MySQL; no SQLite connection is opened here.
Historical file names identify logical namespaces, not physical databases.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

import sqlglot
from sqlglot import exp
from .repositories.mysql import open_connection, MySQLRepository, PROJECTIONS

SCHEMA_PATH=Path(__file__).resolve().parents[1]/'database'/'pilot_schema.json'
LAYOUT=json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
SCOPES={'journal.sqlite3':'j','management.sqlite3':'m','telemetry.sqlite3':'t',
        'followup.sqlite3':'f','research.sqlite3':'r','automation.sqlite3':'a'}
ALIASES={'journal':'j','management':'m','raw':'t','workflow':'f','research':'r'}
REGISTERED={}
ACTIVE=ContextVar('aegis_pilot_connections',default=None)


def store_key(path):
    return sha256(str(Path(path).resolve()).casefold().encode()).hexdigest()[:12]


def configuration(path):
    directory=Path(path).resolve().parent
    known=REGISTERED.get(str(directory))
    if known: return known
    marker=directory/'.aegis-hybrid.json'
    if marker.is_file():
        from .database_config import settings
        record=json.loads(marker.read_text(encoding='utf-8'))
        config=dict(settings(),STORAGE_BACKEND='mysql')
        if record.get('store_key')!=store_key(directory) or record.get('database')!=config['MYSQL']['database']:
            raise RuntimeError('Hybrid store configuration differs; refusing SQLite fallback')
        REGISTERED[str(directory)]=config
        return config
    return None


def initialized(path):
    return configuration(path) is not None


class Row(dict):
    def __getitem__(self,key):
        return tuple(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
    def __iter__(self): return iter(self.values())


class Cursor:
    def __init__(self,rows=(),rowcount=0,lastrowid=None):
        self.rows=iter(Row(r) for r in rows); self.rowcount=rowcount; self.lastrowid=lastrowid
    def fetchone(self): return next(self.rows,None)
    def fetchall(self): return list(self.rows)
    def __iter__(self): return self.rows


def _label(name):
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*',name): raise ValueError('Invalid internal identifier')
    return name


def table_name(key,scope,name):
    return 'p_'+key+'_'+scope+'_'+_label(name)


def _tree(sql):
    # Tag positional binds before parsing so generator reordering cannot swap values.
    count=0
    def tag(match):
        nonlocal count
        token=match.group()
        if token=='?':
            token=':__pos'+str(count); count+=1
        return token
    sql=re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\?",tag,sql)
    return sqlglot.parse_one(sql,read='sqlite')


def _functions(node):
    if isinstance(node,exp.JSONExtract):
        return exp.JSONExtractScalar(this=node.this.copy(),expression=node.expression.copy())
    if isinstance(node,exp.Anonymous) and node.name.upper()=='JSON':
        return exp.Cast(this=node.expressions[0].copy(),to=exp.DataType.build('JSON'))
    if isinstance(node,exp.Anonymous) and node.name.lower()=='forecast_issue_us':
        value=node.expressions[0].copy().transform(_functions).sql(dialect='mysql')
        # All accepted API instants carry Z or an explicit HH:MM offset.
        stamp=f"CAST(REPLACE(LEFT({value},LENGTH({value})-IF(RIGHT({value},1)='Z',1,6)),'T',' ') AS DATETIME(6))"
        zone=f"IF(RIGHT({value},1)='Z','+00:00',RIGHT({value},6))"
        return sqlglot.parse_one(f"TIMESTAMPDIFF(MICROSECOND,'1970-01-01',CONVERT_TZ({stamp},{zone},'+00:00'))",read='mysql')
    return node


def compile_query(sql,params,key,scope):
    tree=_tree(sql)
    ctes={cte.alias for cte in tree.find_all(exp.CTE)}
    def tables(node):
        if not isinstance(node,exp.Table): return node
        name=node.name
        if name in ctes: return node
        namespace=ALIASES.get(node.db,scope)
        if scope=='core' and not node.db or node.db=='main':
            target='api_'+name
        else:
            target=table_name(key,namespace,name)
        alias=node.args.get('alias')
        new=exp.Table(this=exp.to_identifier(target,quoted=True))
        if alias: new.set('alias',alias.copy())
        elif not isinstance(tree,(exp.Insert,exp.Update,exp.Delete,exp.Create)):
            new.set('alias',exp.TableAlias(this=exp.to_identifier(name,quoted=True)))
        return new
    tree=tree.transform(tables).transform(_functions)
    for column in tree.find_all(exp.Column):
        if column.db:
            column.set('db',None)
        if column.name=='rowid': column.set('this',exp.to_identifier('_sequence',quoted=True))
        # SQLite technical columns such as trigger are reserved in MySQL.
        column.this.set('quoted',True)
    for col in tree.find_all(exp.ColumnDef): col.this.set('quoted',True)
    rendered=tree.sql(dialect='mysql',identify=True).replace('%','%%')
    rendered=rendered.replace('INSERT OR IGNORE INTO','INSERT IGNORE INTO')
    values=[]
    def bind(match):
        token=match.group(1)
        if token.startswith('__pos'):
            values.append(params[int(token[5:])])
        else: values.append(params[token])
        return '%s'
    def safe_bind(match):
        return bind(match) if match.group(1) is not None else match.group()
    rendered=re.sub(r"'(?:\\.|''|[^'\\])*'|:([A-Za-z_][A-Za-z0-9_]*)",safe_bind,rendered)
    return rendered,tuple(values)


class PilotConnection:
    def __init__(self,connection,config,key,scope,readonly=False):
        self.connection=connection;self.config=config;self.key=key;self.scope=scope;self.readonly=readonly
        self.repo=MySQLRepository(connection)
    def execute(self,sql,params=()):
        upper=sql.strip().upper()
        if upper.startswith(('BEGIN','PRAGMA')): return Cursor()
        if upper.startswith(('CREATE TABLE','CREATE VIEW','CREATE INDEX','CREATE UNIQUE INDEX')):
            if 'IF NOT EXISTS' in upper:
                name=_tree(sql).find(exp.Table).name
                if name in {o['name'] for v in LAYOUT.values() for o in v['objects']}:
                    return Cursor()
            raise RuntimeError('Pilot schema must be provisioned before serving requests')
        if 'SQLITE_MASTER' in upper:
            match=re.search(r"name\s*=\s*'([^']+)'",sql,re.I)
            if not match: raise ValueError('Unsupported catalog query')
            names={o['name'] for v in LAYOUT.values() for o in v['objects']}
            return Cursor([{'1':1}] if match[1] in names else [])
        if self.readonly and not upper.startswith(('SELECT','WITH')):
            raise sqlite3.OperationalError('Read-only pilot reference connection')
        if self.scope=='core' and upper.startswith('INSERT INTO FARM_ASSESSMENTS'):
            self.repo.add_assessment(params); return Cursor(rowcount=1)
        rendered,values=compile_query(sql,params,self.key,self.scope)
        cursor=self.repo.execute(rendered,values)
        rows=cursor.fetchall() if cursor.description else ()
        result=Cursor(rows,cursor.rowcount,cursor.lastrowid); cursor.close()
        if self.scope=='t' and upper.startswith('INSERT INTO SAMPLES') and result.rowcount:
            from .mongo_delivery import telemetry_event
            telemetry_event(self,params[0])
        if self.scope=='t' and upper.startswith('INSERT INTO SYNTHETIC_FORECAST_INPUTS') and result.rowcount:
            from .mongo_delivery import forecast_event
            forecast_event(self,params[0])
        return result
    def create_function(self,*args,**kwargs): pass  # Known function is compiled above.
    def begin(self,write=False): pass
    def owned(self,kind,identifier,user_id): return self.repo.owned(kind,identifier,user_id)
    def latest_profile(self,season,user): return self.repo.latest_profile(season,user)
    def page(self,table,where,params,size,offset,order):
        if self.scope=='core': return self.repo.page(table,where,params,size,offset,order)
        total=self.execute(f'SELECT COUNT(*) FROM {table} WHERE {where}',params).fetchone()[0]
        rows=self.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?',(*params,size,offset)).fetchall()
        return total,rows


@contextmanager
def connection(path,readonly=False):
    config=configuration(path)
    if config is None: raise RuntimeError('Unregistered MySQL pilot namespace')
    key=store_key(Path(path).parent);scope=SCOPES[Path(path).name]
    active=ACTIVE.get() or {}; identity=(config['MYSQL']['database'],key,scope)
    if identity in active:
        yield active[identity];return
    db=open_connection(config)
    wrapper=PilotConnection(db,config,key,scope,readonly)
    token=ACTIVE.set(dict(active,**{}))
    ACTIVE.get()[identity]=wrapper
    try:
        db.begin()
        wrapper.repo.one('SELECT scope FROM pilot_scope_locks WHERE store_key=%s AND scope=%s FOR UPDATE',(key,scope))
        yield wrapper
        db.commit()
    except BaseException:
        db.rollback();raise
    finally:
        ACTIVE.reset(token);db.close()


def _ddl(sql,key,scope,indexed):
    def column(match):
        name=match[1]
        if name in indexed or name.endswith('_id') or name=='id':
            kind='VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin'
        else: kind='LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin'
        return name+' '+kind
    sql=re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\s+TEXT\b',column,sql,flags=re.I)
    sql=re.sub(r'\bINTEGER\b','BIGINT',sql,flags=re.I)
    tree=_tree(sql)
    # DDL table references must not acquire aliases.
    for table in tree.find_all(exp.Table):
        table.set('this',exp.to_identifier(table_name(key,scope,table.name),quoted=True))
    for identifier in tree.find_all(exp.Identifier): identifier.set('quoted',True)
    return tree.sql(dialect='mysql')


def provision(config,storage):
    key=store_key(storage)
    db=open_connection(config);repo=MySQLRepository(db)
    try:
        row=repo.one('SELECT * FROM pilot_stores WHERE store_key=%s',(key,))
        if row:
            if row['source_path']!=str(Path(storage).resolve()) or row['schema_status']!='complete':
                raise RuntimeError('Pilot namespace is incomplete or has a conflicting source path')
        else:
            repo.execute("INSERT INTO pilot_stores(store_key,source_path,schema_status) VALUES (%s,%s,'running')",(key,str(Path(storage).resolve())))
            db.commit()
            for filename,layout in LAYOUT.items():
                scope=SCOPES[filename]
                # Indexed technical strings share the same MySQL type across FK pairs.
                indexed={c['name'] for cols in layout['columns'].values() for c in cols if c['pk']}
                for obj in layout['objects']:
                    for group in re.findall(r'(?:UNIQUE|PRIMARY KEY|FOREIGN KEY)\s*\(([^)]+)\)',obj['sql'],re.I):
                        indexed.update(x.strip() for x in group.split(','))
                    if obj['type']=='index':
                        group=re.search(r'\bON\s+\w+\s*\(([^)]+)\)',obj['sql'],re.I)
                        if group: indexed.update(x.strip().split()[0] for x in group[1].split(','))
                for obj in layout['objects']:
                    if obj['type']!='table': continue
                    statement=_ddl(obj['sql'],key,scope,indexed)
                    repo.execute(statement)
                    if obj['name'] not in layout['meta']:
                        repo.execute(f'ALTER TABLE `{table_name(key,scope,obj["name"])}` ADD `_sequence` BIGINT NOT NULL AUTO_INCREMENT INVISIBLE UNIQUE')
                for obj in layout['objects']:
                    if obj['type']=='view': repo.execute(_ddl(obj['sql'],key,scope,indexed))
                    if obj['type']=='index':
                        original=obj['sql'];partial=re.search(r'\s+WHERE\s+(.+)$',original,re.I|re.S)
                        if partial:
                            match=re.search(r'ON\s+(\w+)\s*\(([^)]+)\)',original,re.I)
                            columns=[x.strip() for x in match[2].split(',')]
                            first=columns.pop(0)
                            expression=f'(CASE WHEN {partial[1]} THEN `{first}` ELSE NULL END)'
                            keys=','.join([expression]+['`'+x+'`' for x in columns])
                            repo.execute(f'CREATE UNIQUE INDEX `{obj["name"]}` ON `{table_name(key,scope,match[1])}` ({keys})')
                        else: repo.execute(_ddl(original,key,scope,indexed))
                for name,rows in layout['meta'].items():
                    for item in rows:
                        repo.execute(f'INSERT INTO `{table_name(key,scope,name)}` (kind) VALUES (%s)',(item['kind'],))
                repo.execute('INSERT INTO pilot_scope_locks VALUES (%s,%s)',(key,scope))
                db.commit()
            repo.execute("UPDATE pilot_stores SET schema_status='complete' WHERE store_key=%s",(key,));db.commit()
        REGISTERED[str(Path(storage).resolve())]=config
        (Path(storage)/'.aegis-hybrid.json').write_text(json.dumps(dict(
            backend='mysql',mongo=True,store_key=key,database=config['MYSQL']['database'],schema_version=3),indent=2),encoding='utf-8')
    finally: db.close()


def open_readonly(path):
    """Close-compatible reader for offline monitoring tools, never a silent fallback."""
    config=configuration(path)
    if config is None:
        db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        return db
    if Path(path).name=='demo.db':
        from .repositories.mysql import mysql_repository
        manager=mysql_repository(config);repo=manager.__enter__()
        wrapper=PilotConnection(repo.connection,config,store_key(Path(path).parent),'core',readonly=True)
    else:
        manager=connection(path,readonly=True);wrapper=manager.__enter__()
    wrapper.close=lambda:manager.__exit__(None,None,None)
    return wrapper
