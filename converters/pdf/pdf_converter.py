#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
Class for any resource PDF converter
"""
import os
import re
import logging
import markdown2
import string
import yaml
import shutil
import general_tools.html_tools as html_tools
import googletrans
import json
from collections import Counter
from cssutils import parseStyle
from cssutils.css import CSSStyleDeclaration
from bs4 import BeautifulSoup
from abc import abstractmethod
from weasyprint import HTML
from urllib.parse import urlsplit, urlunsplit, urlparse
from general_tools.font_utils import get_font_html_with_local_fonts
from general_tools.file_utils import write_file, read_file, load_json_object, unzip
from general_tools.url_utils import download_file, get_url
from .resource import Resource, Resources, DEFAULT_REF, DEFAULT_OWNER, OWNERS
from .rc_link import ResourceContainerLink
from converters.converter import Converter
from door43_tools.dcs_api import DcsApi
from door43_tools.bible_books import BOOK_NUMBERS
from door43_tools.subjects import SUBJECT_ALIASES, REQUIRED_RESOURCES, HEBREW_OLD_TESTAMENT, GREEK_NEW_TESTAMENT, ALIGNED_BIBLE, BIBLE, \
    OPEN_BIBLE_STORIES, TRANSLATION_ACADEMY, TRANSLATION_WORDS
from app_settings.app_settings import AppSettings

STAGE_PROD = 'prod'
STAGE_PREPROD = 'preprod'
STAGE_DRAFT = 'draft'
STAGE_LATEST = 'latest'

OT_OL_BIBLE_ID = 'uhb'
OT_OL_LANG_CODE = 'hbo'
NT_OL_BIBLE_ID = 'ugnt'
NT_OL_LANG_CODE = 'el-x-koine'

DEFAULT_LANG_CODE = 'en'
DEFAULT_STAGE = 'prod'
DEFAULT_ULT_ID = 'ult'
DEFAULT_UST_ID = 'ust'

TW_CATS = ['kt', 'names', 'other']

APPENDIX_LINKING_LEVEL = 1
APPENDIX_RESOURCES = ['ta', 'tw']
CONTRIBUTORS_TO_HIDE = ['ugnt', 'uhb']


class PdfConverter(Converter):
    my_subject = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.resources = Resources()
        self.relation_resources = Resources()
        self.project_id = None

        if not os.path.isdir(self.source_dir):
            self.log.error(f"No such folder: {self.source_dir}")
            return

        self.wp_logger = None
        self.wp_logger_handler = None
        self.output_logger_handler = None

        self.images_dir = None

        self.reinit()

        self.locale = {}
        self.pdf_converters_dir = os.path.dirname(os.path.realpath(__file__))
        self.style_sheets = []
        self._font_html = ''

        self.logger_stream_handler = None
        self.api = DcsApi(self.dcs_domain, debug=self.debug_mode)

    def reinit(self):
        self._project = None
        self.errors = {}
        self.bad_highlights = {}
        self.rcs = {}
        self.appendix_rcs = {}
        self.all_rcs = {}

    def __del__(self):
        self.close_loggers()

    @property
    def owner(self):
        if self.main_resource:
            return self.main_resource.owner
        else:
            return self._repo_owner or DEFAULT_OWNER

    @property
    def repo_name(self):
        return self._repo_name or self.source_dir.split(os.path.sep)[-1]

    @property
    def resource_name(self):
        if self.main_resource:
            return self.main_resource.identifier
        else:
            return SUBJECT_ALIASES[self.my_subject][0]

    @property
    def stage(self):
        if self.main_resource:
            return self.main_resource.stage
        else:
            return DEFAULT_STAGE

    @property
    def main_resource(self):
        if self.resources:
            return self.resources.main
        else:
            return None

    @property
    def name(self):
        return self.resource_name

    @property
    def title(self):
        return self.main_resource.title

    @property
    def simple_title(self):
        return self.main_resource.simple_title

    @property
    def toc_title(self):
        return f'<h1>{self.translate("table_of_contents")}</h1>'

    @property
    def version(self):
        return self.main_resource.version

    @property
    def file_project_and_ref(self):
        return f'{self.file_project_id}_{self.ref}'

    @property
    def file_project_and_unique_ref(self):
        return f'{self.file_project_id}_{self.ref}'

    @property
    def file_ref_id(self):
        return f'{self.file_base_id}_{self.ref}'

    @property
    def file_project_id(self):
        return f'{self.file_base_id}{self.file_id_project_str}'

    @property
    def file_base_id(self):
        return f'{self.language_id}_{self.name}'

    @property
    def file_id_project_str(self):
        if self.project_id in BOOK_NUMBERS:
            return f'_{self.book_number_padded}-{self.project_id.upper()}'
        elif self.project_id and len(self.projects) > 1:
            return f'_{self.project_id}'
        else:
            return ''

    @property
    def ref(self):
        if not self.main_resource:
            if not self._repo_ref:
                return DEFAULT_REF
            return self._repo_ref
        elif self.version != self.main_resource.ref and f'v{self.version}' != self.main_resource.ref:
            return f'{self._repo_ref}_{self.main_resource.last_commit_sha}'
        else:
            return f'v{self.main_resource.version}'

    @property
    def language_id(self):
        return self.main_resource.manifest['dublin_core']['language']['identifier']

    @property
    def projects(self):
        return self.main_resource.projects

    @property
    def project(self):
        if self.project_id:
            if not self._project or self.project_id != self._project['identifier']:
                self._project = self.main_resource.find_project(self.project_id)
                if not self._project:
                    self.log.error(f'Project not found: {self.project_id}')
                    exit(1)
            return self._project

    @property
    def project_title(self):
        return self.get_project_title(self.project)

    def get_project_title(self, project):
        if not project:
            project = self.project
        if not project or len(self.projects) == 1:
            return ''
        if self.main_resource.title in project['title']:
            return project['title'].replace(f' {self.main_resource.title}', '')
        else:
            return project['title'].replace(f' {self.main_resource.simple_title}', '')

    @property
    def html_file(self):
        return os.path.join(self.output_dir, f'{self.file_project_and_ref}.html')

    @property
    def pdf_file(self):
        return os.path.join(self.output_dir, f'{self.file_project_and_ref}.pdf')

    @property
    def errors_file(self):
        return os.path.join(self.output_dir, f'{self.file_project_and_ref}_errors.html')

    @property
    def bad_hightlights_file(self):
        return os.path.join(self.output_dir, f'{self.file_project_and_ref}_bad_highlights.html')

    @property
    def font_html(self):
        if not self._font_html:
            self._font_html = get_font_html_with_local_fonts(self.language_id, self.output_dir)
        return self._font_html

    @property
    def language_direction(self):
        if self.main_resource and self.main_resource.language_direction:
            return self.main_resource.language_direction
        else:
            return 'auto'

    @property
    def head_html(self):
        html = f'''{self.font_html}
        <meta name="keywords" content={json.dumps(f'{self.main_resource.identifier},{self.main_resource.type},{self.language_id},{self.main_resource.language_title},unfoldingWord')} />
        <meta name="author" content={json.dumps(self.owner)} />
        <meta name="dcterms.created" content={json.dumps(self.main_resource.issued)} />
'''
        return html

    @property
    def book_number(self):
        if self.project_id and self.project_id in BOOK_NUMBERS:
            return int(BOOK_NUMBERS[self.project_id])
        else:
            return 0

    @property
    def book_number_padded(self):
        return self.pad(self.book_number, 'book')

    @property
    def ol_bible_id(self):
        if self.book_number >= 40:
            return NT_OL_BIBLE_ID
        else:
            return OT_OL_BIBLE_ID

    @property
    def ol_lang_code(self):
        if self.book_number >= 40:
            return NT_OL_LANG_CODE
        else:
            return OT_OL_LANG_CODE

    def pad(self, num, project_id=None):
        if not project_id:
            project_id = self.project_id
        if project_id == 'psa':
            return str(num).zfill(3)
        else:
            return str(num).zfill(2)

    def add_style_sheet(self, style_sheet):
        if style_sheet not in self.style_sheets:
            self.log.info(f'Adding CSS style sheet: {style_sheet}')
            self.style_sheets.append(style_sheet)

    def translate(self, key):
        if not self.locale:
            locale_file = os.path.join(self.pdf_converters_dir, 'locale', f'{self.language_id}.json')
            if os.path.isfile(locale_file):
                self.locale = load_json_object(locale_file)
            else:
                self.log.warning(f'No locale file for {self.language_id}. Using English (en) with Google translate')
                self.locale = self.get_locale_with_google()
        if key not in self.locale['translations']:
            self.log.error(f"No translation for `{key}`")
            exit(1)
        return self.locale['translations'][key]

    def determine_google_language(self):
        if self.language_id in googletrans.LANGUAGES:
            return self.language_id
        else:
            sample_text = self.get_sample_text()
            if sample_text:
                translator = googletrans.Translator()
                detect = translator.detect(sample_text)
                if detect and detect.lang:
                    return detect.lang
                else:
                    return None
            else:
                return None

    def get_locale_with_google(self):
        en_locale_file = os.path.join(self.pdf_converters_dir, 'locale', 'en.json')
        locale = load_json_object(en_locale_file)
        google_lang = self.determine_google_language()
        locale_file = os.path.join(self.pdf_converters_dir, 'locale', f'{self.language_id}.json')
        if os.path.exists(locale_file):
            return load_json_object(locale_file)
        locale['source'] = locale['target']
        locale['target'] = self.language_id
        locale['translator'] = 'google'
        locale['google_lang'] = google_lang
        translator = googletrans.Translator()
        for key, value in locale['translations'].items():
            translation = translator.translate(value, src='en', dest=google_lang)
            if translation and translation.text:
                locale['translations'][key] = translation.text
        write_file(locale_file, json.dumps(locale, sort_keys=True, indent=2, ensure_ascii=False))
        return locale

    @staticmethod
    def create_rc(rc_link, article='', title=None, linking_level=0, article_id=None):
        rc = ResourceContainerLink(rc_link, article=article, title=title, linking_level=linking_level,
                                   article_id=article_id)
        return rc

    def add_rc(self, rc_link, article='', title=None, linking_level=0, article_id=None):
        rc = self.create_rc(rc_link, article=article, title=title, linking_level=linking_level, article_id=article_id)
        self.rcs[rc.rc_link] = rc
        return rc

    def add_appendix_rc(self, rc_link, article='', title=None, linking_level=0):
        rc = self.create_rc(rc_link, article=article, title=title, linking_level=linking_level)
        self.appendix_rcs[rc.rc_link] = rc
        return rc

    def add_error_message(self, source_rc, bad_rc_link, message=None):
        if source_rc:
            if source_rc.rc_link not in self.errors:
                self.errors[source_rc.rc_link] = {
                    'source_rc': source_rc,
                    'errors': {}
                }
            if bad_rc_link not in self.errors[source_rc.rc_link] or message:
                self.errors[source_rc.rc_link]['errors'][bad_rc_link] = message

    def add_bad_highlight(self, source_rc, text, rc_link, phrase, message=None):
        if source_rc:
            if source_rc.rc_link not in self.bad_highlights:
                self.bad_highlights[source_rc.rc_link] = {
                    'source_rc': source_rc,
                    'text': text,
                    'highlights': {}
                }
            self.bad_highlights[source_rc.rc_link]['highlights'][rc_link] = {
                'phrase': phrase,
                'fix': message
            }

    def upload_file(self, filepath) -> None:
        """
        Uploads the given file or puts it locally
        """
        #AppSettings.logger.debug("converter.upload_archive()")
        if self.cdn_file_key and os.path.isdir(os.path.dirname(self.cdn_file_key)):
            #AppSettings.logger.debug("converter.upload_archive() doing copy")
            copy(self.output_zip_file, self.cdn_file_key)
        elif os.path.isdir(os.path.sep + AppSettings.cdn_bucket_name):
            file_path = os.path.join(os.path.sep + AppSettings.cdn_bucket_name, self.cdn_file_key)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            copy(self.output_zip_file, self.cdn_file_key)
        elif AppSettings.cdn_s3_handler():
            #AppSettings.logger.debug("converter.upload_archive() using S3 handler")
            AppSettings.cdn_s3_handler().upload_file(self.output_zip_file, self.cdn_file_key, cache_time=0)


    def upload_pdf_and_json_to_cdn(self):
        #if AppSettings.
        #self.pdf_file
        #self.loginfo(f"PDF Converter uploading PDF to {self.cdn_file_key} …")
        #            if self.cdn_file_key:
        #                self.upload_archive()
        #                AppSettings.logger.debug(f"Uploaded converted files (using '{self.cdn_file_key}').")
        #            else:
        #                AppSettings.logger.debug("No converted file upload requested.")
        pass


    def finish_up(self):
        self.close_loggers()

    def setup_images_dir(self):
        self.log.info('Setting up directories...')
        self.images_dir = os.path.join(self.output_dir, 'images')
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)

    def setup_style_sheets(self):
        self.add_style_sheet('css/style.css')
        possible_styles = {
            'lang': self.language_id,
            'resource': self.name,
            'lang_resource': f'{self.language_id}_{self.resource_name}'
        }
        for directory, style in possible_styles.items():
            style_file = f'css/{directory}/{style}_style.css'
            style_path = os.path.join(self.pdf_converters_dir, style_file)
            if os.path.exists(style_path):
                self.add_style_sheet(style_file)
        css_dir = os.path.join(self.output_dir, 'css')
        if not os.path.exists(css_dir):
            os.makedirs(css_dir)
        for style_file in self.style_sheets:
            new_style_file = os.path.join(self.output_dir, style_file)
            new_style_file_dir = os.path.dirname(new_style_file)
            if not os.path.exists(new_style_file_dir):
                os.makedirs(new_style_file_dir)
            shutil.copy(os.path.join(self.pdf_converters_dir, style_file), new_style_file)

    def setup_loggers(self):
        output_log = os.path.join(self.output_dir, f'{self.file_project_and_unique_ref}_output.log')
        if os.path.exists(output_log):
            os.unlink(output_log)
        self.output_logger_handler = logging.FileHandler(output_log)
        if self.debug_mode:
            self.output_logger_handler.setLevel(logging.DEBUG)
        else:
            self.output_logger_handler.setLevel(logging.INFO)
        AppSettings.logger.addHandler(self.output_logger_handler)
        self.log.info(f'Logging output to {output_log}')

        self.wp_logger = logging.getLogger('weasyprint')
        if self.debug_mode:
            self.wp_logger.setLevel(logging.DEBUG)
        else:
            self.wp_logger.setLevel(logging.WARNING)
        weasyprint_log = os.path.join(self.output_dir, f'{self.file_project_and_unique_ref}_weasyprint.log')
        if os.path.exists(weasyprint_log):
            os.unlink(weasyprint_log)
        self.wp_logger_handler = logging.FileHandler(weasyprint_log)
        if self.debug_mode:
            self.wp_logger_handler.setLevel(logging.DEBUG)
        else:
            self.wp_logger_handler.setLevel(logging.INFO)
        self.wp_logger.addHandler(self.wp_logger_handler)
        self.log.info(f'Logging WeasyPrint output to {weasyprint_log}')

    def close_loggers(self):
       if hasattr(self, 'wp_logger_handler') and self.wp_logger_handler:
           self.wp_logger.removeHandler(self.wp_logger_handler)
           self.wp_logger_handler.close()
       if hasattr(self, 'output_logger_handler') and self.output_logger_handler:
           AppSettings.logger.removeHandler(self.output_logger_handler)
           self.output_logger_handler.close()

    def generate_all_files(self):
        for project in self.main_resource.projects:
            if not self.project_ids or project['identifier'] in self.project_ids:
                self.reinit()
                self.project_id = project['identifier']
                self.generate_html_file()
                self.generate_pdf_file()

    def generate_html_file(self):
        if not os.path.exists(self.html_file) or self.debug_mode:
            self.log.info(f'Creating HTML file for {self.file_project_and_ref}...')

            self.log.info('Generating cover page HTML...')
            cover_html = self.get_cover_html()

            self.log.info('Generating license page HTML...')
            license_html = self.get_license_html()

            self.log.info('Generating body HTML...')
            body_html = self.get_body_html()
            body_html = self.add_fit_to_page_wrappers(body_html)
            if not body_html:
                return False
            write_file("/tmp/out.html", body_html)
            self.log.info('Generating appendix RCs...')
            self.get_appendix_rcs()
            self.all_rcs = {**self.rcs, **self.appendix_rcs}
            if 'ta' in self.resources:
                self.log.info('Generating UTA appendix HTML...')
                body_html += self.get_appendix_html(self.resources['ta'])
            if 'tw' in self.resources:
                self.log.info('Generating UTW appendix HTML...')
                body_html += self.get_appendix_html(self.resources['tw'])
            self.log.info('Fixing links in body HTML...')
            body_html = self.fix_links(body_html)
            body_html = self._fix_links(body_html)
            self.log.info('Replacing RC links in body HTML...')
            body_html = self.replace_rc_links(body_html)
            self.log.info('Generating Contributors HTML...')
            body_html += self.get_contributors_html()
            self.log.info('Generating TOC HTML...')
            body_html, toc_html = self.get_toc_html(body_html)
            self.log.info('Done generating TOC HTML.')

            self.log.info('Populating HTML template...')
            with open(os.path.join(self.pdf_converters_dir, 'templates', 'pdf_template.html')) as template_file:
                html_template = string.Template(template_file.read())
            title = f'{self.title} - v{self.version}'

            self.log.info('Piecing together the HTML file...')
            body_html = '\n'.join([cover_html, license_html, toc_html, body_html])
            body_html = self.download_all_images(body_html)
            head = '\n'.join([f'<link href="{style}" rel="stylesheet">' for style in self.style_sheets])
            head += self.head_html
            html = html_template.safe_substitute(lang=self.language_id, dir=self.language_direction, title=title,
                                                 head=head, body=body_html)
            write_file(self.html_file, html)
            self.save_errors_html()
            self.save_bad_highlights_html()
            self.log.info('Generated HTML file.')
        else:
            self.log.info(f'HTML file {self.html_file} is already there. Not generating. Use -r to force regeneration.')

    @classmethod
    def add_fit_to_page_wrappers(cls, html):
        if 'fit-to-page' not in html:
            return html
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.find_all(class_="fit-to-page")
        if not elements:
            return html
        for i, element in enumerate(elements):
            span = soup.new_tag("span", id=f"fit-to-page-{i+1}")
            for content in reversed(element.contents):
                span.insert(0, content.extract())
            element.append(span)
        return str(soup)

    def generate_pdf_file(self):
        if not os.path.exists(self.html_file):
            self.log.error('No HTML to process. Not generating PDF.')
            return
        if not os.path.exists(self.pdf_file) or self.debug_mode:
            self.log.info(f'Generating PDF file {self.pdf_file}...')
            # Convert HTML to PDF with weasyprint
            base_url = f'file://{self.output_dir}'
            all_pages_fitted = False
            soup = BeautifulSoup(read_file(self.html_file), 'html.parser')
            all_pages_fit = False
            doc = None
            tries = 0
            while not all_pages_fit and tries < 10:
                all_pages_fit = True
                tries += 1
                doc = HTML(string=str(soup), base_url=base_url).render()
                for page_idx, page in enumerate(doc.pages):
                    for anchor in page.anchors:
                        if anchor.startswith('fit-to-page-'):
                            if anchor not in doc.pages[page_idx-1].anchors:
                                continue
                            all_pages_fit = False
                            diff = 0.05
                            if page.anchors[anchor][1] > 90:
                                diff = 0.1
                            element = soup.find(id=anchor)
                            if not element:
                                continue
                            if element.has_attr('style'):
                                style = parseStyle(element['style'])
                            else:
                                style = CSSStyleDeclaration()
                            if 'font-size' in style and style['font-size'] and style['font-size'].endswith('em'):
                                font_size = float(style['font-size'].removesuffix('em'))
                            else:
                                font_size = 1.0
                            font_size_str = f'{"%.2f"%(font_size - diff)}em'
                            style['font-size'] = font_size_str
                            css = style.cssText
                            element['style'] = css
                            self.log.info(f'RESIZING {anchor} to {font_size_str}... ({diff}, {page.anchors[anchor]})')
                    write_file(os.path.join(self.output_dir, f'{self.file_project_and_ref}_resized.html'),
                               str(soup))
            if doc:
                doc.write_pdf(self.pdf_file)
                self.log.info('Generated PDF file.')
                self.log.info(f'PDF file located at {self.pdf_file}')
        else:
            self.log.info(
                f'PDF file {self.pdf_file} is already there. Not generating. Use -r to force regeneration.')

    def save_errors_html(self):
        if not self.errors:
            self.log.info('No errors for this version!')
            return

        errors_html = '''
<h1>ERRORS</h1>
<ul>
'''
        for source_rc_link in sorted(self.errors.keys()):
            source_rc = self.errors[source_rc_link]['source_rc']
            errors = self.errors[source_rc_link]['errors']
            for rc_link in sorted(errors.keys()):
                errors_html += f'''
    <li>
        In article 
        <a href="{os.path.basename(self.html_file)}#{source_rc.article_id}" title="See in the HTML" target="{self.name}-html">
            {source_rc_link}
        </a>:
'''
                if rc_link.startswith('rc://'):
                    errors_html += f'''
        BAD RC LINK: `{rc_link}`'''
                else:
                    errors_html += f'''
        {rc_link}'''
                if errors[rc_link]:
                    message = errors[rc_link]
                else:
                    message = 'linked article not found'
                if '\n' in message:
                    message = f'<br/><pre>{message}</pre>'
                errors_html += f': {message}'
                errors_html += f'''
    </li>
'''
        errors_html += '''
</ul>
'''
        with open(os.path.join(self.pdf_converters_dir, 'templates/pdf_template.html')) as template_file:
            html_template = string.Template(template_file.read())
        html = html_template.safe_substitute(title=f'ERRORS FOR {self.file_project_and_unique_ref}',
                                             lang=self.language_id, body=errors_html, head=self.head_html, dir='ltr')
        write_file(self.errors_file, html)

        self.log.info(f'ERRORS HTML file can be found at {self.errors_file}')

    def save_bad_highlights_html(self):
        if not self.bad_highlights:
            self.log.info('No bad highlights for this version!')
            return

        bad_highlights_html = f'''
<h1>BAD HIGHLIGHTS:</h1>
<h2>(i.e. phrases not found in text as written)</h2>
<ul>
'''
        for source_rc_link in sorted(self.bad_highlights.keys()):
            source_rc = self.bad_highlights[source_rc_link]['source_rc']
            bad_highlights_html += f'''
    <li>
        <a href="{os.path.basename(self.html_file)}#{source_rc.article_id}" title="See in the HTML" target="{self.name}-html">
            {source_rc.rc_link}
        </a>:
        <br/>
        {self.bad_highlights[source_rc_link]['text']}
        <br/>
        <ul>
'''
            for target_rc_link in self.bad_highlights[source_rc_link]['highlights'].keys():
                target = self.bad_highlights[source_rc_link]['highlights'][target_rc_link]
                bad_highlights_html += f'''
            <li>
                {target_rc_link}: {target['phrase']} <em>(phrase to match)</em>
'''
                if target['fix']:
                    bad_highlights_html += f'''
                <br/>
                {target['fix']} <em>(QUOTE ISSUE - closest phrase found in text)</em>
'''
                bad_highlights_html += f'''
            </li>
'''
            bad_highlights_html += '''
        </ul>
    </li>'''
        bad_highlights_html += '''
</ul>
'''
        with open(os.path.join(self.pdf_converters_dir, 'templates/pdf_template.html')) as template_file:
            html_template = string.Template(template_file.read())
        html = html_template.safe_substitute(title=f'BAD HIGHLIGHTS FOR {self.file_project_and_unique_ref}',
                                             body=bad_highlights_html, lang=self.language_id, head=self.head_html,
                                             dir='ltr')
        write_file(self.bad_hightlights_file, html)
        self.log.info(f'BAD HIGHLIGHTS file can be found at {self.bad_hightlights_file}')

    def setup_resource(self, resource):
        self.log.info(f'Setting up resource {resource.identifier}...')
        self.download_resource(resource)
        self.log.info(f'  ...set up to use `{resource.repo_name}`: `{resource.ref}`')

    def setup_resources(self):
        if not self.manifest_dict:
            self.log.error('No manifest.yaml file in repo')
            return
        self.log.info('Setting up resources...')
        # Setup Main Resource
        repo_dir = None
        if self.my_subject == OPEN_BIBLE_STORIES and not os.path.exists(os.path.join(self.source_dir, 'content')):
            repo_dir = self.source_dir # Use the massaged OBS dir from door43-job-handler to handle tS repos as well
        zipball_url = self.repo_data_url
        if not self.repo_data_url.endswith('.zip'):
            zipball_url = self.repo_data_url.replace('/commit/', '/archive/') + '.zip'
        else:
            zipball_url = self.repo_data_url
        resource = Resource(subject=self.my_subject, repo_name=self.repo_name, owner=self.owner, ref=self.ref,
                            zipball_url=zipball_url, api=self.api, repo_dir=repo_dir)
        self.resources[resource.identifier] = resource

        # First process relation resource
        self.process_relation_resources()

        # Next process require resources
        for subject in REQUIRED_RESOURCES[self.my_subject]:
            resource = self.find_relation_resource(subject)
            if not resource or resource.identifier in self.resources:
                resource = self.find_resource(subject=subject)
            if resource:
                self.resources[resource.identifier] = resource

        # Now setup the resources we have gathered
        for resource in self.resources.values():
            self.setup_resource(resource)

    def already_have_subject(self, subject):
        count = 0
        needed = Counter(REQUIRED_RESOURCES[self.my_subject])[subject]
        for resource in self.resources.values():
            if resource.subject == subject:
                count += 1
        return count >= needed

    def find_relation_resource(self, subject):
        for resource in self.relation_resources.values():
            if (resource.subject == subject or (subject == BIBLE and resource.subject == ALIGNED_BIBLE)) and resource.identifier not in self.resources:
                return resource
        return None

    def download_all_images(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        for img in soup.find_all('img'):
            if img['src'].startswith('http'):
                u = urlsplit(img['src'])._replace(query="", fragment="")
                url = urlunsplit(u)
                file_path = f'images/{u.netloc}{u.path}'
                full_file_path = os.path.join(self.output_dir, file_path)
                if not os.path.exists(full_file_path):
                    os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
                    self.log.info(f'Downloading {url} to {full_file_path}...')
                    download_file(url, full_file_path)
                img['src'] = file_path
        return str(soup)

    @abstractmethod
    def get_body_html(self):
        pass

    @abstractmethod
    def get_sample_text(self):
        pass

    def get_rc_by_article_id(self, article_id):
        for rc_link, rc in self.all_rcs.items():
            if rc.article_id == article_id:
                return rc

    def get_toc_html(self, body_html):
        toc_html = f'''
<article id="contents">
    {self.toc_title}
'''
        prev_toc_level = 0
        prev_header_level = 0
        soup = BeautifulSoup(body_html, 'html.parser')
        header_titles = [None, None, None, None, None, None]
        headers = soup.find_all(re.compile(r'^h\d'), {'class': 'section-header'})
        for header in headers:
            if header.get('id'):
                article_id = header.get('id')
            else:
                parent = header.find_parent(['article', 'section'])
                article_id = parent.get('id')

            if article_id:
                is_toc = not header.has_attr('class') or 'no-toc' not in header['class']
                is_header = not header.has_attr('class') or 'no-header' not in header['class']

                if not is_toc and not is_header:
                    continue

                toc_level = int(header.get('toc-level', header.name[1]))
                header_level = int(header.get('header-level', toc_level))

                # Get the proper TOC title and add it to the TOC string with an open <li>
                if is_toc:
                    if toc_level > prev_toc_level:
                        for level in range(prev_toc_level, toc_level):
                            toc_html += '\n<ul>\n'
                    elif toc_level < prev_toc_level:
                        toc_html += '\n</li>\n'  # close current item's open <li> tag
                        for level in range(prev_toc_level, toc_level, -1):
                            toc_html += '</ul>\n</li>\n'
                    elif prev_toc_level > 0:
                        toc_html += '\n</li>\n'

                    if header.has_attr('toc_title'):
                        toc_title = header['toc_title']
                    else:
                        rc = self.get_rc_by_article_id(article_id)
                        if rc:
                            toc_title = rc.toc_title
                        else:
                            toc_title = header.text
                    toc_html += f'<li><a href="#{article_id}"><span>{toc_title}</span></a>\n'
                    prev_toc_level = toc_level

                # Get the proper Heading title and add a header tag
                if is_header:
                    if header_level > prev_header_level:
                        for level in range(prev_header_level, header_level):
                            header_titles[level] = None
                    elif header_level < prev_header_level:
                        for level in range(prev_header_level, header_level, -1):
                            header_titles[level - 1] = None

                    if header.has_attr('header_title'):
                        header_title = header['header_title']
                    else:
                        rc = self.get_rc_by_article_id(article_id)
                        if rc:
                            header_title = rc.toc_title
                        else:
                            header_title = header.text
                    header_titles[header_level - 1] = header_title

                    right_header_string = ' :: '.join(filter(None, header_titles[1:header_level]))
                    if len(right_header_string):
                        right_header_tag = soup.new_tag('span', **{'class': 'hidden header-right'})
                        right_header_tag.string = right_header_string
                        header.insert_before(right_header_tag)
                    prev_header_level = header_level

        for level in range(prev_toc_level, 0, -1):
            toc_html += '</li>\n</ul>\n'
        toc_html += '</article>'

        return [str(soup), toc_html]

    def get_cover_html(self):
        version_str = f'{self.translate("version")} {self.version}'
        if self.main_resource.ref != {self.version} and self.main_resource.ref != f'v{self.version}':
            version_str += f' ({DEFAULT_REF} - {self.main_resource.last_commit_sha})'
        if self.project_id and self.project_title:
            project_title_html = f'<h2 class="cover-project">{self.project_title}</h2>'
            version_title_html = f'<h3 class="cover-version">{version_str}</h3>'
        else:
            project_title_html = ''
            version_title_html = f'<h2 class="cover-version">{version_str}</h2>'
        cover_html = f'''
<article id="main-cover" class="cover">
    <img src="{self.main_resource.logo_url}" alt="{self.name.upper()}"/>
    <h1 id="cover-title">{self.title}</h1>
    {project_title_html}
    {version_title_html}
    <h4 class="cover-lang">[{self.language_id}]</h4>
</article>
'''
        return cover_html

    def get_license_html(self):
        license_html = f'''
<article id="copyrights-and-license">
    <div id="copyrights">
        <h1>{self.translate('copyrights_and_licensing')}</h1>
'''
        for resource_name, resource in self.resources.items():
            if not resource.manifest:
                continue
            title = resource.title
            version = resource.version
            publisher = resource.publisher
            issued = resource.issued

            version_str = version
            # if resource.ref == DEFAULT_REF:
            #     version_str += f' ({DEFAULT_REF} - {resource.last_commit_sha})'
            #     issued = f'{resource.last_commit_date} (last commit)'
              
            license_html += f'''
        <div class="resource-info">
          <div class="resource-title"><strong>{title}</strong></div>
          <div class="resource-date"><strong>{self.translate('date')}:</strong> {issued}</div>
          <div class="resource-version"><strong>{self.translate('version')}:</strong> {version_str}</div>
          <div class="resource-publisher"><strong>{self.translate('published_by')}:</strong> {publisher}</div>
        </div>
    </div>
    <div id="license">
'''
        license_file = os.path.join(self.main_resource.repo_dir, 'LICENSE.md')
        if os.path.exists(license_file):
            license_html += markdown2.markdown_path(license_file)
        else:
            license_html += markdown2.markdown(get_url('https://raw.githubusercontent.com/unfoldingWord/dcs/master/options/license/CC-BY-SA-4.0.md'))
        license_html += '''
    </div>
</article>
'''
        return license_html

    def get_contributors_html(self):
        contributors_html = '''
<section id="contributors" class="no-header">
'''
        for idx, resource_name \
                in enumerate(self.resources.keys()):
            resource = self.resources[resource_name]
            if not resource.manifest or not resource.contributors or \
                    resource_name in CONTRIBUTORS_TO_HIDE:
                continue
            contributors = resource.contributors
            contributors_list_classes = 'contributors-list'
            if len(contributors) > 10:
                contributors_list_classes += ' more-than-ten'
            elif len(contributors) > 4:
                contributors_list_classes += ' more-than-four'
            contributors_html += f'<div class="{contributors_list_classes}">'
            if idx == 0:
                contributors_html += f'<h1 class="section-header">{self.translate("contributors")}</h1>'
            if len(self.resources) > 1:
                contributors_html += f'<h2 id="{self.language_id}-{resource_name}-contributors" class="section-header">{resource.title} {self.translate("contributors")}</h2>'
            for contributor in contributors:
                contributors_html += f'<div class="contributor">{contributor}</div>'
            contributors_html += '</div>'
        contributors_html += '''
</section>
'''
        return contributors_html

    def replace(self, m):
        before = m.group(1)
        rc_link = m.group(2)
        after = m.group(3)
        if rc_link not in self.all_rcs:
            return m.group()
        rc = self.all_rcs[rc_link]
        if (before == '[[' and after == ']]') or (before == '(' and after == ')') or before == ' ' \
                or (before == '>' and after == '<'):
            return f'<a href="#{rc.article_id}">{rc.title}</a>'
        if (before == '"' and after == '"') or (before == "'" and after == "'"):
            return f'#{rc.article_id}'
        self.log.error(f'FOUND SOME MALFORMED RC LINKS: {m.group()}')
        return m.group()

    def replace_rc_links(self, text):
        soup = BeautifulSoup(text, 'html.parser')
        rc_pattern = 'rc://[/A-Za-z0-9*_-]+'
        rc_regex = re.compile(rc_pattern)

        # Find anchor tags with an href of an rc link
        anchors_with_rc = soup.find_all('a', href=rc_regex)
        for anchor in anchors_with_rc:
            href_rc_link = anchor['href']
            if href_rc_link in self.all_rcs and self.all_rcs[href_rc_link].linking_level <= APPENDIX_LINKING_LEVEL:
                href_rc = self.all_rcs[href_rc_link]
                anchor['href'] = f'#{href_rc.article_id}'
            else:
                anchor.replace_with_children()

        # Find text either [[rc://...]] links or rc://... links and make them anchor elements
        text_with_bracketed_rcs = soup(text=rc_regex)
        for element_text in text_with_bracketed_rcs:
            parts = re.split(rf'(\[*{rc_pattern}]*)', element_text)
            last_part = soup.new_string(parts[0])
            element_text.replace_with(last_part)
            for part in parts[1:]:
                if not re.search(rc_regex, part):
                    part = soup.new_string(part)
                else:
                    rc_link = part.strip('[]')
                    if rc_link in self.all_rcs and self.all_rcs[rc_link].linking_level <= APPENDIX_LINKING_LEVEL:
                        part = BeautifulSoup(f'<a href="#{self.all_rcs[rc_link].article_id}">{self.all_rcs[rc_link].title}</a>',
                                             'html.parser').find('a')
                    else:
                        part = soup.new_string(part)
                last_part.insert_after(part)
                last_part = part

        return str(soup)

    @staticmethod
    def _fix_links(html):
        # Change [[http.*]] to <a href="http\1">http\1</a>
        html = re.sub(r'\[\[http([^]]+)]]', r'<a href="http\1">http\1</a>', html, flags=re.IGNORECASE)

        # convert URLs to links if not already
        html = re.sub(r'([^">])((http|https|ftp)://[A-Za-z0-9/?&_.:=#-]+[A-Za-z0-9/?&_:=#-])',
                      r'\1<a href="\2">\2</a>', html, flags=re.IGNORECASE)

        # URLS wth just www at the start, no http
        html = re.sub(r'([^/])(www\.[A-Za-z0-9/?&_.:=#-]+[A-Za-z0-9/?&_:=#-])', r'\1<a href="http://\2">\2</a>',
                      html, flags=re.IGNORECASE)

        return html

    def fix_links(self, html):
        # can be implemented by child class
        return html

    def get_appendix_rcs(self):
        for rc_link, rc in self.rcs.items():
            self.crawl_ta_tw_deep_linking(rc)

    def crawl_ta_tw_deep_linking(self, source_rc: ResourceContainerLink):
        if not source_rc or not source_rc.article:
            return
        self.log.info(f'Crawling {source_rc.rc_link} (level: {source_rc.linking_level})...')
        # get all rc links. the "?:" in the regex means to not leave the (ta|tw) match in the result
        rc_links = re.findall(r'rc://[A-Z0-9_*-]+/(?:ta|tw)/[A-Z0-9/_*-]+', source_rc.article, flags=re.IGNORECASE | re.MULTILINE)
        for rc_link in rc_links:
            if rc_link.count('/') < 5 or rc_link.endswith('/'):
                self.add_error_message(source_rc, rc_link, "Malformed rc link")
                continue
            if rc_link in self.rcs or rc_link in self.appendix_rcs:
                rc = self.rcs[rc_link] if rc_link in self.rcs else self.appendix_rcs[rc_link]
                if rc.linking_level > source_rc.linking_level + 1:
                    rc.linking_level = source_rc.linking_level + 1
                already_crawled = True
            else:
                rc = self.add_appendix_rc(rc_link, linking_level=source_rc.linking_level + 1)
                if rc.resource not in self.resources:
                    continue
                already_crawled = False
            rc.add_reference(source_rc)
            if not rc.article and (not already_crawled or rc.linking_level <= APPENDIX_LINKING_LEVEL):
                if rc.resource == 'ta' and TRANSLATION_ACADEMY in REQUIRED_RESOURCES[self.my_subject]:
                    self.get_ta_article_html(rc, source_rc)
                elif rc.resource == 'tw' and TRANSLATION_WORDS in REQUIRED_RESOURCES[self.my_subject]:
                    self.get_tw_article_html(rc, source_rc)
                if rc.article and rc.title:
                    if rc.linking_level <= APPENDIX_LINKING_LEVEL:
                        self.crawl_ta_tw_deep_linking(rc)
                    else:
                        rc.set_article(None)
                else:
                    self.add_error_message(source_rc, rc.rc_link)
                    self.log.warning(f'LINK TO UNKNOWN RESOURCE FOUND IN {source_rc.rc_link}: {rc.rc_link}')
                    if rc.rc_link in self.appendix_rcs:
                        del self.appendix_rcs[rc.rc_link]

    def get_appendix_html(self, resource):
        html = ''
        filtered_rcs = dict(filter(lambda x: x[1].resource == resource.identifier and
                                             x[1].linking_level == APPENDIX_LINKING_LEVEL,
                            self.appendix_rcs.items()))
        sorted_rcs = sorted(filtered_rcs.items(), key=lambda x: x[1].title.lower())
        for item in sorted_rcs:
            rc = item[1]
            if rc.article:
                html += rc.article.replace('</article>', self.get_go_back_to_html(rc) + '</article>')
        if html:
            html = f'''
<section>
    <article id="{self.language_id}-{resource.identifier}-appendix-cover" class="resource-title-page no-header break">
        <img src="{resource.logo_url}" alt="{resource.identifier.upper()}">
        <h1 class="section-header">{resource.title}</h1>
        <h2 class="cover-version">{self.translate("version")} {resource.version}</h2>
    </article>
    {html}
</section>
'''
        return html

    def get_ta_article_html(self, rc, source_rc, config=None, toc_level=2):
        if not rc.path:
            self.add_error_message(source_rc, rc.rc_link, "Bad RC link")
            rc.extra_info = [rc.project]
            rc.project = "translate"
        if not config:
            config_file = os.path.join(self.resources[rc.resource].repo_dir, rc.project, 'config.yaml')
            if not os.path.exists(config_file):
                self.add_error_message(source_rc, rc.rc_link, f"Unable to find config.yaml file: {config_file}")
                exit()
                return
            config = yaml.full_load(read_file(config_file))
        article_dir = os.path.join(self.resources[rc.resource].repo_dir, rc.project, rc.path)
        article_file = os.path.join(article_dir, '01.md')
        if os.path.isfile(article_file):
            article_file_html = markdown2.markdown_path(article_file, extras=['markdown-in-html', 'tables', 'break-on-newline'])
        else:
            message = 'no corresponding article found'
            if os.path.isdir(article_dir):
                if not os.path.isfile(article_file):
                    message = 'dir exists but no 01.md file'
                else:
                    message = '01.md file exists but no content'
            self.add_error_message(source_rc, rc.rc_link, message)
            self.log.warning(f'LINK TO UNKNOWN RESOURCE FOUND IN {source_rc}: {rc.rc_link}')
            return
        top_box = ''
        bottom_box = ''
        question = ''
        dependencies = ''
        recommendations = ''

        title = rc.title
        if not title:
            title_file = os.path.join(article_dir, 'title.md')
            title = read_file(title_file)
            rc.set_title(title)

        question_file = os.path.join(article_dir, 'sub-title.md')
        if os.path.isfile(question_file):
            question = f'''
        <div class="ta-question">
            {self.translate('this_page_answers_the_question')}: <em>{read_file(question_file)}<em>
        </div>
'''
        if rc.path in config:
            if 'dependencies' in config[rc.path] and config[rc.path]['dependencies']:
                lis = ''
                for dependency in config[rc.path]['dependencies']:
                    dep_project = rc.project
                    for project in self.resources['ta'].projects:
                        dep_article_dir = os.path.join(self.resources['ta'].repo_dir, project['identifier'], dependency)
                        if os.path.isdir(dep_article_dir):
                            dep_project = project['identifier']
                    dep_rc_link = f'rc://{self.language_id}/ta/man/{dep_project}/{dependency}'
                    lis += f'''
                    <li>[[{dep_rc_link}]]</li>
'''
                dependencies += f'''
        <div class="ta-dependencies">
            {self.translate('in_order_to_understand_this_topic')}:
            <ul>
                {lis}
            </ul>
        </div>
'''
            if 'recommended' in config[rc.path] and config[rc.path]['recommended']:
                lis = ''
                for recommended in config[rc.path]['recommended']:
                    rec_project = rc.project
                    rec_article_dir = os.path.join(self.resources['ta'].repo_dir, rec_project, recommended)
                    if not os.path.exists(rec_article_dir):
                        for project in self.resources['ta'].projects:
                            rec_article_dir = os.path.join(self.resources['ta'].repo_dir, project['identifier'], recommended)
                            if os.path.isdir(rec_article_dir):
                                rec_project = project['identifier']
                                break
                    if not os.path.exists(rec_article_dir):
                        bad_rc_link = f"{rc.project}/config.yaml -> '{rc.path}' -> 'recommended' -> '{recommended}'"
                        self.add_error_message(rc, bad_rc_link)
                        self.log.warning(f'RECOMMENDED ARTICLE NOT FOUND FOR {bad_rc_link}')
                        continue
                    rec_rc_link = f'rc://{self.language_id}/ta/man/{rec_project}/{recommended}'
                    lis += f'''
                    <li>[[{rec_rc_link}]]</li>
'''
                recommendations = f'''
            <div class="ta-recommendations">
                {self.translate('next_we_recommend_you_learn_about')}:
                <ul>
                    {lis}
                </ul>
            </div>
'''

        if question or dependencies:
            top_box = f'''
    <div class="top-box box">
        {question}
        {dependencies}
    </div>
'''
        if recommendations:
            bottom_box = f'''
    <div class="bottom-box box">
        {recommendations}
    </div>
'''
        article_html = f'''
<article id="{rc.article_id}">
    <h{toc_level} class="section-header" toc-level="{toc_level}">{rc.title}</h{toc_level}>
    {top_box}
    {article_file_html}
    {bottom_box}
</article>'''
        article_html = self.fix_ta_links(article_html, rc.project)
        rc.set_article(article_html)

    def get_go_back_to_html(self, source_rc):
        if source_rc.linking_level == 0:
            return ''
        go_back_tos = []
        for rc_link in source_rc.references:
            if rc_link in self.rcs:
                rc = self.rcs[rc_link]
                go_back_tos.append(f'<a href="#{rc.article_id}">{rc.title}</a>')
        go_back_to_html = ''
        if len(go_back_tos):
            go_back_tos_string = '; '.join(go_back_tos)
            go_back_to_html = f'''
    <div class="go-back-to">
        (<strong>{self.translate('go_back_to')}:</strong> {go_back_tos_string})
    </div>
'''
        return go_back_to_html

    def fix_ta_links(self, text, project):
        text = re.sub(r'href="\.\./\.\./([^/"]+)/([^/"]+?)/*(01\.md)*"', rf'href="rc://{self.language_id}/ta/man/\1/\2"', text,
                      flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'href="\.\./([^/"]+?)/*(01\.md)*"', rf'href="rc://{self.language_id}/ta/man/{project}/\1"', text,
                      flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'href="([^# :/"]+)"', rf'href="rc://{self.language_id}/ta/man/{project}/\1"', text,
                      flags=re.IGNORECASE | re.MULTILINE)
        return text

    def get_tw_article_html(self, rc, source_rc=None, increment_header_depth=1):
        file_path = os.path.join(self.resources[rc.resource].repo_dir, rc.project, f'{rc.path}.md')
        fix = None
        if not os.path.exists(file_path):
            bad_names = {
                'live': 'kt/life',
                'idol': 'kt/falsegod',
                'believer': 'kt/believe',
                'holi': 'kt/holy',
            }
            path2 = ''
            if len(rc.extra_info) and rc.extra_info[-1] in bad_names:
                path2 = bad_names[rc.extra_info[-1]]
                file_path = os.path.join(self.resources[rc.resource].repo_dir, rc.project, f'{path2}.md')
            else:
                for tw_cat in TW_CATS:
                    path2 = re.sub(r'^[^/]+/', rf'{tw_cat}/', rc.path)
                    file_path = os.path.join(self.resources[rc.resource].repo_dir, rc.project, f'{path2}.md')
                    if os.path.isfile(file_path):
                        break
            if os.path.isfile(file_path) and path2:
                fix = f'change to rc://{self.language_id}/tw/dict/{rc.project}/{path2}'
            else:
                fix = None
        if os.path.isfile(file_path):
            if fix:
                self.add_error_message(source_rc, rc.rc_link, fix)
                self.log.error(f'FIX FOUND FOR FOR TW ARTICLE IN {source_rc.rc_link}: {rc.rc_link} => {fix}')
            tw_article_html = markdown2.markdown_path(file_path)
            tw_article_html = html_tools.make_first_header_section_header(tw_article_html)
            tw_article_html = html_tools.increment_headers(tw_article_html, increment_header_depth)
            tw_article_html = self.fix_tw_links(tw_article_html, rc.extra_info[0])
            tw_article_html = f'''                
<article id="{rc.article_id}">
    {tw_article_html}
</article>
'''
            rc.set_title(html_tools.get_title_from_html(tw_article_html))
            rc.set_article(tw_article_html)
        else:
            self.add_error_message(source_rc, rc.rc_link)
            self.log.error(f'TW ARTICLE NOT FOUND: {file_path}')

    def fix_tw_links(self, text, group):
        text = re.sub(r'href="\.\./([^/)]+?)(\.md)*"', rf'href="rc://{self.language_id}/tw/dict/bible/{group}/\1"', text,
                      flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'href="\.\./([^)]+?)(\.md)*"', rf'href="rc://{self.language_id}/tw/dict/bible/\1"', text,
                      flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'(\(|\[\[)(\.\./)*(kt|names|other)/([^)]+?)(\.md)*(\)|]])(?!\[)',
                      rf'[[rc://{self.language_id}/tw/dict/bible/\3/\4]]', text,
                      flags=re.IGNORECASE | re.MULTILINE)
        return text

    def convert(self):
        self.setup_resources()
        self.setup_images_dir()
        self.setup_style_sheets()
        self.setup_loggers()
        self.generate_all_files()
        self.upload_pdf_and_json_to_cdn()
        self.finish_up()
        return True

    def process_relation_resources(self):
        for relation in self.main_resource.relation:
            lang = self.language_id
            if '/' in relation:
                _, resource_name = relation.split('/')[0:2]
            else:
                resource_name = relation
            if '?' in resource_name:
                resource_name, version = resource_name.split('?')[0:2]
                version = version.replace('=', '')
            else:
                version = None
            # if self.debug_mode:
            #     repo_name = f'{self.language_id}_{resource_name}'
            #     repo_dir = os.path.join(self.download_dir, repo_name)
            #     if os.path.exists(repo_dir):
            #         return Resource(owner=self.owner, repo_name=repo_name, repo_dir=repo_dir, ref=version, api=self.api)
            entry = self.api.get_catalog_entry(owner=self.main_resource.owner, repo_name=f'{lang}_{resource_name}',
                                                ref=version)
            # Try version without the "v"
            if not entry:
                entry = self.api.get_catalog_entry(owner=self.main_resource.owner, repo_name=f'{lang}_{resource_name}',
                                                   ref=version[1:])

            if not entry:
                entry = self.api.get_catalog_entry(owner=DEFAULT_OWNER, repo_name=f'{lang}_{resource_name}',
                                                   ref=version)
            if entry:
                if not version:
                    # get the latest version if one, else use DEFAULT_BRANCH
                    entries = self.api.query_catalog(owners=[entry['owner']], repos=[entry['name']])
                    if 'data' in entries and len(entries['data']):
                        entry = entries['data'][0]
                resource = Resource(subject=entry['subject'], owner=entry['owner'], repo_name=entry['name'],
                                    ref=entry['branch_or_tag_name'], zipball_url=entry['zipball_url'], api=self.api)
                self.relation_resources[resource.identifier] = resource

    def find_catalog_entry(self, subject):
        entries = self.find_catalog_entries(subject)
        if len(entries):
            return entries[0]

    def find_catalog_entries(self, subject, lang=None):
        stage = self.stage
        owner = self.owner
        repos = None
        if not lang:
            lang = self.language_id

        if subject == GREEK_NEW_TESTAMENT:
            stage = STAGE_PROD
            owner = 'Door43-Catalog' # Have to hardcode this since this owner has aligned TW data
            lang = NT_OL_LANG_CODE
        elif subject == HEBREW_OLD_TESTAMENT:
            stage = STAGE_PROD
            owner = 'Door43-Catalog' # Have to hardcode this since this owner has aligned TW data
            lang = OT_OL_LANG_CODE
        elif subject == ALIGNED_BIBLE or subject == BIBLE:
            stage = STAGE_PROD
            owner = DEFAULT_OWNER
            repos = [f'{lang}_ult', f'{lang}_ust']

        keyed_args_to_find_best_match = [
            {
                'owners': owner,
                'langs': lang,
                'stage': stage,
                'repos': repos,
            },
            {
                'owners': owner,
                'langs': lang,
                'stage': stage,
            },
            {
                'owners': owner,
                'langs': lang,
                'stage': STAGE_LATEST
            },
            {
                'owners': OWNERS,
                'langs': lang,
                'stage': stage
             },
            {
                'owners': OWNERS,
                'langs': lang,
                'stage': STAGE_LATEST
             },
            {
                'langs': lang,
                'stage': stage
             },
            {
                'langs': lang,
                'stage': STAGE_LATEST
             },
            {
                'langs': DEFAULT_LANG_CODE,
                'stage': stage
            },
            {
                'langs': DEFAULT_LANG_CODE,
                'stage': STAGE_LATEST
            },
            {
                'stage': stage
            },
            {
                'stage': STAGE_LATEST
            }
        ]

        for keyed_args in keyed_args_to_find_best_match:
            response = self.api.query_catalog(subjects=subject, sort='released', order='desc', **keyed_args)
            if 'ok' in response and 'data' in response and len(response['data']):
                return response['data']
        return []

    def find_resources(self, subject, lang=None):
        resources = Resources()
        entries = self.find_catalog_entries(subject, lang)
        if len(entries):
            for entry in entries:
                if entry['subject'] == subject:
                    resource = Resource(subject=subject, owner=entry['owner'], repo_name=entry['name'],
                                        ref=entry['branch_or_tag_name'], zipball_url=entry['zipball_url'], api=self.api)
                    if resource.identifier not in resources:
                        resources[resource.identifier] = resource
        return resources

    def find_resource(self, subject, lang=None):
        resources = self.find_resources(subject, self.language_id)
        if len(resources):
            for identifier, resource in resources.items():
                if identifier not in self.resources:
                    return resource
        if not lang:
            return self.find_resource(subject, DEFAULT_LANG_CODE)
        else:
            return None

    def download_resource(self, resource):
        self.log.info(f"download_source_file( {resource.zipball_url}, {self.download_dir} )")
        source_filepath = os.path.join(self.download_dir, resource.repo_name + '.zip')
        if resource.repo_dir:
            repo_dir = resource.repo_dir
        else:
            repo_dir = os.path.join(self.download_dir, resource.repo_name)
        self.log.info(f"source_filepath: {source_filepath}, repo_dir: {repo_dir}")
        if not os.path.exists(repo_dir):
            if not self.debug_mode or not os.path.exists(source_filepath):
                try:
                    self.log.info(f"Downloading {resource.zipball_url}...")
                    # if the file already exists, remove it, we want a fresh copy
                    if os.path.isfile(source_filepath):
                        os.remove(source_filepath)
                    download_file(resource.zipball_url, source_filepath)
                finally:
                        self.log.info("Downloading finished.")
            try:
                self.log.info(f"Unzipping {source_filepath}...")
                unzip(source_filepath, self.download_dir)
            finally:
                self.log.info("Unzipping finished.")
                if os.path.exists(repo_dir):
                    resource.repo_dir = repo_dir
                else:
                    self.log.error(f"Unable to find repo directory after unzipping {resource.zipball_url}")
        else:
            resource.repo_dir = repo_dir
        # # need to make all resources have the same language code in their dir names for processing
        # if resource.language_id != self.language_id and resource.subject != GREEK_NEW_TESTAMENT and \
        #         resource.subject != HEBREW_OLD_TESTAMENT:
        #     # Create a symlink to the resource so processBibles.js can process it
        #     new_repo_dir = os.path.join(self.download_dir, f'{self.language_id}_{resource.identifier}')
        #     if not os.path.exists(new_repo_dir):
        #         symlink(resource.repo_dir, new_repo_dir)
    # end of download_source_file function


def represent_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

