from tx_usfm_tools.support import abstractRenderer

#
#   Simplest renderer. Ignores everything except ascii text.
#

class MarkdownRenderer(abstractRenderer.AbstractRenderer):

    def __init__(self, inputDir, outputFilename):
        # Unset
        self.f = None  # output file stream
        # IO
        self.outputFilename = outputFilename
        self.inputDir = inputDir
        # Position
        self.currentC = 1
        self.book = ''

    def render(self):
        self.f = open(self.outputFilename, 'wt', encoding='utf_8')
        self.loadUSFM(self.inputDir)
        self.run()
        self.f.close()

    def writeLog(self, s):
        print(s)

    # Support

    def escape(self, s):
        return s

    def renderTEXT(self, token):    self.f.write(self.escape(token.value))

    def renderH(self, token):       self.book = token.getValue()
    def renderMT(self, token):      self.f.write('\n\n# ' + token.value.upper() + '\n\n')
    def renderMT2(self, token):     self.f.write('\n\n## ' + token.value.upper() + '\n\n')
    def renderMS(self, token):      self.f.write('\n\n' + token.value + '\n' + ('=' * len(token.value)) + '\n\n')
    def renderMS2(self, token):     self.f.write('\n\n' + token.value + '\n' + ('-' * len(token.value)) + '\n\n')
    def renderP(self, token):       self.f.write('\n\n')
    def renderB(self, token):       self.f.write('\n\n')
    def renderS(self, token):       self.f.write('\n \n') # Was '\n\ \n' !!! What should it be???
    def renderS2(self, token):      self.f.write('\n \n') # Was '\n\ \n' !!! What should it be???
    def renderC(self, token):       self.currentC = token.value; self.f.write('\n\n [' + self.book + ' ' + self.currentC + ' ] \n\n')
    def renderV(self, token):       self.f.write(' [' + self.currentC + ':' + token.value + '] ')
    def renderQ(self, token):       self.f.write('\n|  ')
    def renderQ1(self, token):      self.f.write('\n|  ')
    def renderQ2(self, token):      self.f.write('\n|    ')
    def renderQ3(self, token):      self.f.write('\n|      ')
    def renderNB(self, token):      self.f.write('\n|  ')
    def renderLI(self, token):      self.f.write('* ')
    def renderPBR(self, token):     self.f.write('\n')

    def renderBDS(self, token):     self.f.write( '**')
    def renderBDE(self, token):     self.f.write( '**')
    def renderBDITS(self, token):   pass
    def renderBDITE(self, token):   pass

    def renderFS(self,token):       self.f.write('^[')
    def renderFE(self,token):       self.f.write(']')
    def renderFR(self, token):      self.f.write(self.escape(token.value))
    def renderFT(self, token):      self.f.write(self.escape(token.value))
    def renderFQ(self, token):      self.f.write(self.escape(token.value))
    def renderFP(self,token):       self.f.write('\n\n')

    def renderXS(self,token):       self.f.write('^[')
    def renderXE(self,token):       self.f.write(']')
    def renderXO(self, token):      self.f.write(self.escape(token.value))
    def renderXT(self, token):      self.f.write(self.escape(token.value))

    def render_imt1(self, token):   self.f.write('\n\n## ' + token.value.upper() + '\n\n')
    def render_imt2(self, token):   self.f.write('\n\n### ' + token.value.upper() + '\n\n')
    def render_imt3(self, token):   self.f.write('\n\n#### ' + token.value.upper() + '\n\n')

