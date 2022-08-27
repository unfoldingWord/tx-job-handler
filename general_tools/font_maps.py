import os
from general_tools.file_utils import load_json_object

# Mappings gathered from here:
#  https://r12a.github.io/scripts (primary site, copied in languages from the "languages using" section of each script)
#  https://www.google.com/get/noto/
#  http://td.unfoldingword.org/uw/languages/
#  https://www.monotype.com/resources/case-studies/more-than-800-languages-in-a-single-typeface-creating-noto-for-google

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

noto_font_list_file = os.path.join(SCRIPT_DIR, 'noto_font_list.json')
font_fallbacks_file = os.path.join(SCRIPT_DIR, 'font_fallbacks.json')
font_by_lang_file = os.path.join(SCRIPT_DIR, 'fonts_by_lang.json')

DEFAULT_FALLBACK = ['Noto Sans', 'sans-serif']
FONT_FALLBACKS = load_json_object(font_fallbacks_file)
NOTO_FONT_LIST = load_json_object(noto_font_list_file)
FONTS_BY_LANG = load_json_object(font_by_lang_file)

# Some font-families need "Noto Sans" in front of it so Latin letters & numbers will show in Noto, such as CJK
PRECEDING_FONT_FAMILIES = {
    'Noto Sans JC': ['Noto Sans'],
    'Noto Sans SC': ['Noto Sans'],
    'Noto Sans TC': ['Noto Sans'],
}
