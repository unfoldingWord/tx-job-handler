
from unittest import TestCase, skip
from unittest.mock import Mock, patch

from webhook import job, AppSettings, get_linter_module, get_converter_module

class TestLookups(TestCase):

    def test_linter_lookups(self):
        linter_test_table = (
            # input format, resource type, linter name
            ('md','obs','obs'),
            ('md','ta','ta'),
            ('md','tn','tn'),
            ('md','tq','tq'),
            ('md','tw','tw'),
            ('md','something','markdown'), # Should trigger 'other'
            ('usfm','udb','usfm'), # RJH: was 'udb'
            ('usfm','ulb','usfm'), # RJH: was 'ulb'
            ('usfm','bible','usfm'),
            ('usfm','something','usfm'), # Should trigger 'other'
            )
        for input_format, resource_type, expected_linter_name in linter_test_table:
            linter_name, linter_class = get_linter_module({'input_format':input_format,'resource_type':resource_type})
            self.assertEqual(linter_name, expected_linter_name)
            self.assertNotEqual(linter_class, None)

    def test_converter_lookups(self):
        converter_test_table = (
            # input format, resource type, converter name
            ('md','obs','html','md2html'),
            ('md','ta','html','md2html'),
            ('md','tn','html','md2html'),
            ('md','tq','html','md2html'),
            ('md','tw','html','md2html'),
            ('md','something','html','md2html'), # Should trigger 'other'
            ('usfm','udb','html','usfm2html'),
            ('usfm','ulb','html','usfm2html'),
            ('usfm','bible','html','usfm2html'),
            ('usfm','something','html','usfm2html'), # Should trigger 'other'
            )
        for input_format, resource_type, output_format, expected_converter_name in converter_test_table:
            #print(input_format, resource_type, output_format, expected_converter_name)
            converter_name, converter_class = get_converter_module({'input_format':input_format,
                                                    'resource_type':resource_type, 'output_format':output_format})
            self.assertEqual(converter_name, expected_converter_name)
            self.assertNotEqual(converter_class, None)
