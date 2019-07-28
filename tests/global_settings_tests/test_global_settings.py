import unittest

from moto import mock_dynamodb2, mock_s3

from global_settings.global_settings import GlobalSettings
# from models.tx_model import TxModel


# class User(GlobalSettings.Base, TxModel):
#     __tablename__ = 'users'
#     id = Column(Integer, primary_key=True)
#     name = Column(String)
#     fullname = Column(String)
#     password = Column(String)


class TestGlobalSettings(unittest.TestCase):

    def test_init(self):
        GlobalSettings()

    # def test_construction_connection_string(self):
    #     """
    #     Test the construction of the connection string with multiple attributes
    #     """
    #     GlobalSettings(db_protocol='protocol', db_user='user', db_pass='pass', db_end_point='my.endpoint.url', db_port='9999',
    #         db_name='db', db_connection_string_params='charset=utf8', auto_setup_db=False)
    #     expected = "protocol://user:pass@my.endpoint.url:9999/db?charset=utf8"
    #     connection_str = GlobalSettings.construct_connection_string()
    #     self.assertEqual(connection_str, expected)

    @mock_s3
    def test_s3_handler(self):
        self.assertIsNotNone(GlobalSettings.cdn_s3_handler())

    def test_prefix_vars(self):
        GlobalSettings(prefix='')
        self.assertEqual(GlobalSettings.cdn_bucket_name, 'cdn.door43.org')
        # self.assertEqual(GlobalSettings.api_url, 'https://api.door43.org')
        GlobalSettings(prefix='test-')
        self.assertEqual(GlobalSettings.cdn_bucket_name, 'test-cdn.door43.org')
        # self.assertEqual(GlobalSettings.api_url, 'https://test-api.door43.org')
        GlobalSettings(prefix='test2-')
        self.assertEqual(GlobalSettings.cdn_bucket_name, 'test2-cdn.door43.org')
        # self.assertEqual(GlobalSettings.api_url, 'https://test2-api.door43.org')
        GlobalSettings(prefix='')
        self.assertEqual(GlobalSettings.cdn_bucket_name, 'cdn.door43.org')
        # self.assertEqual(GlobalSettings.api_url, 'https://api.door43.org')

    def test_reset_app(self):
        default_name = GlobalSettings.name
        GlobalSettings(name='test-name')
        GlobalSettings()
        self.assertEqual(GlobalSettings.name, default_name)
        GlobalSettings.name = 'test-name-2'
        GlobalSettings(name='test-name-2', reset=False)
        self.assertNotEqual(GlobalSettings.name, default_name)
