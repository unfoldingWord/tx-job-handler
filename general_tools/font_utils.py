import re
import os
from urllib.parse import urlencode
from door43_tools.td_language import TdLanguage
from .url_utils import get_url, download_file
from .font_maps import FONTS_BY_LANG, PRECEDING_FONT_FAMILIES, DEFAULT_FALLBACK


def get_name(lang_code):
    language = TdLanguage.get_language(lang_code)
    if language:
        return language.ang
    else:
        return None


def get_fallbacks_recursive(font_family, exclude=None):
    fallbacks = []
    if not exclude:
        exclude = []
    exclude.append(font_family)
    if font_family in fallbacks:
        for font in fallbacks:
            fallbacks.append(font)
            if font not in exclude:
                fallbacks += get_fallbacks_recursive(font, exclude)
    return fallbacks


def get_fallbacks(font_family):
    fallbacks = get_fallbacks_recursive(font_family)
    fallbacks += DEFAULT_FALLBACK
    return fallbacks


def get_names(lang_code):
    names = [lang_code]
    language = TdLanguage.get_language(lang_code)
    if language:
        for name in [language.ang] + language.alt:
            names.append(name)
            m = re.match(r'^(.*?) *\(([^)]+)\)$', name)
            if m:
                names += m.groups()
            if ', ' in name:
                names += name.split(', ')
    return names


def get_prod_font_face_url(font_family):
    return f'https://fonts.googleapis.com/css2?' + urlencode({'family': font_family}) + ':ital,wght@0,400;0,700;1,400;1,700'


def get_earlyaccess_font_face_url(font_family):
    filename = f"{font_family.lower().replace(',', '').replace(' ', '')}.css"
    return f'https://fonts.googleapis.com/earlyaccess/{filename}'


def get_prod_font_face(font_family):
    url = get_prod_font_face_url(font_family)
    return get_url(url, catch_exception=True)


def get_earlyaccess_font_face(font_family):
    url = get_earlyaccess_font_face_url(font_family)
    return get_url(url, catch_exception=True)


def get_font_families(lang_code):
    if lang_code in FONTS_BY_LANG:
        return FONTS_BY_LANG[lang_code]
    else:
        return None


def get_font_families_with_fallbacks(lang_code):
    font_families = get_font_families(lang_code)
    if font_families:
        if font_families[0] in PRECEDING_FONT_FAMILIES:
            font_families += PRECEDING_FONT_FAMILIES[font_families[0]]
        font_families += get_fallbacks(font_families[-1])
        return font_families
    else:
        return DEFAULT_FALLBACK


def get_font_html(lang_code):
    html = ''
    font_families = get_font_families_with_fallbacks(lang_code)
    for font_family in font_families:
        if 'Noto' in font_family:
            if get_prod_font_face(font_family):
                href = get_prod_font_face_url(font_family)
            else:
                href = get_earlyaccess_font_face_url(font_family)
            html += f"""
<link href="{href}" rel="stylesheet">
"""
    html += f"""
<style>
    :lang({lang_code}) {{ 
        font-family: '{"', '".join(font_families)}'; }}
</style>
"""
    return html


def get_font_html_with_local_fonts(lang_code, html_dir):
    font_families = get_font_families_with_fallbacks(lang_code)
    font_face_html = ''
    fonts_dir = os.path.join(html_dir, 'fonts')
    if not os.path.exists(fonts_dir):
        os.mkdir(fonts_dir)
    for font_family in font_families:
        if 'Noto' in font_family:
            if get_prod_font_face(font_family):
                font_face_css_url = get_prod_font_face_url(font_family)
            else:
                font_face_css_url = get_earlyaccess_font_face_url(font_family)
            font_face_css = get_url(font_face_css_url)
            new_font_face_css = []
            for line in font_face_css.split("\n"):
                m = re.match(r"^(.*) url\(([^)#?]+)(.*)\)(.*)$", line)
                if m:
                    font_url = m.group(2)
                    if font_url.startswith('//'):
                        font_url = f'https:{font_url}'
                    filename = os.path.basename(font_url)
                    filepath = os.path.join(html_dir, 'fonts', filename)
                    if not os.path.exists(filepath):
                        download_file(font_url, filepath)
                    line = f'{m.group(1)} url(fonts/{filename}{m.group(3)}){m.group(4)}'
                new_font_face_css.append(line)
            font_face_html += "\n".join(new_font_face_css)
    html = f"""
<style>
{font_face_html}
    :lang({lang_code}) {{
        font-family: '{"', '".join(font_families)}'; 
    }}
</style>
"""
    return html
