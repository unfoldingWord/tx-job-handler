import re
from abc import abstractmethod, ABCMeta
from bs4 import BeautifulSoup
import markdown

from linters.py_markdown_linter.options import IntOption

RE_HEADERS = re.compile('^h[1-6]$')


class Rule(metaclass=ABCMeta):
    """ Class representing markdown rules. """
    options_spec = []
    id = []
    name = ""
    error_str = ""

    def __init__(self, opts={}):
        self.options = {}
        for op_spec in self.options_spec:
            self.options[op_spec.name] = op_spec
            actual_option = opts.get(op_spec.name)
            if actual_option:
                self.options[op_spec.name].set(actual_option)

    def __eq__(self, other):
        return self.id == other.id and self.name == other.name

    @abstractmethod
    def validate(self):
        pass


class FileRule(Rule):
    """ Class representing rules that act on an entire file """

    @staticmethod
    def md_to_tree(md):
        """
        Converts a string of pure markdown into a bs4 object. Makes parsing much
        easier, but not necessarily faster.
        """
        return BeautifulSoup(markdown.markdown(md, extensions=['md_in_html', 'tables', 'footnotes']), "html.parser")


class LineRule(Rule):
    """ Class representing rules that act on a line by line basis """
    pass


class RuleViolation:
    def __init__(self, rule_id, message, line_nr=None):
        self.rule_id = rule_id
        self.line_nr = line_nr
        self.message = message

    def __eq__(self, other):
        return self.rule_id == other.rule_id and self.message == other.message and self.line_nr == other.line_nr

    def __str__(self):
        return "{0}: {1} {2}".format(self.line_nr, self.rule_id, self.message)

    def __repr__(self):
        return self.__str__()


class HeaderIncrement(FileRule):
    """Rule: Header levels should only increment 1 level at a time."""
    name = "header-increment"
    id = "MD001"
    error_str = "Headers don't increment"

    def validate(self, lines):
        soup = self.md_to_tree(lines)
        old_level = None
        for header in soup.find_all(RE_HEADERS):
            level = int(header.name[-1])
            if old_level and level > old_level + 1:
                return RuleViolation(self.id, self.error_str)
            old_level = level


class TopLevelHeader(FileRule):
    """Rule: First header of the file must be h1."""
    name = "first-header-h1"
    id = "MD002"
    options_spec = [IntOption("first-header-level", 1, "Top level header")]
    error_str = "First header of the file must be top level header"

    def validate(self, lines):
        soup = self.md_to_tree(lines)
        top_level = self.options['first-header-level'].value
        first_header = soup.find(RE_HEADERS)
        if first_header:
            first_header_level = int(first_header.name[-1])
            if top_level != first_header_level:
                return RuleViolation(self.id, self.error_str)


class TrailingWhiteSpace(LineRule):
    """Rule: No line may have trailing whitespace."""
    name = "trailing-whitespace"
    id = "MD009"
    error_str = "Line has trailing whitespace"

    def validate(self, line):
        pattern = re.compile(r"\s$")
        if pattern.search(line):
            return RuleViolation(self.id, self.error_str)


class HardTab(LineRule):
    """Rule: No line may contain tab (\\t) characters."""
    name = "hard-tab"
    id = "MD010"
    error_str = "Line contains hard tab characters (\\t)"

    def validate(self, line):
        if "\t" in line:
            return RuleViolation(self.id, self.error_str)


class MaxLineLengthRule(LineRule):
    """Rule: No line may exceed 80 (default) characters in length."""
    name = "max-line-length"
    id = "MD013"
    options_spec = [IntOption('line-length', 80, "Max line length")]
    error_str = "Line exceeds max length ({0}>{1})"

    def validate(self, line):
        max_length = self.options['line-length'].value
        if len(line) > max_length:
            return RuleViolation(self.id, self.error_str.format(len(line), max_length))
