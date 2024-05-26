import tkinter as tk
from tkinter.constants import *


class DraggableFrame(tk.PanedWindow):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.orient = VERTICAL
        self.bind("<Button-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        self.bind("<ButtonRelease-1>", self.stop_move)

        # Add resize handles
        self.resize_handle = tk.Frame(
            self, width=10, height=10, bg="black", cursor="arrow"
        )
        self.resize_handle.place(relx=1.0, rely=1.0, anchor="se")

        self.resize_handle.bind("<Button-1>", self.start_resize)
        self.resize_handle.bind("<B1-Motion>", self.do_resize)
        self.resize_handle.bind("<ButtonRelease-1>", self.stop_resize)

    def start_move(self, event):
        self._x = event.x
        self._y = event.y

    def do_move(self, event):
        x = self.winfo_x() - self._x + event.x
        y = self.winfo_y() - self._y + event.y
        self.place(x=x, y=y)

    def stop_move(self, event):
        self._x = None
        self._y = None

    def start_resize(self, event):
        self._x = event.x
        self._y = event.y
        self._width = self.winfo_width()
        self._height = self.winfo_height()

    def do_resize(self, event):
        new_width = self._width + (event.x - self._x)
        new_height = self._height + (event.y - self._y)
        if new_width > 100 and new_height > 50:  # Set minimum size limits
            self.config(width=new_width, height=new_height)
            self.resize_handle.place(relx=1.0, rely=1.0, anchor="se")
            self.update_idletasks()

    def stop_resize(self, event):
        self._x = None
        self._y = None
        self._width = None
        self._height = None
