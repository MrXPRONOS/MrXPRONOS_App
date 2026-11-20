import importlib.util
from pathlib import Path
from unittest import TestCase, mock
import sys

ROOT=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('franchise_publisher',ROOT/'publish_franchise_saga_bot.py')
ff=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ff)

class FranchisePosterTests(TestCase):
    def test_one_saga_poster_has_download_rescue_and_public_source(self):
        mark=ff.poster_keyboard('abcdefghijklmnopqrstuvwx','https://t.me/+abcdefghijkL')
        self.assertEqual(len(mark['inline_keyboard']),3)
        self.assertIn('ffs_abcdefghijklmnopqrstuvwx',mark['inline_keyboard'][0][0]['url'])
        self.assertEqual(mark['inline_keyboard'][2][0]['url'],'https://t.me/fastandfuriousvffr')
        self.assertEqual([x[0]['style'] for x in mark['inline_keyboard']],['success','danger','primary'])

    def test_invalid_poster_token_or_backup_is_rejected(self):
        with self.assertRaises(RuntimeError):
            ff.poster_keyboard('short','https://t.me/+abcdefghijkL')
        with self.assertRaises(RuntimeError):
            ff.poster_keyboard('abcdefghijklmnopqrstuvwx','https://evil.example')

    def test_no_media_means_publication_cannot_start(self):
        entries={
         'slug':ff.SLUG,'source_chat_id':'-1001234567890',
         'poster_source_message_id':55,'public_post_id':None,'rescue_post_id':None,
         'rights_attested':1,'status':'draft','token':'abcdefghijklmnopqrstuvwx',
        }
        class Bot:
            def __init__(self,secret):
                self._token=secret
            def call(self,method,data):
                if method=='getMe':return {'id':123,'username':'CineXPublishBot'}
                if method=='getChat':
                    if str(data['chat_id']).lower() in ('@fastandfuriousvffr','-1001234567890'):
                        return {'id':-1001234567890,'type':'channel','username':ff.HANDLE,
                                'pinned_message':{'photo':[{'file_id':'poster'}],'message_id':55}}
                    if data['chat_id']==ff.PUBLIC:
                        return {'id':-1009999999999,'type':'channel'}
                    return {'id':-1004357703501,'type':'channel'}
                if method=='getChatMember':
                    return {'status':'administrator','can_post_messages':True}
                raise AssertionError(method)
        def d1(sql,params):
            if 'FROM cine_franchise_catalog' in sql:return [entries]
            if 'FROM cine_classic_rescue_config' in sql:return [{'rescue_chat_id':'-1004357703501','invite_url':'https://t.me/+abcdefghijkL'}]
            if 'COUNT(*) AS n FROM cine_franchise_films' in sql:return [{'n':0}]
            if 'COUNT(*) AS n FROM cine_owner_vault' in sql:return [{'n':0}]
            if sql.strip().startswith('UPDATE'):return []
            raise AssertionError(sql)
        env={'CINEX_PUBLISH_BOT_TOKEN':'123:token'}
        with mock.patch.dict('os.environ',env,clear=True):
            with mock.patch.object(ff,'d1',side_effect=d1):
                with mock.patch.object(ff,'BotAPI',Bot):
                    with mock.patch.object(ff,'identify_radar_bot',return_value=456):
                        with mock.patch.object(ff,'request_bot') as telegram_write:
                            with self.assertRaisesRegex(RuntimeError,'source, affiche ou films'):
                                ff.audit_and_publish(publish=True)
                            telegram_write.assert_not_called()
