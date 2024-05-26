import tkinter as tk

from models import *

from connectors.binance import BinanceClient

from interface.styling import *


class RealTimeDashboard(tk.Frame):
    def __init__(self, parent, binance_client: BinanceClient, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.client = binance_client
        self.configure(bg=BG_COLOR)
        self.create_widgets()
        self.update_interval = 10000  # Update every 10 seconds
        self.update_dashboard()

    def create_widgets(self):
        self.balance_label = tk.Label(
            self, text="Account Balance:", bg=BG_COLOR, fg=FG_COLOR, font=GLOBAL_FONT
        )
        self.balance_label.pack(pady=5)

        self.balance_value = tk.Label(
            self, text="0.00 USDT", bg=BG_COLOR, fg=FG_COLOR, font=GLOBAL_FONT
        )
        self.balance_value.pack(pady=5)

        self.market_data_label = tk.Label(
            self, text="Market Data:", bg=BG_COLOR, fg=FG_COLOR, font=GLOBAL_FONT
        )
        self.market_data_label.pack(pady=5)

        self.market_data_value = tk.Label(
            self,
            text="Bid: 0.00 | Ask: 0.00",
            bg=BG_COLOR,
            fg=FG_COLOR,
            font=GLOBAL_FONT,
        )
        self.market_data_value.pack(pady=5)

    def update_dashboard(self):
        # Update balance information
        balances = self.client.get_balances()
        if self.client.futures:
            usdt_balance = balances.get(
                "USDT", Balance({"walletBalance": 0}, "binance_futures")
            ).wallet_balance
        else:
            usdt_balance = balances.get(
                "USDT", Balance({"free": 0, "locked": 0}, "binance_spot")
            ).free
        self.balance_value.config(text=f"{usdt_balance:.2f} USDT")

        # Update market data information
        contract = self.client.contracts.get("BTCUSDT")
        if contract:
            prices = self.client.get_bid_ask(contract)
            self.market_data_value.config(
                text=f"Bid: {prices['bid']:.1f} | Ask: {prices['ask']:.1f}"
            )

        self.after(self.update_interval, self.update_dashboard)
