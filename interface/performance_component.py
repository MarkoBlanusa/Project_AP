import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import numpy as np


class PerformanceDashboard(tk.Frame):
    def __init__(self, binance_client, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.binance_client = binance_client
        self.trades_data = self.get_trades_data()
        self.create_widgets()

    def create_widgets(self):
        self.stats_frame = tk.Frame(self, bg="lightgrey")
        self.stats_frame.pack(side=tk.TOP, fill=tk.X)

        self.pnl_chart_frame = tk.Frame(self, bg="lightgrey")
        self.pnl_chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.equity_curve_frame = tk.Frame(self, bg="lightgrey")
        self.equity_curve_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.create_stats()
        self.create_pnl_chart()
        self.create_equity_curve()

    def create_stats(self):
        stats = self.calculate_stats()

        stats_labels = [
            f"Total Trades: {stats['total_trades']}",
            f"Winning Trades: {stats['winning_trades']}",
            f"Losing Trades: {stats['losing_trades']}",
            f"Average PnL per Trade: {stats['average_pnl']:.2f}",
            f"Sharpe Ratio: {stats['sharpe_ratio']:.2f}",
            f"Sortino Ratio: {stats['sortino_ratio']:.2f}",
            f"Max Drawdown: {stats['max_drawdown']:.2f}",
        ]

        for i, text in enumerate(stats_labels):
            label = tk.Label(
                self.stats_frame, text=text, bg="lightgrey", font=("Arial", 12)
            )
            label.pack(side=tk.TOP, anchor="w", padx=10, pady=2)

    def create_pnl_chart(self):
        fig, ax = plt.subplots()
        pnl_data = self.get_pnl_data()
        ax.plot(
            pnl_data["timestamp"], pnl_data["cumulative_pnl"], label="Cumulative PnL"
        )
        ax.set_xlabel("Time")
        ax.set_ylabel("PnL")
        ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=self.pnl_chart_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def create_equity_curve(self):
        fig, ax = plt.subplots()
        equity_data = self.get_equity_data()
        ax.plot(equity_data["timestamp"], equity_data["equity"], label="Equity Curve")
        ax.set_xlabel("Time")
        ax.set_ylabel("Equity")
        ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=self.equity_curve_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def calculate_stats(self):
        total_trades = len(self.trades_data)
        winning_trades = sum(1 for trade in self.trades_data if trade.pnl > 0)
        losing_trades = total_trades - winning_trades
        average_pnl = (
            sum(trade.pnl for trade in self.trades_data) / total_trades
            if total_trades > 0
            else 0
        )
        sharpe_ratio = self.calculate_sharpe_ratio()
        sortino_ratio = self.calculate_sortino_ratio()
        max_drawdown = self.calculate_max_drawdown()

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "average_pnl": average_pnl,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
        }

    def get_trades_data(self):
        return self.binance_client.get_trade_history()

    def get_pnl_data(self):
        timestamps = [trade.time for trade in self.trades_data]
        pnl_values = [trade.pnl for trade in self.trades_data]
        cumulative_pnl = np.cumsum(pnl_values).tolist()

        return pd.DataFrame({"timestamp": timestamps, "cumulative_pnl": cumulative_pnl})

    def get_equity_data(self):
        initial_balance = 100000  # Replace with actual initial balance if available
        timestamps = [trade.time for trade in self.trades_data]
        equity_values = [
            initial_balance + sum(trade.pnl for trade in self.trades_data[: i + 1])
            for i in range(len(self.trades_data))
        ]

        return pd.DataFrame({"timestamp": timestamps, "equity": equity_values})

    def calculate_sharpe_ratio(self):
        returns = pd.Series([trade.pnl for trade in self.trades_data])
        mean_return = returns.mean()
        std_return = returns.std()
        return mean_return / std_return * np.sqrt(252) if std_return != 0 else 0

    def calculate_sortino_ratio(self):
        returns = pd.Series([trade.pnl for trade in self.trades_data])
        mean_return = returns.mean()
        negative_returns = returns[returns < 0]
        std_negative_return = negative_returns.std()
        return (
            mean_return / std_negative_return * np.sqrt(252)
            if std_negative_return != 0
            else 0
        )

    def calculate_max_drawdown(self):
        equity = self.get_equity_data()["equity"]
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        return drawdown.min()
