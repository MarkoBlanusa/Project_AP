import tkinter as tk
from tkinter import ttk
import typing
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import mplfinance as mpf
from datetime import datetime

from models import *

from connectors.binance import BinanceClient

from interface.styling import *
from interface.autocomplete_widget import Autocomplete
from interface.scrollable_frame import ScrollableFrame

from database import WorkspaceData


class Watchlist(tk.Frame):
    def __init__(
        self,
        binance_contracts: typing.Dict[str, Contract],
        binance_client: BinanceClient,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.db = WorkspaceData()

        self.binance_symbols = list(binance_contracts.keys())
        self.client = binance_client

        self._commands_frame = tk.Frame(self, bg=BG_COLOR)
        self._commands_frame.pack(side=tk.TOP, fill=tk.X)

        self._table_frame = tk.Frame(self, bg=BG_COLOR)
        self._table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._binance_label = tk.Label(
            self._commands_frame,
            text="Binance",
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=BOLD_FONT,
        )
        self._binance_label.grid(row=0, column=0)

        self._binance_entry = Autocomplete(
            self.binance_symbols,
            self._commands_frame,
            fg=FG_COLOR,
            justify=tk.CENTER,
            insertbackground=FG_COLOR,
            bg=BG_COLOR_2,
            highlightthickness=False,
        )
        self._binance_entry.bind("<Return>", self._add_binance_symbol)
        self._binance_entry.grid(row=1, column=0, padx=5)

        self.body_widgets = dict()

        self._headers = [
            "Symbol",
            "Exchange",
            "Bid",
            "Ask",
            "Last Price",
            "Volume",
            "Delete",
            "Display",
        ]

        self._headers_frame = tk.Frame(self._table_frame, bg=BG_COLOR)

        self._col_width = 12

        # Creates the headers dynamically
        for idx, h in enumerate(self._headers):
            header = tk.Label(
                self._headers_frame,
                text=h,
                bg=BG_COLOR,
                fg=FG_COLOR,
                font=BOLD_FONT,
                width=self._col_width,
            )
            header.grid(row=0, column=idx)

        header = tk.Label(
            self._headers_frame,
            text="",
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=BOLD_FONT,
            width=2,
        )
        header.grid(row=0, column=len(self._headers))

        self._headers_frame.pack(side=tk.TOP, anchor="nw")

        # Creates the table body
        self._body_frame = ScrollableFrame(self._table_frame, bg=BG_COLOR, height=250)
        self._body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, anchor="nw")

        # Add keys to the body_widgets dictionary, the keys represents columns or data related to a column
        for h in self._headers:
            self.body_widgets[h] = dict()
            if h in ["Bid", "Ask", "Last Price", "Volume"]:
                self.body_widgets[h + "_var"] = dict()

        self._body_index = 0

        # Loads the Watchlist symbols saved to the database during a previous session
        saved_symbols = self.db.get("watchlist")

        for s in saved_symbols:
            self._add_symbol(s["symbol"], s["exchange"])

    def _remove_symbol(self, b_index: int):
        for h in self._headers:
            self.body_widgets[h][b_index].grid_forget()
            del self.body_widgets[h][b_index]

    def _add_binance_symbol(self, event):
        symbol = event.widget.get()
        if symbol in self.binance_symbols:
            self._add_symbol(symbol, "Binance")
            event.widget.delete(0, tk.END)

    def _add_symbol(self, symbol: str, exchange: str):
        b_index = self._body_index

        self.body_widgets["Symbol"][b_index] = tk.Label(
            self._body_frame.sub_frame,
            text=symbol,
            bg=BG_COLOR,
            fg=FG_COLOR_2,
            font=GLOBAL_FONT,
            width=self._col_width,
        )
        self.body_widgets["Symbol"][b_index].grid(row=b_index, column=0)

        self.body_widgets["Exchange"][b_index] = tk.Label(
            self._body_frame.sub_frame,
            text=exchange,
            bg=BG_COLOR,
            fg=FG_COLOR_2,
            font=GLOBAL_FONT,
            width=self._col_width,
        )
        self.body_widgets["Exchange"][b_index].grid(row=b_index, column=1)

        self.body_widgets["Bid_var"][b_index] = tk.StringVar()
        self.body_widgets["Bid"][b_index] = tk.Label(
            self._body_frame.sub_frame,
            textvariable=self.body_widgets["Bid_var"][b_index],
            bg=BG_COLOR,
            fg=FG_COLOR_2,
            font=GLOBAL_FONT,
            width=self._col_width,
        )
        self.body_widgets["Bid"][b_index].grid(row=b_index, column=2)

        self.body_widgets["Ask_var"][b_index] = tk.StringVar()
        self.body_widgets["Ask"][b_index] = tk.Label(
            self._body_frame.sub_frame,
            textvariable=self.body_widgets["Ask_var"][b_index],
            bg=BG_COLOR,
            fg=FG_COLOR_2,
            font=GLOBAL_FONT,
            width=self._col_width,
        )
        self.body_widgets["Ask"][b_index].grid(row=b_index, column=3)

        self.body_widgets["Last Price_var"][b_index] = tk.StringVar()
        self.body_widgets["Last Price"][b_index] = tk.Label(
            self._body_frame.sub_frame,
            textvariable=self.body_widgets["Last Price_var"][b_index],
            bg=BG_COLOR,
            fg=FG_COLOR_2,
            font=GLOBAL_FONT,
            width=self._col_width,
        )
        self.body_widgets["Last Price"][b_index].grid(row=b_index, column=4)

        self.body_widgets["Volume_var"][b_index] = tk.StringVar()
        self.body_widgets["Volume"][b_index] = tk.Label(
            self._body_frame.sub_frame,
            textvariable=self.body_widgets["Volume_var"][b_index],
            bg=BG_COLOR,
            fg=FG_COLOR_2,
            font=GLOBAL_FONT,
            width=self._col_width,
        )
        self.body_widgets["Volume"][b_index].grid(row=b_index, column=5)

        self.body_widgets["Delete"][b_index] = tk.Button(
            self._body_frame.sub_frame,
            text="X",
            bg="darkred",
            fg=FG_COLOR,
            font=GLOBAL_FONT,
            command=lambda: self._remove_symbol(b_index),
            width=4,
        )
        self.body_widgets["Delete"][b_index].grid(row=b_index, column=6)

        self.body_widgets["Display"][b_index] = tk.Button(
            self._body_frame.sub_frame,
            text="Display",
            bg="blue",
            fg=FG_COLOR,
            font=GLOBAL_FONT,
            command=lambda: self._display_symbol(symbol),
            width=8,
        )
        self.body_widgets["Display"][b_index].grid(row=b_index, column=7)

        self._body_index += 1

    def _display_symbol(self, symbol: str):
        CandlePlotWindow(self, symbol, self.client)


class CandlePlotWindow(tk.Toplevel):
    def __init__(self, parent, symbol, client: BinanceClient):
        super().__init__(parent)
        self.symbol = symbol
        self.client = client
        self.title(f"Candlestick Chart - {self.symbol}")
        self.geometry("800x600")
        self.create_widgets()

        self.update_interval = 5000  # Update every 5 seconds
        self.max_candle = 30  # Set maximum limit to display
        self.update_plot()  # Start the update loop

    def create_widgets(self):
        self.timeframe_var = tk.StringVar(value="1m")
        timeframe_options = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
        self.timeframe_menu = tk.OptionMenu(
            self, self.timeframe_var, *timeframe_options, command=self.update_plot
        )
        self.timeframe_menu.pack(pady=5)

        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_plot(self, *args):
        timeframe = self.timeframe_var.get()
        contract = self.client.contracts.get(self.symbol)
        if contract is None:
            print(f"Contract for symbol {self.symbol} not found.")
            return

        historical_data = self.client.get_historical_candles(
            contract, interval=timeframe
        )

        if historical_data is not None and len(historical_data) > 0:
            self.ax.clear()
            limited_data = historical_data[-self.max_candle :]
            candlestick_data = [
                (
                    pd.Timestamp(candle.timestamp, unit="ms"),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                )
                for candle in limited_data
            ]
            candlestick_df = pd.DataFrame(
                candlestick_data, columns=["Date", "Open", "High", "Low", "Close"]
            )
            candlestick_df.set_index("Date", inplace=True)

            mpf.plot(candlestick_df, type="candle", ax=self.ax, style="charles")

            self.fig.autofmt_xdate()
            self.canvas.draw()
        else:
            print("No historical data available or fetched data is empty.")

        self.after(self.update_interval, self.update_plot)  # Schedule the next update
