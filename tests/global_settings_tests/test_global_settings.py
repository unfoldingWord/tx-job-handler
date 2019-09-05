import unittest

from moto import mock_dynamodb2, mock_s3

from app_settings.app_settings import AppSettings
# from models.tx_model import TxModel


# class User(AppSettings.Base, TxModel):
#     __tablename__ = 'users'
#     id = Column(Integer, primary_key=True)
#     name = Column(String)
#     fullname = Column(String)
#     password = Column(String)


class TestAppSettings(unittest.TestCase):

    def test_init(self):
        AppSettings()

    # def test_construction_connection_string(self):
    #     """
    #     Test the construction of the connection string with multiple attributes
    #     """
    #     AppSettings(db_protocol='protocol', db_user='user', db_pass='pass', db_end_point='my.endpoint.url', db_port='9999',
    #         db_name='db', db_connection_string_params='charset=utf8', auto_setup_db=False)
    #     expected = "protocol://user:pass@my.endpoint.url:9999/db?charset=utf8"
    #     connection_str = AppSettings.construct_connection_string()
    #     self.assertEqual(connection_str, expected)

    @mock_s3
    def test_s3_handler(self):
        self.assertIsNotNone(AppSettings.cdn_s3_handler())

    def test_prefix_vars(self):
        AppSettings(prefix='')
        self.assertEqual(AppSettings.cdn_bucket_name, 'cdn.door43.org')
        # self.assertEqual(AppSettings.api_url, 'https://api.door43.org')
        AppSettings(prefix='test-')
        self.assertEqual(AppSettings.cdn_bucket_name, 'test-cdn.door43.org')
        # self.assertEqual(AppSettings.api_url, 'https://test-api.door43.org')
        AppSettings(prefix='test2-')
        self.assertEqual(AppSettings.cdn_bucket_name, 'test2-cdn.door43.org')
        # self.assertEqual(AppSettings.api_url, 'https://test2-api.door43.org')
        AppSettings(prefix='')
        self.assertEqual(AppSettings.cdn_bucket_name, 'cdn.door43.org')
        # self.assertEqual(AppSettings.api_url, 'https://api.door43.org')

    def test_reset_app(self):
        default_name = AppSettings.name
        AppSettings(name='test-name')
        AppSettings()
        self.assertEqual(AppSettings.name, default_name)
        AppSettings.name = 'test-name-2'
        AppSettings(name='test-name-2', reset=False)
        self.assertNotEqual(AppSettings.name, default_name)
