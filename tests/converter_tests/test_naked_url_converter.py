import unittest


from converters.convert_naked_urls import fix_naked_urls


testData = (
                    ('example.com', '<a href="http://example.com">example.com</a>'),
                    (' example.org', ' <a href="http://example.org">example.org</a>'),
                    (' example.net ', ' <a href="http://example.net">example.net</a> '),
                    (' example.us!', ' <a href="http://example.us">example.us</a>!'),
                    (' example.bible', ' <a href="http://example.bible">example.bible</a>'),
                    ('(example.bible)', '(<a href="http://example.bible">example.bible</a>)'),
                    ('[example.bible]', '[<a href="http://example.bible">example.bible</a>]'),
                    ('<example.bible>', '<a href="http://example.bible">example.bible</a>'),
                    ('www.example.com', '<a href="http://www.example.com">www.example.com</a>'),
                    ('(www.example.com)', '(<a href="http://www.example.com">www.example.com</a>)'),
                    ('[www.example.com]', '[<a href="http://www.example.com">www.example.com</a>]'),
                    ('<www.example.com>', '<a href="http://www.example.com">www.example.com</a>'),
                    ('http://example.com', '<a href="http://example.com">http://example.com</a>'),
                    ('http://www.example.com', '<a href="http://www.example.com">http://www.example.com</a>'),
                    (' https://example.com', ' <a href="https://example.com">https://example.com</a>'),
                    (' ftp://example.com download', ' <a href="ftp://example.com">ftp://example.com</a> download'),
                    ('(http://example.com)', '(<a href="http://example.com">http://example.com</a>)'),
                    ('[http://example.com]', '[<a href="http://example.com">http://example.com</a>]'),
                    ('<http://example.com>', '<a href="http://example.com">http://example.com</a>'),
                    (' http://example.com/ ', ' <a href="http://example.com/">http://example.com/</a> '),
                    (' (http://example.com/) ', ' (<a href="http://example.com/">http://example.com/</a>) '),
                    (' [http://example.com/] ', ' [<a href="http://example.com/">http://example.com/</a>] '),
                    (' <http://example.com/> ', ' <a href="http://example.com/">http://example.com/</a> '),
                    ('go to http://example.com', 'go to <a href="http://example.com">http://example.com</a>'),
                    ('go to <http://example.com> now!', 'go to <a href="http://example.com">http://example.com</a> now!'),
                    (' http://www.example.us/path/?name=val', ' <a href="http://www.example.us/path/?name=val">http://www.example.us/path/?name=val</a>'),
                    ('(http://www.example.us/path/?name=val)', '(<a href="http://www.example.us/path/?name=val">http://www.example.us/path/?name=val</a>)'),
                    ('[https://www.example.us/path/?name=val]', '[<a href="https://www.example.us/path/?name=val">https://www.example.us/path/?name=val</a>]'),
                    ('<http://example.us/path/?name=val>', '<a href="http://example.us/path/?name=val">http://example.us/path/?name=val</a>'),
                    ('<http://www.example.us/path/?name=val>', '<a href="http://www.example.us/path/?name=val">http://www.example.us/path/?name=val</a>'),
                    (' www.example.us/path/?name=val', ' <a href="http://www.example.us/path/?name=val">www.example.us/path/?name=val</a>'),
                    ('(www.example.us/path/?name=val)', '(<a href="http://www.example.us/path/?name=val">www.example.us/path/?name=val</a>)'),
                    ('[www.example.us/path/?name=val]', '[<a href="http://www.example.us/path/?name=val">www.example.us/path/?name=val</a>]'),
                    ('<www.example.us/path/?name=val>', '<a href="http://www.example.us/path/?name=val">www.example.us/path/?name=val</a>'),
                    # (' del.icio.us', '<a href="del.icio.us">del.icio.us</a>'),
                    ('me@example.com', '<a href="mailto:me@example.com">me@example.com</a>'),
                    ('m.e@example.com', '<a href="mailto:m.e@example.com">m.e@example.com</a>'),
                    ('(me@example.com)', '(<a href="mailto:me@example.com">me@example.com</a>)'),
                    ('[me@example.com]', '[<a href="mailto:me@example.com">me@example.com</a>]'),
                    ('<me@example.com>', '<a href="mailto:me@example.com">me@example.com</a>'),
                    ('me26@example.com', '<a href="mailto:me26@example.com">me26@example.com</a>'),
                    ('m.e.26@example.com', '<a href="mailto:m.e.26@example.com">m.e.26@example.com</a>'),
                    ('(me26@example.com)', '(<a href="mailto:me26@example.com">me26@example.com</a>)'),
                    ('[me26@example.com]', '[<a href="mailto:me26@example.com">me26@example.com</a>]'),
                    ('<me26@example.com>', '<a href="mailto:me26@example.com">me26@example.com</a>'),
                    ('<p>Contact me26@example.com<p>', '<p>Contact <a href="mailto:me26@example.com">me26@example.com</a><p>'),

                    ("""Copy this link:  https://drive.google.com/open?id=0B_ngEzvayg74TWhvOHIwNEViMTA

When you have arrived at the list, right click on the file of choice and choose download.""",
                        """Copy this link:  <a href="https://drive.google.com/open?id=0B_ngEzvayg74TWhvOHIwNEViMTA">https://drive.google.com/open?id=0B_ngEzvayg74TWhvOHIwNEViMTA</a>

When you have arrived at the list, right click on the file of choice and choose download."""),
                    ("""ordained 1986, abc123@gmail.com

1In 1992 the Smiths established the Far West Bible School""",
                        """ordained 1986, <a href="mailto:abc123@gmail.com">abc123@gmail.com</a>

1In 1992 the Smiths established the Far West Bible School"""),
                    )


class TestNakedURLConverter(unittest.TestCase):
    
    def test_naked_url_converter(self):
        goodCount = totalCount = 0
        for j, (testString, expectedResultString) in enumerate(testData):
            # print(f"\n{j+1:2}/ testString='{testString}'")
            result = fix_naked_urls(testString)
            totalCount += 1
            if result == expectedResultString:
                goodCount += 1
            else:
                print(f"BADBAD! fix_naked_urls wanted '{expectedResultString}'")
                raise Exception(f"Failed to convert naked url: {j+1}/ '{testString}'")

        print(f"\nSuccess rate = {goodCount} / {totalCount}.")
