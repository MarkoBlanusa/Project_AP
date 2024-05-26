import tkinter as tk
import typing

import json

from interface.styling import *
from interface.scrollable_frame import ScrollableFrame

from connectors.binance import BinanceClient

from strategies import (
    TechnicalStrategy,
    BreakoutStrategy,
    FractalStrategy,
    DummyStrategy,
)
from utils import *

from database import WorkspaceData


if typing.TYPE_CHECKING:
    from interface.root_component import Root


class StrategyEditor(tk.Frame):
    def __init__(
        self,
        root: "Root",
        binance: BinanceClient,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.root = root

        self.db = WorkspaceData()

        self._valid_integer = self.register(check_integer_format)
        self._valid_float = self.register(check_float_format)

        self._exchanges = {"Binance": binance}

        self._all_contracts = []
        self._all_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

        for exchange, client in self._exchanges.items():
            for symbol, contract in client.contracts.items():
                self._all_contracts.append(symbol + "_" + exchange.capitalize())

        self._commands_frame = tk.Frame(self, bg=BG_COLOR)
        self._commands_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self._add_button = tk.Button(
            self._commands_frame,
            text="New strategy",
            font=("Arial", 12, "bold"),
            command=self._add_strategy_row,
            bg="#4CAF50",
            fg="white",
        )
        self._add_button.pack(side=tk.LEFT, padx=5)

        # Create a canvas for the scrollable frame
        self._canvas = tk.Canvas(self, bg=BG_COLOR)
        self._canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Create a horizontal scrollbar linked to the canvas
        self._h_scrollbar = tk.Scrollbar(
            self, orient=tk.HORIZONTAL, command=self._canvas.xview
        )
        self._h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self._canvas.configure(xscrollcommand=self._h_scrollbar.set)

        # Create a frame inside the canvas
        self._strategy_container = tk.Frame(self._canvas, bg=BG_COLOR)
        self._canvas.create_window((0, 0), window=self._strategy_container, anchor="nw")

        self._strategy_container.bind("<Configure>", self._on_frame_configure)

        self.body_widgets = dict()
        self.additional_parameters = dict()
        self._extra_input = dict()
        self._strategy_frames = dict()

        self._base_params = [
            {
                "code_name": "strategy_type",
                "widget": tk.OptionMenu,
                "data_type": str,
                "values": ["Technical", "Breakout", "Fractals", "Dummy"],
                "width": 20,
                "header": "Strategy",
            },
            {
                "code_name": "contract",
                "widget": tk.OptionMenu,
                "data_type": str,
                "values": self._all_contracts,
                "width": 20,
                "header": "Symbol",
            },
            {
                "code_name": "timeframe",
                "widget": tk.OptionMenu,
                "data_type": str,
                "values": self._all_timeframes,
                "width": 20,
                "header": "Timeframe",
            },
            {
                "code_name": "parameters",
                "widget": tk.Button,
                "data_type": float,
                "text": "Parameters",
                "bg": "#2196F3",
                "command": self._show_popup,
                "header": "",
                "width": 20,
            },
            {
                "code_name": "activation",
                "widget": tk.Button,
                "data_type": float,
                "text": "DEACTIVATED",
                "bg": "#F44336",
                "command": self._switch_strategy,
                "header": "",
                "width": 20,
            },
            {
                "code_name": "delete",
                "widget": tk.Button,
                "data_type": float,
                "text": "CLOSE",
                "bg": "#F44336",
                "command": self._delete_row,
                "header": "",
                "width": 20,
            },
        ]

        self.extra_params = {
            "Technical": [
                {
                    "code_name": "rsi_length",
                    "name": "RSI Periods",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "ema_fast",
                    "name": "MACD Fast Length",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "ema_slow",
                    "name": "MACD Slow Length",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "ema_signal",
                    "name": "MACD Signal Length",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "balance_pct",
                    "name": "Balance Pct",
                    "widget": tk.Entry,
                    "data_type": float,
                },
            ],
            "Breakout": [
                {
                    "code_name": "min_volume",
                    "name": "Minimum Volume",
                    "widget": tk.Entry,
                    "data_type": float,
                },
                {
                    "code_name": "balance_pct",
                    "name": "Balance Pct",
                    "widget": tk.Entry,
                    "data_type": float,
                },
            ],
            "Fractals": [
                {
                    "code_name": "rsi_length",
                    "name": "RSI Periods",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "ema_fast",
                    "name": "EMA Fast",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "ema_slow",
                    "name": "EMA Slow",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "ema_very_slow",
                    "name": "EMA Very Slow",
                    "widget": tk.Entry,
                    "data_type": int,
                },
                {
                    "code_name": "risk_pct",
                    "name": "Risk Percentage",
                    "widget": tk.Entry,
                    "data_type": float,
                },
            ],
            "Dummy": [
                {
                    "code_name": "balance_pct",
                    "name": "Balance Pct",
                    "widget": tk.Entry,
                    "data_type": float,
                },
            ],  # No extra parameters for the Dummy strategy
        }

        for h in self._base_params:
            self.body_widgets[h["code_name"]] = dict()
            if h["code_name"] in ["strategy_type", "contract", "timeframe"]:
                self.body_widgets[h["code_name"] + "_var"] = dict()

        self._body_index = 0

        self._load_workspace()

    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _add_strategy_row(self):
        b_index = self._body_index

        strategy_frame = tk.Frame(
            self._strategy_container, bg=BG_COLOR, bd=2, relief=tk.RIDGE
        )
        strategy_frame.pack(side=tk.LEFT, padx=10, pady=10)

        self._strategy_frames[b_index] = strategy_frame

        for idx, base_param in enumerate(self._base_params):
            code_name = base_param["code_name"]
            header = tk.Label(
                strategy_frame,
                text=base_param["header"],
                bg=BG_COLOR,
                fg="white",
                font=("Arial", 10, "bold"),
            )
            header.grid(row=idx, column=0, padx=5, pady=5)

            if base_param["widget"] == tk.OptionMenu:
                self.body_widgets[code_name + "_var"][b_index] = tk.StringVar()
                self.body_widgets[code_name + "_var"][b_index].set(
                    base_param["values"][0]
                )
                self.body_widgets[code_name][b_index] = tk.OptionMenu(
                    strategy_frame,
                    self.body_widgets[code_name + "_var"][b_index],
                    *base_param["values"],
                )
                self.body_widgets[code_name][b_index].config(
                    width=base_param["width"],
                    bd=0,
                    indicatoron=0,
                    bg="#4CAF50",
                    fg="white",
                )

            elif base_param["widget"] == tk.Entry:
                self.body_widgets[code_name][b_index] = tk.Entry(
                    strategy_frame,
                    justify=tk.CENTER,
                    bg="#4CAF50",
                    fg="white",
                    font=("Arial", 10),
                    bd=1,
                    width=base_param["width"],
                )

                if base_param["data_type"] == int:
                    self.body_widgets[code_name][b_index].config(
                        validate="key", validatecommand=(self._valid_integer, "%P")
                    )
                elif base_param["data_type"] == float:
                    self.body_widgets[code_name][b_index].config(
                        validate="key", validatecommand=(self._valid_float, "%P")
                    )

            elif base_param["widget"] == tk.Button:
                self.body_widgets[code_name][b_index] = tk.Button(
                    strategy_frame,
                    text=base_param["text"],
                    bg=base_param["bg"],
                    fg="white",
                    font=("Arial", 10, "bold"),
                    width=base_param["width"],
                    command=lambda frozen_command=base_param["command"]: frozen_command(
                        b_index
                    ),
                )
            else:
                continue

            self.body_widgets[code_name][b_index].grid(
                row=idx, column=1, padx=5, pady=5
            )

        self.additional_parameters[b_index] = dict()

        for strat, params in self.extra_params.items():
            for param in params:
                self.additional_parameters[b_index][param["code_name"]] = None

        self._body_index += 1

    def _delete_row(self, b_index: int):
        if b_index in self._strategy_frames:
            self._strategy_frames[b_index].destroy()
            del self._strategy_frames[b_index]

    def _show_popup(self, b_index: int):
        x = self.body_widgets["parameters"][b_index].winfo_rootx()
        y = self.body_widgets["parameters"][b_index].winfo_rooty()

        self._popup_window = tk.Toplevel(self)
        self._popup_window.wm_title("Parameters")

        self._popup_window.config(bg=BG_COLOR)
        self._popup_window.attributes("-topmost", "true")
        self._popup_window.grab_set()

        self._popup_window.geometry(f"+{x - 80}+{y + 30}")

        strat_selected = self.body_widgets["strategy_type_var"][b_index].get()

        row_nb = 0

        self._extra_input[b_index] = {}

        for param in self.extra_params[strat_selected]:
            code_name = param["code_name"]

            temp_label = tk.Label(
                self._popup_window,
                bg=BG_COLOR,
                fg=FG_COLOR,
                text=param["name"],
                font=BOLD_FONT,
            )
            temp_label.grid(row=row_nb, column=0)

            if param["widget"] == tk.Entry:
                self._extra_input[b_index][code_name] = tk.Entry(
                    self._popup_window,
                    bg=BG_COLOR_2,
                    justify=tk.CENTER,
                    fg=FG_COLOR,
                    insertbackground=FG_COLOR,
                    highlightthickness=False,
                )

                if param["data_type"] == int:
                    self._extra_input[b_index][code_name].config(
                        validate="key", validatecommand=(self._valid_integer, "%P")
                    )
                elif param["data_type"] == float:
                    self._extra_input[b_index][code_name].config(
                        validate="key", validatecommand=(self._valid_float, "%P")
                    )

                if self.additional_parameters[b_index][code_name] is not None:
                    self._extra_input[b_index][code_name].insert(
                        tk.END, str(self.additional_parameters[b_index][code_name])
                    )
            else:
                continue

            self._extra_input[b_index][code_name].grid(row=row_nb, column=1)

            row_nb += 1

        validation_button = tk.Button(
            self._popup_window,
            text="Validate",
            bg=BG_COLOR_2,
            fg=FG_COLOR,
            command=lambda: self._validate_parameters(b_index),
        )
        validation_button.grid(row=row_nb, column=0, columnspan=2)

    def _validate_parameters(self, b_index: int):
        strat_selected = self.body_widgets["strategy_type_var"][b_index].get()

        for param in self.extra_params[strat_selected]:
            code_name = param["code_name"]

            if self._extra_input[b_index][code_name].get() == "":
                self.additional_parameters[b_index][code_name] = None
            else:
                self.additional_parameters[b_index][code_name] = param["data_type"](
                    self._extra_input[b_index][code_name].get()
                )

        self._popup_window.destroy()

    def _switch_strategy(self, b_index: int):
        strat_selected = self.body_widgets["strategy_type_var"][b_index].get()

        for param in self.extra_params[strat_selected]:
            if self.additional_parameters[b_index][param["code_name"]] is None:
                self.root.logging_frame.add_log(
                    f"Missing {param['code_name']} parameter"
                )
                return

        symbol = self.body_widgets["contract_var"][b_index].get().split("_")[0]
        timeframe = self.body_widgets["timeframe_var"][b_index].get()
        exchange = self.body_widgets["contract_var"][b_index].get().split("_")[1]

        contract = self._exchanges[exchange].contracts[symbol]

        if self.body_widgets["activation"][b_index].cget("text") == "DEACTIVATED":

            if strat_selected == "Technical":
                new_strategy = TechnicalStrategy(
                    self._exchanges[exchange],
                    contract,
                    exchange,
                    timeframe,
                    self.additional_parameters[b_index],
                )
            elif strat_selected == "Breakout":
                new_strategy = BreakoutStrategy(
                    self._exchanges[exchange],
                    contract,
                    exchange,
                    timeframe,
                    self.additional_parameters[b_index],
                )
            elif strat_selected == "Fractals":
                new_strategy = FractalStrategy(
                    self._exchanges[exchange],
                    contract,
                    exchange,
                    timeframe,
                    self.additional_parameters[b_index],
                )
            elif strat_selected == "Dummy":
                new_strategy = DummyStrategy(
                    self._exchanges[exchange],
                    contract,
                    exchange,
                    timeframe,
                    self.additional_parameters[b_index],
                )
            else:
                return

            new_strategy.candles = self._exchanges[exchange].get_historical_candles(
                contract, timeframe
            )

            if len(new_strategy.candles) == 0:
                self.root.logging_frame.add_log(
                    f"No historical data retrieved for {contract.symbol}"
                )
                return

            if exchange == "Binance":
                self._exchanges[exchange].subscribe_channel([contract], "aggTrade")
                self._exchanges[exchange].subscribe_channel([contract], "bookTicker")

            self._exchanges[exchange].strategies[b_index] = new_strategy

            for param in self._base_params:
                code_name = param["code_name"]

                if code_name != "activation" and "_var" not in code_name:
                    self.body_widgets[code_name][b_index].config(state=tk.DISABLED)

            self.body_widgets["activation"][b_index].config(
                bg="green", text="ACTIVATED"
            )
            self.root.logging_frame.add_log(
                f"{strat_selected} strategy on {symbol} / {timeframe} started"
            )

        else:
            if b_index in self._exchanges[exchange].strategies:
                del self._exchanges[exchange].strategies[b_index]

            for param in self._base_params:
                code_name = param["code_name"]

                if code_name != "activation" and "_var" not in code_name:
                    self.body_widgets[code_name][b_index].config(state=tk.NORMAL)

            self.body_widgets["activation"][b_index].config(
                bg="red", text="DEACTIVATED"
            )
            self.root.logging_frame.add_log(
                f"{strat_selected} strategy on {symbol} / {timeframe} stopped"
            )

    def _load_workspace(self):
        data = self.db.get("strategies")

        for row in data:
            self._add_strategy_row()

            b_index = self._body_index - 1

            for base_param in self._base_params:
                code_name = base_param["code_name"]

                if base_param["widget"] == tk.OptionMenu and row[code_name] is not None:
                    self.body_widgets[code_name + "_var"][b_index].set(row[code_name])
                elif base_param["widget"] == tk.Entry and row[code_name] is not None:
                    self.body_widgets[code_name][b_index].insert(tk.END, row[code_name])

            extra_params = json.loads(row["extra_params"])

            for param, value in extra_params.items():
                if value is not None:
                    self.additional_parameters[b_index][param] = value
