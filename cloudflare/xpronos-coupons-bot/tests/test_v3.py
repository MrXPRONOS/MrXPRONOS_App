import sqlite3,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FreePronosSupportTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:')
  self.db.execute('PRAGMA foreign_keys=ON')
  for f in ['0001_initial.sql','0002_free_pronos_experience.sql','0003_support_tickets.sql']:
   self.db.executescript((ROOT/'migrations'/f).read_text(encoding='utf-8'))
  self.db.execute("INSERT INTO users(id,name,adult_confirmed,required_verified,xp) VALUES(10,'Test',1,0,0)")
 def tearDown(self):self.db.close()
 def test_tickets_preserve_user_ownership(self):
  self.db.execute("INSERT INTO support_tickets(user_id,message) VALUES(10,'Mon solde XP est incorrect')")
  self.assertEqual(self.db.execute('SELECT status FROM support_tickets WHERE user_id=10').fetchone()[0],'open')
  self.db.execute("UPDATE support_tickets SET status='replied',admin_reply='Merci, vérification faite.' WHERE id=1")
  self.assertEqual(self.db.execute('SELECT admin_reply FROM support_tickets').fetchone()[0],'Merci, vérification faite.')
 def test_invalid_status_rejected(self):
  with self.assertRaises(sqlite3.IntegrityError):
   self.db.execute("INSERT INTO support_tickets(user_id,message,status) VALUES(10,'Ticket à traiter','withdraw_money')")
 def test_empty_message_rejected(self):
  with self.assertRaises(sqlite3.IntegrityError):
   self.db.execute("INSERT INTO support_tickets(user_id,message) VALUES(10,'')")
if __name__=='__main__':unittest.main()
