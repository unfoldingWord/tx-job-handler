#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF for OBS
"""
import os
import string
import markdown2
from door43_tools.subjects import OPEN_BIBLE_STORIES
from .pdf_converter import PdfConverter
from general_tools.file_utils import read_file
from general_tools import obs_tools
from weasyprint import HTML


class ObsPdfConverter(PdfConverter):
    my_subject = OPEN_BIBLE_STORIES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._title = None

    @property
    def title(self):
        if not self._title:
            front_title_path = os.path.join(self.main_resource.repo_dir, 'content', 'front', 'title.md')
            self._title = read_file(front_title_path).strip()
        return self._title

    @property
    def toc_title(self):
        return f'<h1>{self.main_resource.title}</h1>'

    def get_page_template(self, obs_chapter_data, frame_idx):
        frame1 = obs_chapter_data['frames'][frame_idx]
        page_template_html = f'''
    <article class="obs-page">
        <div class="obs-frame no-break obs-frame-odd">
            <img src="{frame1['image']}" class="obs-img"/>
            <div class="obs-text no-break" style="font-size: $font_size">
                {frame1['text']}
            </div>
'''
        if frame_idx + 1 < len(obs_chapter_data['frames']):
            frame2 = obs_chapter_data['frames'][frame_idx + 1]
            page_template_html += f'''
        </div>
        <div class="obs-frame no-break obs-frame-even">
            <img src="{frame2['image']}" class="obs-img"/>
            <div class="obs-text no-break" style="font-size: $font_size">
                {frame2['text']}
            </div>
'''
        # If this page is at the end of the chapter, need the bible reference
        if frame_idx + 2 >= len(obs_chapter_data['frames']) and obs_chapter_data['bible_reference']:
            page_template_html += f'''
            <div class="bible-reference no-break"  style="font-size: $bible_reference_font_size">{obs_chapter_data['bible_reference']}</div>
'''
        page_template_html += '''
        </div>
    </article>
'''
        page_template_html = self.download_all_images(page_template_html)
        return string.Template(page_template_html)

    def get_body_html(self):
        self.log.info('Generating OBS html...')
        obs_html = '''
<article class="blank-page">
</article>        
'''
        stylesheets = [os.path.join(self.output_res_dir, style) for style in self.style_sheets]
        for chapter_num in range(1, 51):
            chapter_num = str(chapter_num).zfill(2)
            obs_chapter_data = obs_tools.get_obs_chapter_data(self.main_resource.repo_dir, chapter_num)
            chapter_title = obs_chapter_data['title']
            obs_html += f'''
<article class="obs-chapter-title-page no-header-footer">
    <h1 id="{self.lang_code}-obs-{chapter_num}" class="section-header">{chapter_title}</h1>
</article>
'''
            frames = obs_chapter_data['frames']
            for frame_idx in range(0, len(frames), 2):
                page_template = self.get_page_template(obs_chapter_data, frame_idx)
                font_size_em = 1.0
                frames_str = f'{chapter_num}:{str(frame_idx+1).zfill(2)}'
                has_two_frames = True
                if frame_idx < len(frames) - 1:
                    frames_str += f'-{str(frame_idx+2).zfill(2)}'
                else:
                    has_two_frames = False
                self.log.info(f'Fitting {frames_str} to page with font_size={font_size_em}em...')
                while has_two_frames:  # mimic do-while loop with break
                    # See if the page fits on one printed page. If not, reduce font size by .05em
                    # Bible reference font size is always .1em less than the text font size
                    page_html = page_template.safe_substitute(font_size=f'{font_size_em}em',
                                                              bible_reference_font_size=f'{font_size_em-0.1}em')
                    doc = HTML(string=page_html, base_url=self.output_res_dir).render(stylesheets=stylesheets)
                    if len(doc.pages) > 1:
                        font_size_em -= .05
                        self.log.info(f'REfitting {frames_str} to page with font_size={font_size_em}em...')
                    else:
                        obs_html += page_html
                        break
        return obs_html

    def get_cover_html(self):
        cover_html = f'''
<article id="main-cover" class="cover no-header-footer">
    <img src="https://cdn.door43.org/obs/png/uW_OBS_Logo.png" alt="{self.name.upper()}"/>
    <div class="language">
        {self.main_resource.language_title}<br/>
        {self.main_resource.language_id}
    </div>
</article>
<article class="blank-page no-footer">
</article>
'''
        return cover_html

    def get_license_html(self):
        front_path = os.path.join(self.main_resource.repo_dir, 'content', 'front', 'intro.md')
        front_html = markdown2.markdown_path(front_path)
        license_html = f'''
<article id="front" class="no-footer">
  {front_html}
  <p>
</article>
'''
        return license_html

    def get_contributors_html(self):
        back_path = os.path.join(self.main_resource.repo_dir, 'content', 'back', 'intro.md')
        back_html = markdown2.markdown_path(back_path)
        back_html = f'''
<article id="back" class="obs-page">
  {back_html}
</article>
'''
        return back_html
