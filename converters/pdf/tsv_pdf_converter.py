#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF TSV (parent class) documents
"""
import os
import re
import csv
import subprocess
import markdown2
from abc import abstractmethod
from bs4 import BeautifulSoup
from collections import OrderedDict
from .pdf_converter import PdfConverter
from tx_usfm_tools.singleFilelessHtmlRenderer import SingleFilelessHtmlRenderer
from door43_tools.subjects import ALIGNED_BIBLE, BIBLE
from general_tools.alignment_tools import get_alignment, flatten_quote
from general_tools.file_utils import read_file, load_json_object, get_latest_version_path, get_child_directories
from general_tools.usfm_utils import unalign_usfm


class TsvPdfConverter(PdfConverter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.alignment_bibles = []
        self.project_id = None

        self.resources_dir = None
        self.book_data = OrderedDict()
        self.last_ended_with_quote_tag = False
        self.last_ended_with_paragraph_tag = False
        self.open_quote = False
        self.next_follows_quote = False

        self.ult = None
        self.ust = None

        self.add_style_sheet('css/resource/tsv_style.css')

    def get_sample_text(self):
        project = self.projects[0]
        book_filepath = os.path.abspath(os.path.join(self.main_resource.repo_dir, project['path']))
        if not os.path.isfile(book_filepath):
            return ''
        reader = self.unicode_csv_reader(open(book_filepath))
        next(reader)
        row = next(reader)
        html = markdown2.markdown(row[-1].replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n').replace('</br>', ''))
        soup = BeautifulSoup(html, 'html.parser')
        p = soup.find('p')
        if not p:
            p = soup
        return p.text

    @abstractmethod
    def get_body_html(self):
        pass

    def setup_resources(self):
        super().setup_resources()
        self.determine_ult_ust_bibles()

    def determine_ult_ust_bibles(self):
        for resource in self.resources.values():
            if resource.subject == ALIGNED_BIBLE or resource.subject == BIBLE:
                if resource.identifier == 'ult' or resource.identifier == 'ulb':
                    if self.ult:
                        self.ust = self.ult
                    self.ult = resource
                elif resource.identifier == 'ust' or resource.identifier == 'udb':
                    self.ust = resource
                else:
                    if not self.ult:
                        self.ult = resource
                    elif not self.ust:
                        self.ust = resource
        if not self.ult:
            self.log.error('No ULT or similar aligned Bible found. Add one to the relation field in manifest.yaml')
            exit(1)

    def process_bibles(self):
        self.resources_dir = os.path.join(self.download_dir, f'resources')
        if not self.ult:
            self.log.error('No Bible found!')
            exit(1)
        if not os.path.exists(self.resources_dir):
            args = ['node', 'start',
                    '--resources_dir', self.resources_dir,
                    '--repos_dir', self.download_dir,
                    '-l', self.lang_code,
                    '--ult_id', self.ult.identifier]
            if self.ust:
                args += ['--ust_id', self.ust.identifier]
            self.log.info(f'Running {" ".join(args)} in {self.pdf_converters_dir}/resources')
            ret = subprocess.call(args, shell=True, cwd=f'{self.pdf_converters_dir}/resources')
            if ret:
                self.log.error('Error running resources/processBibles.js. Exiting.')
                exit(1)

    def get_usfm_from_verse_objects(self, verse_objects):
        usfm = ''
        for idx, obj in enumerate(verse_objects):
            if obj['type'] == 'milestone':
                usfm += self.get_usfm_from_verse_objects(obj['children'])
            elif obj['type'] == 'word':
                if not self.next_follows_quote and obj['text'] != 's':
                    usfm += ' '
                usfm += obj['text']
                self.next_follows_quote = False
            elif obj['type'] == 'text':
                obj['text'] = obj['text'].replace('\n', '').strip()
                if not self.open_quote and len(obj['text']) > 2 and obj['text'][-1] == '"':
                    obj['text'] = f"{obj['text'][:-1]} {obj['text'][-1]}"
                if not self.open_quote and obj['text'] == '."':
                    obj['text'] = '. "'
                if len(obj['text']) and obj['text'][0] == '"' and not self.open_quote and obj['text'] not in ['-', '—']:
                    usfm += ' '
                usfm += obj['text']
                if obj['text'].count('"') == 1:
                    self.open_quote = not self.open_quote
                if self.open_quote and '"' in obj['text'] or obj['text'] in ['-', '—', '(', '[']:
                    self.next_follows_quote = True
            elif obj['type'] == 'quote':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
                if idx == len(verse_objects) - 1 and obj['tag'] == 'q' and len(obj['text']) == 0:
                    self.last_ended_with_quote_tag = True
                else:
                    usfm += f"\n\\{obj['tag']} {obj['text'] if len(obj['text']) > 0 else ''}"
                if obj['text'].count('"') == 1:
                    self.open_quote = not self.open_quote
                if self.open_quote and '"' in obj['text']:
                    self.next_follows_quote = True
            elif obj['type'] == 'section':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
            elif obj['type'] == 'paragraph':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
                if idx == len(verse_objects) - 1 and not obj['text']:
                    self.last_ended_with_paragraph_tag = True
                else:
                    usfm += f"\n\\{obj['tag']}{obj['text']}\n"
            elif obj['type'] == 'footnote':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
                usfm += f' \\{obj["tag"]} {obj["content"]} \\{obj["tag"]}*'
            else:
                self.log.error("ERROR! Not sure what to do with this:")
                self.log.error(obj)
                exit(1)
        return usfm

    def populate_book_data(self, bible_id, lang_code=None):
        if bible_id in self.book_data:
            return
        if not lang_code:
            lang_code = self.lang_code
        bible_path = os.path.join(self.resources_dir, lang_code, 'bibles', bible_id)
        if not bible_path:
            self.log.error(f'{bible_path} not found!')
            exit(1)
        bible_version_path = get_latest_version_path(bible_path)
        if not bible_version_path:
            self.log.error(f'No versions found in {bible_path}!')
            exit(1)

        book_data = OrderedDict()
        book_file = os.path.join(self.resources[bible_id].repo_dir, f'{self.book_number}-{self.project_id.upper()}.usfm')
        book_usfm = read_file(book_file)

        unaligned_usfm = unalign_usfm(book_usfm)
        self.log.info(f'Converting {self.project_id.upper()} from USFM to HTML...')
        book_html, warnings = SingleFilelessHtmlRenderer({self.project_id.upper(): unaligned_usfm}).render()
        html_verse_splits = re.split(r'(<span id="[^"]+-ch-0*(\d+)-v-(\d+(?:-\d+)?)" class="v-num">)', book_html)
        usfm_chapter_splits = re.split(r'\\c ', unaligned_usfm)
        usfm_verse_splits = None
        chapter_verse_index = 0
        for i in range(1, len(html_verse_splits), 4):
            chapter = html_verse_splits[i+1]
            verses = html_verse_splits[i+2]
            if chapter not in book_data:
                book_data[chapter] = OrderedDict()
                usfm_chapter = f'\\c {usfm_chapter_splits[int(chapter)]}'
                usfm_verse_splits = re.split(r'\\v ', usfm_chapter)
                chapter_verse_index = 0
            chapter_verse_index += 1
            verse_usfm = f'\\v {usfm_verse_splits[chapter_verse_index]}'
            verse_html = html_verse_splits[i] + html_verse_splits[i+3]
            verse_html = re.split('<h2', verse_html)[0]  # remove next chapter since only split on verses
            verse_soup = BeautifulSoup(verse_html, 'html.parser')
            for tag in verse_soup.find_all():
                if (not tag.contents or len(tag.get_text(strip=True)) <= 0) and tag.name not in ['br', 'img']:
                    tag.decompose()
            verse_html = str(verse_soup)
            verses = re.findall(r'\d+', verses)
            for verse in verses:
                verse = verse.lstrip('0')
                book_data[chapter][verse] = {
                    'usfm': verse_usfm,
                    'html': verse_html
                }
        self.book_data[bible_id] = book_data

    @staticmethod
    def unicode_csv_reader(utf8_data, dialect=csv.excel, **kwargs):
        csv_reader = csv.reader(utf8_data, dialect=dialect, delimiter=str("\t"), quotechar=str('"'), **kwargs)
        for row in csv_reader:
            yield [cell for cell in row]

    def get_plain_scripture(self, bible_id, chapter, verse):
        if verse not in self.book_data[bible_id][chapter]:
            return ''
        data = self.book_data[bible_id][chapter][verse]
        footnotes_split = re.compile('<div class="footnotes">', flags=re.IGNORECASE | re.MULTILINE)
        verses_and_footnotes = re.split(footnotes_split, data['html'], maxsplit=1)
        scripture = verses_and_footnotes[0]
        footnotes = ''
        if len(verses_and_footnotes) == 2:
            footnote = f'<div class="footnotes">{verses_and_footnotes[1]}'
            if footnotes:
                footnote = footnote.replace('<hr class="footnotes-hr"/>', '')
            footnotes += footnote
        html = ''
        if scripture:
            scripture = re.sub(r'\s*<span class="v-num"', '</div><div class="verse"><span class="v-num"', scripture, flags=re.IGNORECASE | re.MULTILINE)
            scripture = re.sub(r'^</div>', '', scripture)
            if scripture and '<div class="verse">' in scripture:
                scripture += '</div>'
            html = scripture + footnotes
            html = re.sub(r'\s*\n\s*', ' ', html, flags=re.IGNORECASE | re.MULTILINE)
            html = re.sub(r'\s*</*p[^>]*>\s*', ' ', html, flags=re.IGNORECASE | re.MULTILINE)
            html = html.strip()
            html = re.sub('id="(ref-)*fn-', rf'id="{bible_id}-\1fn-', html,
                          flags=re.IGNORECASE | re.MULTILINE)
            html = re.sub('href="#(ref-)*fn-', rf'href="#{bible_id}-\1fn-', html,
                          flags=re.IGNORECASE | re.MULTILINE)
        return html

    def get_verse_objects(self, bible_id, chapter, verse):
        bible_path = os.path.join(self.resources_dir, self.lang_code, 'bibles', bible_id)
        if not bible_path:
            self.log.error(f'{bible_path} not found!')
            exit(1)
        bible_version_path = get_latest_version_path(bible_path)
        if not bible_version_path:
            self.log.error(f'No versions found in {bible_path}!')
            exit(1)

        chapter_json_path = f'{bible_version_path}/{self.project_id}/{chapter}.json'
        data = load_json_object(chapter_json_path)
        if verse in data:
            return data[verse]['verseObjects']
        else:
            return []

    def get_text_from_verse_objects(self, verse_objects):
        text = ''
        for verse_object in verse_objects:
            if 'text' in verse_object:
                text += verse_object['text']
            if 'children' in verse_object:
                text += self.get_text_from_verse_objects(verse_object['children'])
        return text

    def get_aligned_text(self, bible_id, context_id):
        if not context_id or 'quote' not in context_id or not context_id['quote'] or 'reference' not in context_id or \
                'chapter' not in context_id['reference'] or 'verse' not in context_id['reference']:
            return None
        chapter = str(context_id['reference']['chapter'])
        verse = str(context_id['reference']['verse'])
        verse_objects = self.get_verse_objects(bible_id, chapter, verse)
        if not verse_objects:
            return None
        quote = context_id['quote']
        occurrence = int(context_id['occurrence'])
        alignment = get_alignment(verse_objects, quote, occurrence)
        if not alignment:
            title = f'{self.project_title} {chapter}:{verse}'
            aligned_text_rc_link = f'rc://{self.lang_code}/{bible_id}/bible/{self.project_id}/{self.pad(chapter)}/{str(verse).zfill(3)}'
            aligned_text_rc = self.create_rc(aligned_text_rc_link, title=title)
            if 'quoteString' in context_id:
                quote_string = context_id['quoteString']
            else:
                quote_string = context_id['quote']
                if isinstance(quote_string, list):
                    flatten_quote(context_id['quote'])
            if int(self.book_number) > 40 or self.project_id.lower() == 'rut' or self.project_id.lower() == 'jon':
                title = f'OL ({self.ol_lang_code.upper()}) quote not found in {bible_id.upper()} {self.project_title} {chapter}:{verse} alignment'
                message = f'''
VERSE: {self.project_title} {chapter}:{verse}
RC: {context_id['rc']}
QUOTE: {quote_string}
{bible_id.upper()}: {self.book_data[bible_id][chapter][verse]['usfm']}
{self.ol_bible_id.upper()}: {self.book_data[self.ol_bible_id][chapter][verse]['usfm']}
'''
                self.add_error_message(self.create_rc(context_id['rc']), title, message)
        return alignment

    def fix_tsv_links(self, html, chapter):
        def replace_link(match):
            before_href = match.group(1)
            link = match.group(2)
            after_href = match.group(3)
            linked_text = match.group(4)
            new_link = link
            if link.startswith('../../'):
                # link to another book, which we don't link to so link removed
                return linked_text
            elif link.startswith('../'):
                # links to another verse in another chapter
                link = os.path.splitext(link)[0]
                parts = link.split('/')
                if len(parts) == 3:
                    # should have two numbers, the chapter and the verse
                    c = parts[1]
                    v = parts[2]
                    new_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/{self.pad(c)}/{v.zfill(3)}'
                if len(parts) == 2:
                    # shouldn't be here, but just in case, assume link to the first verse of the given chapter
                    c = parts[1]
                    new_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/{self.pad(c)}/001'
            elif link.startswith('./'):
                # link to another verse in the same chapter
                link = os.path.splitext(link)[0]
                parts = link.split('/')
                v = parts[1]
                new_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/{v.zfill(3)}'
            return f'<a{before_href}href="{new_link}"{after_href}>{linked_text}</a>'
        regex = re.compile(r'<a([^>]+)href="(\.[^"]+)"([^>]*)>(.*?)</a>')
        html = regex.sub(replace_link, html)
        return html

    def get_verse_html(self, usfm, resource_id, chapter, verse):
        usfm = rf'''\id {self.project_id.upper()}
\ide UTF-8
\h {self.project_title}
\mt {self.project_title}

\c {chapter}
{usfm}'''
        html, warnings = SingleFilelessHtmlRenderer({self.project_id.upper(): usfm}).render()
        soup = BeautifulSoup(html, 'html.parser')
        header = soup.find('h1')
        if header:
            header.decompose()
        chapter_header = soup.find('h2')
        if chapter_header:
            chapter_header.decompose()
        for span in soup.find_all('span', {'class': 'v-num'}):
            bible_rc_link = f'rc://{self.lang_code}/{resource_id}/bible/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}'
            bible_rc = self.create_rc(bible_rc_link)
            span['id'] = bible_rc.article_id
        html = ''.join(['%s' % x for x in soup.body.contents]).strip()
        return html

    def get_go_back_to_html(self, source_rc):
        if source_rc.linking_level == 0:
            return ''
        go_back_tos = []
        book_started = False
        for rc_link in source_rc.references:
            if rc_link in self.rcs:
                rc = self.rcs[rc_link]
                chapter = rc.chapter
                verse = rc.verse
                if chapter == 'front':
                    text = rc.title
                elif verse == 'intro':
                    text = rc.title
                    book_started = True
                else:
                    if book_started:
                        text = rc.title.split(' ')[-1]
                    else:
                        text = rc.title
                    book_started = True
                go_back_tos.append('<a href="#{0}">{1}</a>'.format(rc.article_id, text))
        go_back_to_html = ''
        if len(go_back_tos):
            go_back_tos_string = '; '.join(go_back_tos)
            go_back_to_html = f'''
    <div class="go-back-to">
        (<strong>{self.translate('go_back_to')}:</strong> {go_back_tos_string})
    </div>
'''
        return go_back_to_html
