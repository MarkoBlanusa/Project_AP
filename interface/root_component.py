import tkinter as tk
from tkinter.messagebox import askquestion
import logging
import json
import threading


from connectors.binance import BinanceClient

from interface.styling import *
from interface.logging_component import Logging
from interface.watchlist_component import Watchlist
from interface.trades_component import TradesWatch
from interface.strategy_component import StrategyEditor
from interface.performance_component import PerformanceDashboard
from interface.draggable_frame import DraggableFrame
from interface.scrollable_frame import ScrollableFrame
from interface.login_component import create_login_interface


logger = logging.getLogger()


class Root(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Trading Programm")
        self.geometry("1200x800")
        self.protocol("WM_DELETE_WINDOW", self._ask_before_close)
        self.configure(bg=BG_COLOR)

        self.binance = None

        self._set_scaling_factor(0.9)

        self.show_login_interface()

    def _set_scaling_factor(self, factor):
        self.tk.call("tk", "scaling", factor)

    def show_login_interface(self):
        self.login_frame = create_login_interface(self, self.on_login_success)
        self.login_frame.pack(fill="both", expand=True)

    def on_login_success(self, binance_client):
        self.binance = binance_client
        self.login_frame.pack_forget()
        self._initialize_main_interface()
        self._create_components()
        self._update_ui()

    def _initialize_main_interface(self):
        self.main_menu = tk.Menu(self)
        self.configure(menu=self.main_menu)

        self.workspace_menu = tk.Menu(self.main_menu, tearoff=False)
        self.main_menu.add_cascade(label="Interface", menu=self.workspace_menu)
        self.workspace_menu.add_command(
            label="Save interface", command=self._save_workspace
        )
        self.workspace_menu.add_command(
            label="Load interface", command=self._load_workspace
        )

        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=1)

        self.left_pane = tk.PanedWindow(self.paned_window, orient=tk.VERTICAL)
        self.paned_window.add(self.left_pane)

        self.right_pane = tk.PanedWindow(self.paned_window, orient=tk.VERTICAL)
        self.paned_window.add(self.right_pane)

        self.frames = {
            "watchlist": DraggableFrame(
                self.left_pane, width=200, height=300, bg="lightgrey"
            ),
            "trade": DraggableFrame(
                self.right_pane, width=400, height=300, bg="lightblue"
            ),
            "logging": DraggableFrame(
                self.left_pane, width=200, height=150, bg="lightyellow"
            ),
            "strategy": DraggableFrame(
                self.left_pane, width=200, height=150, bg="lightcoral"
            ),
            "performance": DraggableFrame(
                self.right_pane, width=800, height=400, bg="lightgreen"
            ),
        }

        self.left_pane.add(self.frames["watchlist"])
        self.right_pane.add(self.frames["trade"])
        self.left_pane.add(self.frames["logging"])
        self.left_pane.add(self.frames["strategy"])
        self.right_pane.add(self.frames["performance"])

    def _create_components(self):
        self._watchlist_frame = Watchlist(
            self.binance.contracts, self.binance, self.frames["watchlist"], bg=BG_COLOR
        )
        self._watchlist_frame.pack(fill=tk.BOTH, expand=True)

        self.logging_frame = Logging(self.frames["logging"], bg=BG_COLOR)
        self.logging_frame.pack(fill=tk.BOTH, expand=True)

        self._strategy_frame = StrategyEditor(
            self, self.binance, self.frames["strategy"], bg=BG_COLOR
        )
        self._strategy_frame.pack(fill=tk.BOTH, expand=True)

        self._trades_frame = TradesWatch(self.frames["trade"], bg=BG_COLOR)
        self._trades_frame.pack(fill=tk.BOTH, expand=True)

        scrollable_performance = ScrollableFrame(
            self.frames["performance"], bg=BG_COLOR, height=400
        )
        scrollable_performance.pack(fill=tk.BOTH, expand=True)
        self.performance_dashboard = PerformanceDashboard(
            self.binance, scrollable_performance.sub_frame, bg=BG_COLOR
        )
        self.performance_dashboard.pack(fill=tk.BOTH, expand=True)

    def _ask_before_close(self):
        result = askquestion(
            "Confirmation", "Do you really want to exit the application?"
        )
        if result == "yes":
            if self.binance:
                self.binance.reconnect = (
                    False  # Avoids the infinite reconnect loop in _start_ws()
                )
                self.binance.ws.close()
            self.destroy()  # Destroys the UI and terminates the program as no other thread is running

    def _update_ui(self):
        def fetch_data():
            if self.binance:
                for log in self.binance.logs:
                    if not log["displayed"]:
                        self.logging_frame.add_log(log["log"])
                        log["displayed"] = True

                for client in [self.binance]:
                    try:
                        for b_index, strat in client.strategies.items():
                            for log in strat.logs:
                                if not log["displayed"]:
                                    self.logging_frame.add_log(log["log"])
                                    log["displayed"] = True

                            for trade in strat.trades:
                                if (
                                    trade.time
                                    not in self._trades_frame.body_widgets["symbol"]
                                ):
                                    self._trades_frame.add_trade(trade)

                                precision = trade.contract.price_decimals
                                pnl_str = "{0:.{prec}f}".format(
                                    trade.pnl, prec=precision
                                )
                                self._trades_frame.body_widgets["pnl_var"][
                                    trade.time
                                ].set(pnl_str)
                                self._trades_frame.body_widgets["status_var"][
                                    trade.time
                                ].set(trade.status.capitalize())
                                self._trades_frame.body_widgets["quantity_var"][
                                    trade.time
                                ].set(trade.quantity)

                    except RuntimeError as e:
                        logger.error(
                            "Error while looping through strategies dictionary: %s", e
                        )

                try:
                    for key, value in self._watchlist_frame.body_widgets[
                        "Symbol"
                    ].items():
                        symbol = self._watchlist_frame.body_widgets["Symbol"][key].cget(
                            "text"
                        )
                        exchange = self._watchlist_frame.body_widgets["Exchange"][
                            key
                        ].cget("text")

                        if exchange == "Binance":
                            if symbol not in self.binance.contracts:
                                continue

                            if (
                                symbol
                                not in self.binance.ws_subscriptions["bookTicker"]
                                and self.binance.ws_connected
                            ):
                                self.binance.subscribe_channel(
                                    [self.binance.contracts[symbol]], "bookTicker"
                                )

                            prices = self.binance.get_bid_ask(
                                self.binance.contracts[symbol]
                            )
                            precision = self.binance.contracts[symbol].price_decimals

                            if prices:
                                if "bid" in prices and prices["bid"] is not None:
                                    price_str = "{0:.{prec}f}".format(
                                        prices["bid"], prec=precision
                                    )
                                    self._watchlist_frame.body_widgets["Bid_var"][
                                        key
                                    ].set(price_str)
                                if "ask" in prices and prices["ask"] is not None:
                                    price_str = "{0:.{prec}f}".format(
                                        prices["ask"], prec=precision
                                    )
                                    self._watchlist_frame.body_widgets["Ask_var"][
                                        key
                                    ].set(price_str)
                                if "last" in prices and prices["last"] is not None:
                                    last_price_str = "{0:.{prec}f}".format(
                                        prices["last"], prec=precision
                                    )
                                    self._watchlist_frame.body_widgets[
                                        "Last Price_var"
                                    ][key].set(last_price_str)
                                if "volume" in prices and prices["volume"] is not None:
                                    volume_str = "{0:.{prec}f}".format(
                                        prices["volume"], prec=precision
                                    )
                                    self._watchlist_frame.body_widgets["Volume_var"][
                                        key
                                    ].set(volume_str)

                except RuntimeError as e:
                    logger.error(
                        "Error while looping through watchlist dictionary: %s", e
                    )

            self.after(1500, self._update_ui)

        threading.Thread(target=fetch_data).start()

    def _save_workspace(self):
        layout = {
            name: {
                "x": frame.winfo_x(),
                "y": frame.winfo_y(),
                "width": frame.winfo_width(),
                "height": frame.winfo_height(),
            }
            for name, frame in self.frames.items()
        }
        with open("layout_config.json", "w") as file:
            json.dump(layout, file)

        self.logging_frame.add_log("Interface saved")

    def _load_workspace(self):
        try:
            with open("layout_config.json", "r") as file:
                layout = json.load(file)
            for name, frame in self.frames.items():
                if name in layout:
                    frame.place(x=layout[name]["x"], y=layout[name]["y"])
                    frame.config(
                        width=layout[name]["width"], height=layout[name]["height"]
                    )
        except FileNotFoundError:
            self.logging_frame.add_log("No saved interface found")
