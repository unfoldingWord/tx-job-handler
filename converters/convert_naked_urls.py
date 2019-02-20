import re

from global_settings.global_settings import GlobalSettings



def fix_naked_urls(given_html):
    """
    Neither of the markdown processors used fix naked URLs,
        i.e., URLs which are not marked as links, e.g., [Fred](https://fred.com)

    This function attempts to make the links live
        (hopefully without destroying any existing links)
    """
    # GlobalSettings.logger.debug(f"fix_naked_urls( ({len(given_html)}) {repr(given_html) if len(given_html)<200 else repr(given_html)[:200]+'…'})…")
    result_html = given_html

    re_flags = re.MULTILINE
    # TODO: I'm sure some of these RE's could be combined (but I need to move on)
    # <Full URLs> -- angle brackets get dropped
    for j, regex in enumerate((r'<((?:ftp|http|https)://(?:[\.\w\d]+?)\.(?:com|org|net|us|bible)(?:[/=\?\w\d]+))>',
                                r'<((?:ftp|http|https)://(?:[\.\w\d]+?)\.(?:com|org|net|us|bible)/?)>')):
        while True:
            match = re.search(regex, result_html, re_flags)
            if not match: break
            GlobalSettings.logger.debug(f"Found naked URL matchA{j}: '{match.group(1)}' inside '{match.group(0)}'")
            result_html = f'{result_html[:match.start(0)]}<a href="{match.group(1)}">{match.group(1)}</a>{result_html[match.end(0):]}'

    # Full URls (possibly in brackets)
    for j, regex in enumerate((r'(?:^|[ \(\[])((?:ftp|http|https)://(?:[\.\w\d]+?)\.(?:com|org|net|us|bible)(?:[/=\?\w\d]+))',
                                r'(?:^|[ \(\[])((?:ftp|http|https)://(?:[\.\w\d]+?)\.(?:com|org|net|us|bible)/?)(?:$|[ \.,!\)\]>])')):
        while True:
            match = re.search(regex, result_html, re_flags)
            if not match: break
            GlobalSettings.logger.debug(f"Found naked URL matchB{j}: '{match.group(1)}' inside '{match.group(0)}'")
            result_html = f'{result_html[:match.start(1)]}<a href="{match.group(1)}">{match.group(1)}</a>{result_html[match.end(1):]}'

    # <No protocol URLS> -- angle brackets get dropped
    for j, regex in enumerate((r'<((?:[\.\w\d]+?)\.(?:com|org|net|us|bible)(?:[/=\?\w\d]+))>',
                                r'<((?:[\.\w\d]+?)\.(?:com|org|net|us|bible)/?)>')):
        while True:
            match = re.search(regex, result_html, re_flags)
            if not match: break
            GlobalSettings.logger.debug(f"Found naked URL matchC{j}: '{match.group(1)}' inside '{match.group(0)}'")
            result_html = f'{result_html[:match.start(0)]}<a href="http://{match.group(1)}">{match.group(1)}</a>{result_html[match.end(0):]}'

    # No protocol URls (possibly in brackets)
    for j, regex in enumerate((r'(?:^|[ \(\[])((?:[\.\w\d]+?)\.(?:com|org|net|us|bible)(?:$|[/=\?\w\d]+))',
                                r'(?:^|[ \(\[])((?:[\.\w\d]+?)\.(?:com|org|net|us|bible)/?)(?:$|[ \.,!\)\]>])')):
        while True:
            match = re.search(regex, result_html, re_flags)
            if not match: break
            GlobalSettings.logger.debug(f"Found naked URL matchD{j}: '{match.group(1)}' inside '{match.group(0)}'")
            result_html = f'{result_html[:match.start(1)]}<a href="http://{match.group(1)}">{match.group(1)}</a>{result_html[match.end(1):]}'

    # Email addresses
    bracketed_email_search_re = r'<((?:[\._\w\d]+?)@(?:\w+?)\.(?:com|org|net|us|bible)/?)>'
    while True:
        match = re.search(bracketed_email_search_re, result_html, re_flags)
        if not match: break
        GlobalSettings.logger.debug(f"Found naked email matchE: '{match.group(1)}' inside '{match.group(0)}'")
        result_html = f'{result_html[:match.start(0)]}<a href="mailto:{match.group(1)}">{match.group(1)}</a>{result_html[match.end(0):]}'
    email_search_re = r'(?:^|[ \(\[])((?:[\._\w\d]+?)@(?:\w+?)\.(?:com|org|net|us|bible)/?)(?:$|[ \.,!\)\]<>])'
    while True:
        match = re.search(email_search_re, result_html, re_flags)
        if not match: break
        GlobalSettings.logger.debug(f"Found naked email matchF: '{match.group(1)}' inside '{match.group(0)}'")
        result_html = f'{result_html[:match.start(1)]}<a href="mailto:{match.group(1)}">{match.group(1)}</a>{result_html[match.end(1):]}'

    return result_html
