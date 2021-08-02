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
import markdown2
from bs4 import BeautifulSoup
from door43_tools.subjects import OPEN_BIBLE_STORIES
from general_tools.file_utils import copy_tree, read_file, unzip
from .pdf_converter import PdfConverter
from general_tools.url_utils import get_url, download_file
from general_tools import obs_tools


class ObsPdfConverter(PdfConverter):
    my_subject = OPEN_BIBLE_STORIES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._title = None

    def get_sample_text(self):
        md_file = os.path.join(self.file_path, '01.md')
        if os.path.exists(md_file):
            html = markdown2.markdown_path(md_file)
            soup = BeautifulSoup(html, 'html.parser')
            paragraphs = soup.find_all('p')
            if len(paragraphs) > 1:
                for p in paragraphs[1:]:
                    if p.text:
                        return p.text
            return soup.text

    @property
    def toc_title(self):
        return f'<h1>{self.main_resource.title}</h1>'

    @property
    def head_html(self):
        html = super().head_html + f'''
        <meta name="description" content="unrestricted visual Bible stories" />
 '''
        return html

    def setup_images_dir(self):
        super().setup_images_dir()
        jpg_dir = os.path.join(self.images_dir, 'cdn.door43.org', 'obs', 'jpg')
        if not os.path.exists(jpg_dir):
            download_file('http://cdn.door43.org/obs/jpg/obs-images-360px-compressed.zip', os.path.join(self.images_dir,
                                                                                                        'images.zip'))
            unzip(os.path.join(self.images_dir, 'images.zip'), jpg_dir)
            os.unlink(os.path.join(self.images_dir, 'images.zip'))

    def get_body_html(self):
        self.log.info('Generating OBS html...')
        html = f'''
<article class="blank-page no-footer">
</article>
'''
        # The ObsPreprosessor in door43-job-handler puts all the Markdown files into the root dir
        for chapter in range(1, 51):
            chapter_str = str(chapter).zfill(2)
            obs_chapter_data = obs_tools.get_obs_chapter_data(self.file_path, chapter_str)
            chapter_title = obs_chapter_data['title']
            html += f'''
<article class="obs-chapter-title-page no-header-footer">
    <h1 id="{chapter_str}" class="section-header">{chapter_title}</h1>
</article>
'''
            frames = obs_chapter_data['frames']
            for frame_idx in range(0, len(frames), 2):
                frames_str = f'{chapter_str}:{str(frame_idx+1).zfill(2)}'
                if frame_idx < len(frames) - 1:
                    frames_str += f'-{str(frame_idx+2).zfill(2)}'
                article_id = frames_str.replace(':', '-')
                frame1 = obs_chapter_data['frames'][frame_idx]
                html += f'''
                    <article class="obs-page" id="fit-to-page-{article_id}">
                        <div class="obs-frame no-break obs-frame-odd">
                            <img src="{frame1['image']}" class="obs-img"/>
                            <div class="obs-text no-break">
                                {frame1['text']}
                            </div>
                '''
                if frame_idx + 1 < len(obs_chapter_data['frames']):
                    frame2 = obs_chapter_data['frames'][frame_idx + 1]
                    soup = BeautifulSoup(frame2['text'], 'html.parser')
                    span = soup.new_tag("span", id=f"{article_id}-frame-2")
                    p = soup.find('p')
                    if p:
                        p.append(span)
                    else:
                        soup.append(span)
                    html += f'''
                        </div>
                        <div class="obs-frame no-break obs-frame-even">
                            <img src="{frame2['image']}" class="obs-img"/>
                            <div class="obs-text no-break">
                                {str(soup)}
                            </div>
                '''
                # If this page is at the end of the chapter, need the bible reference
                if frame_idx + 2 >= len(obs_chapter_data['frames']) and obs_chapter_data['bible_reference']:
                    html += f'''
                            <div id="{article_id}-bible" class="bible-reference no-break">
                                {obs_chapter_data['bible_reference']}
                            </div>
                '''
                html += f'''
                        </div>
                    </article>
                '''
        return html

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

    @property
    def is_massaged_obs(self):
        return not os.path.exists(os.path.join(self.main_resource.repo_dir, 'content'))

    @property
    def file_path(self):
        if self.is_massaged_obs:
            return self.main_resource.repo_dir
        return os.path.join(self.main_resource.repo_dir, 'content')

    @property
    def front_path(self):
        if self.is_massaged_obs:
            return os.path.join(self.file_path, 'front.md')
        return os.path.join(self.file_path, 'front', 'intro.md')

    @property
    def back_path(self):
        if self.is_massaged_obs:
            return os.path.join(self.file_path, 'back.md')
        return os.path.join(self.file_path, 'back', 'intro.md')

    def get_license_html(self):
        front_path = self.front_path
        if os.path.exists(front_path):
            front_html = markdown2.markdown_path(front_path)
        else:
            front_html = markdown2.markdown(get_url('https://git.door43.org/api/v1/repos/unfoldingword/en_obs/raw/content/front/intro.md'))
        license_html = f'''
<article id="front" class="no-footer">
  {front_html}
  <p>
</article>
'''
        return license_html

    def get_contributors_html(self):
        back_path = self.back_path
        if os.path.exists(back_path):
            back_html = markdown2.markdown_path(back_path)
        else:
            back_html = markdown2.markdown(get_url('https://git.door43.org/api/v1/repos/unfoldingword/en_obs/raw/content/back/intro.md'))
        back_html = f'''
<article id="back" class="obs-page">
  {back_html}
</article>
'''
        return back_html
