from tx_usfm_tools.support import abstractRenderer
from tx_usfm_tools.support import books

#
#   UTF-8 CVS file
#

class CSVRenderer(abstractRenderer.AbstractRenderer):

    def __init__(self, inputDir, outputFilename):
        # Unset
        self.f = None  # output file stream
        # IO
        self.outputFilename = outputFilename
        self.inputDir = inputDir
        # Flags
        self.cb = ''    # Current Book
        self.cc = '001'    # Current Chapter
        self.cv = '001'    # Currrent Verse
        self.infootnote = False

    def render(self):
        self.f = open(self.outputFilename, 'wt', encoding='utf_8')
        self.loadUSFM(self.inputDir)
        self.run()
        self.f.close()

    def writeLog(self, s):
        print(s)

    #   SUPPORT

    def escape(self, s):
        return '' if self.infootnote else s

    #   TOKENS

    def renderID(self, token):
        self.cb = books.bookKeyForIdValue(token.value)
    def renderC(self, token):
        self.cc = token.value.zfill(3)
    def renderV(self, token):
        self.cv = token.value.zfill(3)
        self.f.write('\n' + str(int(self.cb)) + ',' + str(int(self.cc)) + ',' + self.cv   + ',')
    def renderTEXT(self, token):    self.f.write(self.escape(token.value) + ' ')
    def renderFS(self, token):      self.infootnote = True
    def renderFE(self, token):      self.infootnote = False
