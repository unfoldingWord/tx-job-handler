import os
from general_tools.font_maps import FONT_FALLBACKS
from general_tools.font_utils import get_font_families_with_fallbacks, get_prod_font_face, get_prod_font_face_url, get_earlyaccess_font_face_url, FONTS_BY_LANG
from general_tools.file_utils import write_file, read_file, load_json_object

if __name__ == "__main__":
  html = ''
  links = {}
  fonts = {}
  if os.path.exists('./links.json'):
    links = load_json_object('./links.json')
  if os.path.exists('./fonts.json'):
    fonts = load_json_object('./fonts.json')
  for lang_code in FONTS_BY_LANG:
    print(lang_code)
    if lang_code not in fonts:
      fonts[lang_code] = get_font_families_with_fallbacks(lang_code)
    for font_family in fonts[lang_code]:
      if font_family in links:
        continue
      if 'Noto' in font_family:
        if get_prod_font_face(font_family):
          href = get_prod_font_face_url(font_family)
        else:
          href = get_earlyaccess_font_face_url(font_family)
        links[font_family] = href
    write_file('./links.json', links, indent=2)
    write_file('./fonts.json', fonts, indent=2)
