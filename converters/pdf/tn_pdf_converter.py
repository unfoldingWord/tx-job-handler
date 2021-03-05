#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF TN documents
"""
import os
import re
import markdown2
import general_tools.html_tools as html_tools
from door43_tools.subjects import TSV_TRANSLATION_NOTES, ALIGNED_BIBLE
from glob import glob
from collections import OrderedDict
from .tsv_pdf_converter import TsvPdfConverter
from .pdf_converter import represent_int
from door43_tools.bible_books import BOOK_CHAPTER_VERSES
from general_tools.alignment_tools import flatten_alignment
from general_tools.file_utils import load_json_object, get_latest_version_path, get_child_directories

QUOTES_TO_IGNORE = ['general information:', 'connecting statement:']


class TnPdfConverter(TsvPdfConverter):
    my_subject = TSV_TRANSLATION_NOTES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tw_words_data = OrderedDict()
        self.tn_groups_data = OrderedDict()
        self.tn_book_data = OrderedDict()

    @property
    def name(self):
        return 'tn'

    def get_body_html(self):
        self.log.info('Creating TN for {0}...'.format(self.file_project_and_ref))
        self.process_bibles()
        for resource in self.resources.items():
            if resource.subject == ALIGNED_BIBLE:
                self.populate_book_data(resource.identifier, resource.lang_code)
        self.populate_book_data(self.ol_bible_id, self.ol_lang_code)
        self.populate_tw_words_data()
        self.populate_tn_groups_data()
        self.populate_tn_book_data()
        html = self.get_tn_html()
        self.tn_book_data = None
        self.tn_groups_data = None
        self.tw_words_data = None
        return html

    def populate_tn_book_data(self):
        book_filename = f'{self.lang_code}_{self.main_resource.identifier}_{self.book_number}-{self.project_id.upper()}.tsv'
        book_filepath = os.path.join(self.main_resource.repo_dir, book_filename)
        if not os.path.isfile(book_filepath):
            return
        book_data = OrderedDict()
        reader = self.unicode_csv_reader(open(book_filepath))
        header = next(reader)
        row_count = 1
        for row in reader:
            row_count += 1
            verse_data = {
                'contextId': None,
                'row': row_count,
                'alignments': {
                    self.ult_id: None,
                    self.ust_id: None
                }
            }
            found = False
            for idx, field in enumerate(header):
                field = field.strip()
                if idx >= len(row):
                    self.log.error(f'ERROR: {book_filepath} is malformed at row {row_count}: {row}')
                    self.add_error_message(self.create_rc(f'{book_filename}#{row_count}'), f'Line {row_count}', f'Malformed row: {row}')
                    found = False
                    break
                else:
                    found = True
                    verse_data[field] = row[idx]
            if not found:
                continue
            chapter = verse_data['Chapter'].lstrip('0')
            verse = verse_data['Verse'].lstrip('0')
            occurrence = 1
            if represent_int(verse_data['Occurrence']) and int(verse_data['Occurrence']) > 0:
                occurrence = int(verse_data['Occurrence'])
            tn_rc_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}/{verse_data["ID"]}'
            tn_title = f'{verse_data["GLQuote"]}'
            if verse_data['OrigQuote']:
                context_id = None
                if chapter in self.tn_groups_data and verse in self.tn_groups_data[chapter] and \
                        self.tn_groups_data[chapter][verse]:
                    for c_id in self.tn_groups_data[chapter][verse]:
                        if c_id['quoteString'] == verse_data['OrigQuote'] and c_id['occurrence'] == occurrence:
                            context_id = c_id
                            break
                if not context_id and chapter.isdigit() and verse.isdigit():
                    context_id = {
                        'reference': {
                            'chapter': int(chapter),
                            'verse': int(verse)
                        },
                        'rc': f'rc://{self.lang_code}/{self.name}/help///{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}',
                        'quote': verse_data['OrigQuote'],
                        'occurrence': occurrence,
                        'quoteString': verse_data['OrigQuote']
                    }
                if context_id:
                    context_id['rc'] += f'/{verse_data["ID"]}'
                    context_id['quoteString'] = verse_data['OrigQuote']
                    verse_data['contextId'] = context_id
                    verse_data['alignments'] = {
                        self.ult_id: self.get_aligned_text(self.ult_id, context_id),
                        self.ust_id: self.get_aligned_text(self.ust_id, context_id)
                    }
                if verse_data['alignments'][self.ult_id]:
                    tn_title = flatten_alignment(verse_data['alignments'][self.ult_id]) + f' ({self.ult_id.upper()})'
                    if verse_data['alignments'][self.ust_id]:
                        tn_title += '<br/>' + flatten_alignment(verse_data['alignments'][self.ust_id]) + f' ({self.ust_id.upper()})'
                else:
                    tn_title = f'{verse_data["GLQuote"]}'
            tn_rc = self.create_rc(tn_rc_link, title=tn_title)
            verse_data['title'] = tn_title
            verse_data['rc'] = tn_rc
            if chapter not in book_data:
                book_data[chapter] = OrderedDict()
            if verse not in book_data[chapter]:
                book_data[chapter][verse] = []
            book_data[str(chapter)][str(verse)].append(verse_data)
        self.tn_book_data = book_data

    def get_tn_html(self):
        tn_html = f'''
<section id="{self.lang_code}-{self.name}-{self.project_id}" class="{self.name}">
    <article id="{self.lang_code}-{self.name}-{self.project_id}-cover" class="resource-title-page">
        <img src="{self.main_resource.logo_url}" class="logo" alt="UTN">
        <h1 class="section-header">{self.title}</h1>
        <h2 class="section-header no-header">{self.project_title}</h2>
    </article>
'''
        if 'front' in self.tn_book_data and 'intro' in self.tn_book_data['front']:
            book_intro = markdown2.markdown(self.tn_book_data['front']['intro'][0]['OccurrenceNote'].replace('<br>', '\n'))
            book_intro_title = html_tools.get_title_from_html(book_intro)
            book_intro = self.fix_tn_links(book_intro, 'intro')
            book_intro = html_tools.make_first_header_section_header(book_intro, level=3)
            # HANDLE FRONT INTRO RC LINKS
            book_intro_rc_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/front/intro'
            book_intro_rc = self.add_rc(book_intro_rc_link, title=book_intro_title)
            book_intro = f'''
    <article id="{book_intro_rc.article_id}">
        {book_intro}
    </article>
'''
            book_intro_rc.set_article(book_intro)
            tn_html += book_intro
        for chapter in BOOK_CHAPTER_VERSES[self.project_id]:
            self.log.info(f'Chapter {chapter}...')
            chapter_title = f'{self.project_title} {chapter}'
            # HANDLE INTRO RC LINK
            chapter_rc_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/{self.pad(chapter)}'
            chapter_rc = self.add_rc(chapter_rc_link, title=chapter_title)
            tn_html += f'''
    <section id="{chapter_rc.article_id}" class="chapter">
        <h3 class="section-header no-header">{chapter_title}</h3>
'''
            if 'intro' in self.tn_book_data[chapter]:
                self.log.info('Generating chapter info...')
                chapter_intro = markdown2.markdown(self.tn_book_data[chapter]['intro'][0]['OccurrenceNote'].replace('<br>', "\n"))
                # Remove leading 0 from chapter header
                chapter_intro = re.sub(r'<h(\d)>([^>]+) 0+([1-9])', r'<h\1>\2 \3', chapter_intro, 1, flags=re.MULTILINE | re.IGNORECASE)
                chapter_intro = html_tools.make_first_header_section_header(chapter_intro, level=4, no_toc=True)
                chapter_intro_title = html_tools.get_title_from_html(chapter_intro)
                chapter_intro = self.fix_tn_links(chapter_intro, chapter)
                # HANDLE INTRO RC LINK
                chapter_intro_rc_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/chapter_intro'
                chapter_intro_rc = self.add_rc(chapter_intro_rc_link, title=chapter_intro_title)
                chapter_intro = f'''
        <article id="{chapter_intro_rc.article_id}">
            {chapter_intro}
        </article>
'''
                chapter_intro_rc.set_article(chapter_intro)
                tn_html += chapter_intro

            for verse in range(1,  int(BOOK_CHAPTER_VERSES[self.project_id][chapter]) + 1):
                verse = str(verse)
                self.log.info(f'Generating verse {chapter}:{verse}...')
                tn_html += self.get_tn_article(chapter, verse)
            tn_html += '''
    </section>
'''
        tn_html += '''
</section>
'''
        self.log.info('Done generating TN HTML.')
        return tn_html

    def get_tn_article(self, chapter, verse):
        tn_title = f'{self.project_title} {chapter}:{verse}'
        tn_rc_link = f'rc://{self.lang_code}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}'
        tn_rc = self.add_rc(tn_rc_link, title=tn_title)
        ult_with_tw_words = self.get_scripture_with_tw_words(self.ult_id, chapter, verse)
        # ult_with_tw_words = self.get_scripture_with_tn_quotes(self.ult_id, chapter, verse, rc, ult_with_tw_words)
        ust_with_tw_words = self.get_scripture_with_tw_words(self.ust_id, chapter, verse)
        # ust_with_tw_words = self.get_scripture_with_tn_quotes(self.ust_id, chapter, verse, rc, ust_with_tw_words)

        tn_article = f'''
                <article id="{tn_rc.article_id}">
                    <h4 class="section-header no-toc">{tn_title}</h4>
                    <div class="notes">
                            <div class="col1">
                                <h3 class="bible-resource-title">{self.ult_id.upper()}</h3>
                                <div class="bible-text">{ult_with_tw_words}</div>
                                <h3 class="bible-resource-title">{self.ust_id.upper()}</h3>
                                <div class="bible-text">{ust_with_tw_words}</div>
                            </div>
                            <div class="col2">
                                {self.get_tn_article_text(chapter, verse)}
                                {self.get_tw_html_list(self.ult_id, chapter, verse, ult_with_tw_words)}
                                {self.get_tw_html_list(self.ust_id, chapter, verse, ust_with_tw_words)}
                            </div>
                    </div>
                </article>
'''
        tn_rc.set_article(tn_article)
        return tn_article

    def get_tw_html_list(self, bible_id, chapter, verse, scripture=''):
        if chapter not in self.tw_words_data or verse not in self.tw_words_data[chapter] or \
                not self.tw_words_data[chapter][verse]:
            return ''
        group_datas = self.tw_words_data[chapter][verse]
        for group_data_idx, group_data in enumerate(group_datas):
            alignment = group_data['alignments'][bible_id]
            if alignment:
                title = flatten_alignment(alignment)
            else:
                title = f'[[{group_data["contextId"]["rc"]}]]'
            group_datas[group_data_idx]['title'] = title
        rc_pattern = 'rc://[/A-Za-z0-9*_-]+'
        rc_order = re.findall(rc_pattern, scripture)
        group_datas.sort(key=lambda x: str(rc_order.index(x['contextId']['rc']) if x['contextId']['rc'] in rc_order else x['title']))
        links = []
        for group_data_idx, group_data in enumerate(group_datas):
            tw_rc = group_data['contextId']['rc']
            occurrence = group_data['contextId']['occurrence']
            occurrence_text = ''
            if occurrence > 1:
                occurrence_text = f' ({occurrence})'
            title = group_data['title']
            links.append(f'<a href="{tw_rc}" class="tw-phrase tw-phrase-{group_data_idx + 1}">{title}</a>{occurrence_text}')
        tw_html = f'''
                <h3>{self.resources['tw'].simple_title} - {bible_id.upper()}</h3>
                <ul class="tw-list">
                    <li>{'</li><li>'.join(links)}</li>
                </ul>
'''
        return tw_html

    def get_tn_article_text(self, chapter, verse):
        verse_notes = ''
        if verse in self.tn_book_data[chapter]:
            for tn_note in self.tn_book_data[chapter][verse]:
                note = markdown2.markdown(tn_note['OccurrenceNote'].replace('<br>', "\n"))
                note = re.sub(r'</*p[^>]*>', '', note, flags=re.IGNORECASE | re.MULTILINE)
                verse_notes += f'''
        <div id="{tn_note['rc'].article_id}" class="verse-note">
            <h3 class="verse-note-title">{tn_note['title']}</h3>
            <div class="verse-note-text">
                {note}
            </div>
        </div>
'''
        else:
            verse_notes += f'''
        <div class="no-notes">
            ({self.translate('no_notes_for_this_verse')})
        </div>
'''
        verse_notes = self.fix_tn_links(verse_notes, chapter)
        return verse_notes

    def populate_tw_words_data(self):
        tw_path = os.path.join(self.resources_dir, self.ol_lang_code, 'translationHelps/translationWords')
        if not tw_path:
            self.log.error(f'{tw_path} not found!')
            exit(1)
        tw_version_path = get_latest_version_path(tw_path)
        if not tw_version_path:
            self.log.error(f'No versions found in {tw_path}!')
            exit(1)

        groups = get_child_directories(tw_version_path)
        words_data = OrderedDict()
        for group in groups:
            files_path = os.path.join(tw_version_path, f'{group}/groups/{self.project_id}', '*.json')
            files = glob(files_path)
            for file in files:
                base = os.path.splitext(os.path.basename(file))[0]
                tw_rc_link = f'rc://{self.lang_code}/tw/dict/bible/{group}/{base}'
                tw_group_data = load_json_object(file)
                for group_data in tw_group_data:
                    chapter = str(group_data['contextId']['reference']['chapter'])
                    verse = str(group_data['contextId']['reference']['verse'])
                    group_data['contextId']['rc'] = tw_rc_link
                    group_data['alignments'] = {
                        self.ult_id: self.get_aligned_text(self.ult_id, group_data['contextId']),
                        self.ust_id: self.get_aligned_text(self.ust_id, group_data['contextId'])
                    }
                    if chapter not in words_data:
                        words_data[chapter] = OrderedDict()
                    if verse not in words_data[chapter]:
                        words_data[chapter][verse] = []
                    words_data[chapter][verse].append(group_data)
        self.tw_words_data = words_data

    def populate_tn_groups_data(self):
        tn_resource_path = os.path.join(self.resources_dir, self.lang_code, 'translationHelps', 'translationNotes')
        if not tn_resource_path:
            self.log.error(f'{tn_resource_path} not found!')
            exit(1)
        tn_version_path = get_latest_version_path(tn_resource_path)
        if not tn_version_path:
            self.log.error(f'Version not found in {tn_resource_path}!')
            exit(1)

        groups = get_child_directories(tn_version_path)
        groups_data = OrderedDict()
        for group in groups:
            files_path = os.path.join(tn_version_path, f'{group}/groups/{self.project_id}', '*.json')
            files = glob(files_path)
            for file in files:
                base = os.path.splitext(os.path.basename(file))[0]
                occurrences = load_json_object(file)
                for occurrence in occurrences:
                    context_id = occurrence['contextId']
                    chapter = str(context_id['reference']['chapter'])
                    verse = str(context_id['reference']['verse'])
                    tn_rc_link = f'rc://{self.lang_code}/{self.name}/help/{group}/{base}/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}'
                    context_id['rc'] = tn_rc_link
                    if chapter not in groups_data:
                        groups_data[chapter] = OrderedDict()
                    if verse not in groups_data[chapter]:
                        groups_data[chapter][verse] = []
                    groups_data[chapter][verse].append(context_id)
        self.tn_groups_data = groups_data

    def get_scripture_with_tw_words(self, bible_id, chapter, verse, rc=None):
        scripture = self.get_plain_scripture(bible_id, chapter, verse)
        footnotes_split = re.compile('<div class="footnotes">', flags=re.IGNORECASE | re.MULTILINE)
        verses_and_footnotes = re.split(footnotes_split, scripture, maxsplit=1)
        scripture = verses_and_footnotes[0]
        footnote = ''
        if len(verses_and_footnotes) == 2:
            footnote = f'<div class="footnotes">{verses_and_footnotes[1]}'
        orig_scripture = scripture
        if chapter not in self.tw_words_data or verse not in self.tw_words_data[chapter] or \
                not self.tw_words_data[chapter][verse]:
            return scripture
        phrases = self.tw_words_data[chapter][verse]
        for group_data_idx, group_data in enumerate(phrases):
            tw_rc = group_data['contextId']['rc']
            split = ''
            if len(group_data):
                split = ' split'
            tag = f'<a href="{tw_rc}" class="tw-phrase tw-phrase-{group_data_idx + 1}{split}">'
            alignment = group_data['alignments'][bible_id]
            if alignment:
                marked_verse_html = html_tools.mark_phrases_in_html(scripture, alignment, tag=tag)
                if not marked_verse_html:
                    if rc:
                        self.add_bad_highlight(rc, orig_scripture, tw_rc, flatten_alignment(group_data))
                else:
                    scripture = marked_verse_html
        scripture += footnote
        return scripture

    def get_scripture_with_tn_quotes(self, bible_id, chapter, verse, rc, scripture):
        if not scripture:
            scripture = self.get_plain_scripture(bible_id, chapter, verse)
        footnotes_split = re.compile('<div class="footnotes">', flags=re.IGNORECASE | re.MULTILINE)
        verses_and_footnotes = re.split(footnotes_split, scripture, maxsplit=1)
        scripture = verses_and_footnotes[0]
        footnote = ''
        if len(verses_and_footnotes) == 2:
            footnote = f'<div class="footnotes">{verses_and_footnotes[1]}'
        if verse in self.tn_book_data[chapter]:
            tn_notes = self.tn_book_data[chapter][verse]
        else:
            tn_notes = []
        orig_scripture = scripture
        for tn_note_idx, tn_note in enumerate(tn_notes):
            occurrence = 1
            if represent_int(tn_note['Occurrence']) and int(tn_note['Occurrence']) > 0:
                occurrence = int(tn_note['Occurrence'])
            gl_quote_phrase = [[{
                'word': tn_note['GLQuote'],
                'occurrence': occurrence
            }]]
            phrase = tn_note['alignments'][bible_id]
            if not phrase:
                phrase = gl_quote_phrase
            if flatten_alignment(phrase).lower() in QUOTES_TO_IGNORE:
                continue
            split = ''
            if len(phrase) > 1:
                split = ' split'
            tag = f'<span class="highlight phrase phrase-{tn_note_idx+1}{split}">'
            marked_verse_html = html_tools.mark_phrases_in_html(scripture, phrase, tag=tag)
            if not marked_verse_html:
                fix = None
                if flatten_alignment(phrase).lower() not in QUOTES_TO_IGNORE:
                    if tn_note['GLQuote']:
                        marked_with_gl_quote = html_tools.mark_phrases_in_html(scripture, gl_quote_phrase)
                        if marked_with_gl_quote:
                            fix = tn_note['GLQuote']
                    self.add_bad_highlight(rc, orig_scripture, tn_note['rc'], tn_note['GLQuote'], fix)
            else:
                scripture = marked_verse_html
        scripture += footnote
        return scripture

    def fix_tn_links(self, html, chapter):
        html = self.fix_tsv_links(html, chapter)
        return html


