"""SQL dialect boundaries needed by existing SQLite-shaped pilot queries."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.hybrid_pilot import Row,Cursor,compile_query


class HybridDialectTests(unittest.TestCase):
    def test_row_supports_mapping_and_sqlite_tuple_iteration(self):
        row=Row(status='ready',count=2)
        self.assertEqual(dict(row),{'status':'ready','count':2})
        self.assertEqual(tuple(row),('ready',2))
        self.assertEqual(row[0],'ready')
        self.assertEqual(dict(Cursor([row])),{'ready':2})

    def test_named_bind_does_not_replace_literal_or_percent(self):
        sql,values=compile_query("SELECT ':uid' label FROM events WHERE user_id=:uid AND state LIKE 'r%'",{'uid':'owner'},'123456789012','f')
        self.assertIn("':uid'",sql)
        self.assertIn("'r%%'",sql)
        self.assertEqual(sql.count('%s'),1)
        self.assertEqual(values,('owner',))

    def test_positional_bind_order_and_cte_namespace(self):
        sql,values=compile_query('WITH x AS (SELECT * FROM events WHERE user_id=?) SELECT * FROM x LIMIT ? OFFSET ?',('owner',10,20),'123456789012','f')
        self.assertIn('p_123456789012_f_events',sql)
        self.assertNotIn('p_123456789012_f_x',sql)
        self.assertEqual(values,('owner',10,20))


if __name__=='__main__': unittest.main()
