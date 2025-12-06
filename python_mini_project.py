import wx
import random
import os
from enum import Enum

# =========================
# High-score manager
# =========================
class HighScoreManager:
    def __init__(self, filename: str = "snake_highscore.txt"):
        self.filename = filename
        self._score = 0
        self._load()

    def _path(self):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            base = os.getcwd()
        return os.path.join(base, self.filename)

    def _load(self):
        path = self._path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    txt = f.read().strip()
                    self._score = int(txt) if txt else 0
            except Exception:
                self._score = 0

    @property
    def score(self):
        return self._score

    def save_if_high(self, value: int) -> bool:
        if value > self._score:
            self._score = int(value)
            try:
                with open(self._path(), "w") as f:
                    f.write(str(self._score))
            except Exception:
                pass
            return True
        return False


# =========================
# Enums and Config
# =========================
class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


class GameState(Enum):
    RUNNING = 1
    PAUSED = 2
    GAME_OVER = 3


class GameConfig:
    def __init__(self):
        self.cols = 32
        self.rows = 22
        self.base_speed_ms = 200
        self.margin_px = 16


# =========================
# Snake Game Panel
# =========================
class SnakeGamePanel(wx.Panel):
    def __init__(self, parent, frame, config: GameConfig, highscores: HighScoreManager):
        super().__init__(parent, style=wx.WANTS_CHARS)
        self.frame = frame
        self.config = config
        self.highscores = highscores

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_LEFT_DOWN, lambda e: self.SetFocus())

        self.timer = wx.Timer(self)
        self.cell = 20
        self.play_rect = wx.Rect(0, 0, 100, 100)

        self.state = GameState.RUNNING
        self.direction = Direction.RIGHT
        self.next_direction = self.direction
        self.score = 0
        self.snake = []
        self.apple = None
        self.overlay_text = ""

        self.init_game()

    # -------- Game logic --------
    def init_game(self):
        self.state = GameState.RUNNING
        self.direction = Direction.RIGHT
        self.next_direction = self.direction
        self.score = 0
        self.timer.Start(self.config.base_speed_ms)

        head = (self.config.cols // 2, self.config.rows // 2)
        self.snake = [head, (head[0] - 1, head[1]), (head[0] - 2, head[1])]
        self.place_apple()
        self.overlay_text = "Use arrow keys to move"
        self.frame.update_scores(self.score, self.highscores.score)
        self.Refresh(False)
        self.SetFocus()

    def place_apple(self):
        free = [
            (x, y)
            for x in range(self.config.cols)
            for y in range(self.config.rows)
            if (x, y) not in self.snake
        ]
        self.apple = random.choice(free) if free else None

    def on_size(self, event):
        self.update_geometry()
        event.Skip()

    def update_geometry(self):
        w, h = self.GetClientSize()
        m = self.config.margin_px
        usable_w = max(10, w - 2 * m)
        usable_h = max(10, h - 2 * m)
        cs = int(min(usable_w / self.config.cols, usable_h / self.config.rows))
        cs = max(12, cs)
        self.cell = cs
        board_w = self.config.cols * cs
        board_h = self.config.rows * cs
        x = (w - board_w) // 2
        y = (h - board_h) // 2
        self.play_rect = wx.Rect(x, y, board_w, board_h)

    def on_key_down(self, event):
        key = event.GetKeyCode()

        if key in (ord("P"), ord("p")):
            self.state = (
                GameState.PAUSED
                if self.state == GameState.RUNNING
                else GameState.RUNNING
            )
            self.overlay_text = "PAUSED" if self.state == GameState.PAUSED else ""
            self.Refresh(False)
            return

        if key in (wx.WXK_SPACE, wx.WXK_RETURN) and self.state == GameState.GAME_OVER:
            self.init_game()
            return

        mapping = {
            wx.WXK_UP: Direction.UP,
            wx.WXK_DOWN: Direction.DOWN,
            wx.WXK_LEFT: Direction.LEFT,
            wx.WXK_RIGHT: Direction.RIGHT,
        }
        if key in mapping:
            new_dir = mapping[key]
            if not self.is_opposite(new_dir, self.direction):
                self.next_direction = new_dir
            self.overlay_text = ""
        event.Skip()

    @staticmethod
    def is_opposite(a: Direction, b: Direction) -> bool:
        ax, ay = a.value
        bx, by = b.value
        return ax + bx == 0 and ay + by == 0

    def on_timer(self, event):
        if self.state == GameState.RUNNING:
            self.step()

    def step(self):
        if self.is_opposite(self.next_direction, self.direction):
            self.next_direction = self.direction

        self.direction = self.next_direction
        dx, dy = self.direction.value
        head_x, head_y = self.snake[0]
        new_head = (head_x + dx, head_y + dy)

        if (
            new_head[0] < 0
            or new_head[0] >= self.config.cols
            or new_head[1] < 0
            or new_head[1] >= self.config.rows
            or new_head in self.snake
        ):
            self.game_over()
            return

        self.snake.insert(0, new_head)

        if self.apple and new_head == self.apple:
            self.score += 10
            self.place_apple()
            self.highscores.save_if_high(self.score)
            self.frame.update_scores(self.score, self.highscores.score)

            if self.score % 30 == 0:
                new_speed = max(40, self.config.base_speed_ms - 10)
                self.config.base_speed_ms = new_speed
                self.timer.Start(new_speed)
        else:
            self.snake.pop()

        self.Refresh(False)

    def game_over(self):
        self.state = GameState.GAME_OVER
        self.timer.Stop()
        self.highscores.save_if_high(self.score)
        self.frame.update_scores(self.score, self.highscores.score)

        dlg = wx.MessageDialog(
            self, "Game Over! Retry?", "Game Over", wx.YES_NO | wx.ICON_QUESTION
        )
        res = dlg.ShowModal()
        dlg.Destroy()

        if res == wx.ID_NO and self.frame.menu:
            self.frame.Close()
            self.frame.menu.return_to_menu()
        elif res == wx.ID_YES:
            self.init_game()

    # -------- Drawing --------
    def cell_rect(self, pos, shrink=2):
        x, y = pos
        pr = self.play_rect
        r = wx.Rect(
            pr.x + x * self.cell,
            pr.y + y * self.cell,
            self.cell,
            self.cell,
        )
        r.Deflate(shrink, shrink)
        return r

    def draw_snake(self, dc):
        if not self.snake:
            return

        for i, seg in enumerate(self.snake):
            rect = self.cell_rect(seg, 3)
            head = (i == 0)
            top = wx.Colour(70, 255, 110) if head else wx.Colour(40, 200, 80)
            bottom = wx.Colour(20, 140, 50) if head else wx.Colour(10, 90, 30)
            dc.GradientFillLinear(rect, top, bottom, wx.SOUTH)
            dc.SetPen(wx.Pen(wx.Colour(0, 0, 0), 1))
            dc.DrawRoundedRectangle(rect, 6)

        # eyes on head
        head_pos = self.snake[0]
        hrect = self.cell_rect(head_pos, 6)
        cx = hrect.x + hrect.width // 2
        cy = hrect.y + hrect.height // 2
        dx, dy = self.direction.value
        eye_offset = self.cell // 4

        dc.SetBrush(wx.Brush(wx.Colour(255, 255, 255)))
        dc.SetPen(wx.Pen(wx.Colour(0, 0, 0), 1))

        if dx > 0:       # right
            ex1, ey1 = cx + eye_offset, cy - eye_offset // 2
            ex2, ey2 = cx + eye_offset, cy + eye_offset // 2
        elif dx < 0:     # left
            ex1, ey1 = cx - eye_offset, cy - eye_offset // 2
            ex2, ey2 = cx - eye_offset, cy + eye_offset // 2
        elif dy > 0:     # down
            ex1, ey1 = cx - eye_offset // 2, cy + eye_offset
            ex2, ey2 = cx + eye_offset // 2, cy + eye_offset
        else:            # up
            ex1, ey1 = cx - eye_offset // 2, cy - eye_offset
            ex2, ey2 = cx + eye_offset // 2, cy - eye_offset

        dc.DrawCircle(ex1, ey1, 3)
        dc.DrawCircle(ex2, ey2, 3)

    def draw_apple(self, dc):
        if not self.apple:
            return

        rect = self.cell_rect(self.apple, 4)
        dc.SetPen(wx.Pen(wx.Colour(120, 0, 0), 2))
        dc.SetBrush(wx.Brush(wx.Colour(230, 40, 40)))
        dc.DrawEllipse(rect)

        # highlight
        highlight = wx.Rect(rect.x + 2, rect.y + 2, rect.width // 2, rect.height // 2)
        dc.SetBrush(wx.Brush(wx.Colour(255, 210, 210, 180)))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawEllipse(highlight)

        # stem
        stem_x = rect.x + rect.width // 2
        dc.SetPen(wx.Pen(wx.Colour(80, 50, 20), 2))
        dc.DrawLine(stem_x, rect.y, stem_x, rect.y - 6)

        # leaf
        leaf = wx.Rect(stem_x + 1, rect.y - 8, 10, 6)
        dc.SetBrush(wx.Brush(wx.Colour(40, 200, 80)))
        dc.SetPen(wx.Pen(wx.Colour(20, 110, 40), 1))
        dc.DrawRoundedRectangle(leaf, 3)

    def draw_grid(self, dc):
        pen = wx.Pen(wx.Colour(255, 255, 255, 60), 1)
        dc.SetPen(pen)
        pr = self.play_rect

        for c in range(self.config.cols + 1):
            x = pr.x + c * self.cell
            dc.DrawLine(x, pr.y, x, pr.y + pr.height)

        for r in range(self.config.rows + 1):
            y = pr.y + r * self.cell
            dc.DrawLine(pr.x, y, pr.x + pr.width, y)

    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        self.update_geometry()
        w, h = self.GetClientSize()

        dc.GradientFillLinear(
            (0, 0, w, h),
            wx.Colour(15, 25, 60),
            wx.Colour(0, 130, 150),
            wx.SOUTH,
        )

        pr = self.play_rect
        dc.SetPen(wx.Pen(wx.Colour(230, 230, 230), 3))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRoundedRectangle(pr.x - 4, pr.y - 4, pr.width + 8, pr.height + 8, 12)

        self.draw_grid(dc)
        self.draw_snake(dc)
        self.draw_apple(dc)


# =========================
# Snake Frame
# =========================
class SnakeFrame(wx.Frame):
    def __init__(self, menu=None):
        super().__init__(None, title="Snake", size=(900, 700))
        self.menu = menu
        self.highscores = HighScoreManager()
        self.config = GameConfig()

        root = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        hud = wx.Panel(root)
        hud.SetBackgroundColour(wx.Colour(10, 20, 45))
        hud_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.lbl_score = wx.StaticText(hud, label="Score: 0")
        self.lbl_high = wx.StaticText(
            hud, label=f"High Score: {self.highscores.score}"
        )

        for lbl in (self.lbl_score, self.lbl_high):
            font = wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
            lbl.SetFont(font)
            lbl.SetForegroundColour(wx.Colour(255, 255, 255))

        hud_sizer.Add(self.lbl_score, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        hud_sizer.AddStretchSpacer()
        hud_sizer.Add(self.lbl_high, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        hud.SetSizer(hud_sizer)

        sizer.Add(hud, 0, wx.EXPAND)
        self.game_panel = SnakeGamePanel(root, self, self.config, self.highscores)
        sizer.Add(self.game_panel, 1, wx.EXPAND | wx.ALL, 8)

        root.SetSizer(sizer)
        self.Centre()

    def update_scores(self, score, high):
        self.lbl_score.SetLabel(f"Score: {score}")
        self.lbl_high.SetLabel(f"High Score: {high}")


# =========================
# Menu Frame (full window, black)
# =========================
class SnakeMenu(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Snake Menu", size=(900, 700))
        self.highscores = HighScoreManager()

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.BLACK)

        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="ULTRA SNAKE")
        title_font = wx.Font(40, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        title.SetForegroundColour(wx.Colour(0, 200, 255))

        diff_label = wx.StaticText(panel, label="Select Difficulty:")
        diff_font = wx.Font(18, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        diff_label.SetFont(diff_font)
        diff_label.SetForegroundColour(wx.Colour(255, 255, 255))

        self.diff_choice = wx.Choice(panel, choices=["Easy", "Normal", "Hard"])
        self.diff_choice.SetSelection(1)
        self.diff_choice.SetFont(wx.Font(16, wx.FONTFAMILY_SWISS,
                                         wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        self.lbl_high = wx.StaticText(panel, label=f"High Score: {self.highscores.score}")
        high_font = wx.Font(22, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.lbl_high.SetFont(high_font)
        self.lbl_high.SetForegroundColour(wx.Colour(0, 255, 127))

        btn_play = wx.Button(panel, label="Play", size=(240, 70))
        btn_quit = wx.Button(panel, label="Quit", size=(240, 70))

        btn_play.SetBackgroundColour(wx.Colour(0, 200, 110))
        btn_play.SetForegroundColour(wx.BLACK)
        btn_play.SetFont(wx.Font(22, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        btn_quit.SetBackgroundColour(wx.Colour(200, 40, 40))
        btn_quit.SetForegroundColour(wx.WHITE)
        btn_quit.SetFont(wx.Font(22, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        sizer.AddStretchSpacer()
        sizer.Add(title, 0, wx.ALIGN_CENTER | wx.BOTTOM, 40)
        sizer.Add(diff_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        sizer.Add(self.diff_choice, 0, wx.ALIGN_CENTER | wx.BOTTOM, 35)
        sizer.Add(self.lbl_high, 0, wx.ALIGN_CENTER | wx.BOTTOM, 50)
        sizer.Add(btn_play, 0, wx.ALIGN_CENTER | wx.BOTTOM, 20)
        sizer.Add(btn_quit, 0, wx.ALIGN_CENTER | wx.BOTTOM, 20)
        sizer.AddStretchSpacer()

        panel.SetSizer(sizer)

        btn_quit.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        btn_play.Bind(wx.EVT_BUTTON, self.on_play)

        self.Centre()
        self.Show()

    def on_play(self, event):
        diff = self.diff_choice.GetStringSelection()
        self.game_frame = SnakeFrame(menu=self)

        if diff == "Easy":
            self.game_frame.game_panel.config.base_speed_ms = 250
        elif diff == "Normal":
            self.game_frame.game_panel.config.base_speed_ms = 180
        else:
            self.game_frame.game_panel.config.base_speed_ms = 120

        self.game_frame.Show()
        self.game_frame.Raise()
        self.game_frame.game_panel.SetFocus()
        self.Hide()

    def return_to_menu(self):
        self.lbl_high.SetLabel(f"High Score: {self.highscores.score}")
        self.Show()
        self.Raise()


# =========================
# Entry Point
# =========================
if __name__ == "__main__":
    app = wx.App(False)
    SnakeMenu()
    app.MainLoop()
