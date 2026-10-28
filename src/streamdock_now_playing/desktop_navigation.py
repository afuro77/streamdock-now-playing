"""Desktop-only navigation; state and history never touch Spotify screens."""
class DesktopNavigation:
    def __init__(self, pages=1):self.pages=pages;self.page=0;self.screen=None;self.history=[]
    def open(self,screen):self.history.append((self.page,self.screen));self.screen=screen
    def home(self):self.page=0;self.screen=None;self.history.clear()
    def back(self):
        if self.history:self.page,self.screen=self.history.pop()
    def move(self,delta):
        if self.screen is None:self.page=max(0,min(self.pages-1,self.page+delta))
