import logging
from typing import *
import time
from threading import Timer
import pandas as pd
from models import *

if TYPE_CHECKING:  # Import the connector class names only for typing purpose
    from connectors.binance import BinanceClient

logger = logging.getLogger()

TF_EQUIV = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}


class Strategy:
    def __init__(
        self,
        client: Union["BinanceClient"],
        contract: Contract,
        exchange: str,
        timeframe: str,
        strat_name: str,
    ):
        self.client = client
        self.contract = contract
        self.exchange = exchange
        self.tf = timeframe
        self.tf_equiv = TF_EQUIV[timeframe] * 1000
        self.strat_name = strat_name

        self.ongoing_position = False
        self.candles: List[Candle] = []
        self.trades: List[Trade] = []
        self.logs = []

    def _add_log(self, msg: str):
        logger.info("%s", msg)
        self.logs.append({"log": msg, "displayed": False})

    def get_trade_size(self, price: float) -> float:
        """
        Compute the trade size. This method should be overridden by each specific strategy.
        :param price: The current price of the asset
        :return: The computed trade size
        """
        raise NotImplementedError(
            "get_trade_size method should be implemented by each strategy."
        )

    def parse_trades(self, price: float, size: float, timestamp: int) -> str:
        timestamp_diff = int(time.time() * 1000) - timestamp
        if timestamp_diff >= 2000:
            logger.warning(
                "%s %s: %s milliseconds of difference between the current time and the trade time",
                self.exchange,
                self.contract.symbol,
                timestamp_diff,
            )

        last_candle = self.candles[-1]

        if timestamp < last_candle.timestamp + self.tf_equiv:
            last_candle.close = price
            last_candle.volume += size

            if price > last_candle.high:
                last_candle.high = price
            elif price < last_candle.low:
                last_candle.low = price

            for trade in self.trades:
                if trade.status == "open" and trade.entry_price is not None:
                    self._check_tp_sl(trade)

            return "same_candle"

        elif timestamp >= last_candle.timestamp + 2 * self.tf_equiv:
            missing_candles = (
                int((timestamp - last_candle.timestamp) / self.tf_equiv) - 1
            )

            logger.info(
                "%s missing %s candles for %s %s (%s %s)",
                self.exchange,
                missing_candles,
                self.contract.symbol,
                self.tf,
                timestamp,
                last_candle.timestamp,
            )

            for missing in range(missing_candles):
                new_ts = last_candle.timestamp + self.tf_equiv
                candle_info = {
                    "ts": new_ts,
                    "open": last_candle.close,
                    "high": last_candle.close,
                    "low": last_candle.close,
                    "close": last_candle.close,
                    "volume": 0,
                }
                new_candle = Candle(candle_info, self.tf, "parse_trade")

                self.candles.append(new_candle)
                last_candle = new_candle

            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {
                "ts": new_ts,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": size,
            }
            new_candle = Candle(candle_info, self.tf, "parse_trade")
            self.candles.append(new_candle)

            return "new_candle"

        elif timestamp >= last_candle.timestamp + self.tf_equiv:
            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {
                "ts": new_ts,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": size,
            }
            new_candle = Candle(candle_info, self.tf, "parse_trade")
            self.candles.append(new_candle)

            logger.info(
                "%s New candle for %s %s", self.exchange, self.contract.symbol, self.tf
            )

            return "new_candle"

    def _check_order_status(self, order_id):
        order_status = self.client.get_order_status(self.contract, order_id)

        if order_status is not None:
            logger.info("%s order status: %s", self.exchange, order_status.status)
            if order_status.status == "filled":
                for trade in self.trades:
                    if trade.entry_id == order_id:
                        trade.entry_price = order_status.avg_price
                        trade.quantity = order_status.executed_qty
                        break
                return

        t = Timer(2.0, lambda: self._check_order_status(order_id))
        t.start()

    def _open_position(
        self,
        signal_result: int,
        trade_size: float,
        stop_loss: float,
        take_profit: float,
    ):
        if self.client.platform == "binance_spot" and signal_result == -1:
            return

        order_side = "buy" if signal_result == 1 else "sell"
        position_side = "long" if signal_result == 1 else "short"

        self._add_log(
            f"{position_side.capitalize()} signal on {self.contract.symbol} {self.tf}"
        )

        order_status = self.client.place_order(
            self.contract, "MARKET", trade_size, order_side
        )

        if order_status is not None:
            self._add_log(
                f"{order_side.capitalize()} order placed on {self.exchange} | Status: {order_status.status}"
            )

            self.ongoing_position = True
            avg_fill_price = None

            if order_status.status == "filled":
                avg_fill_price = order_status.avg_price
            else:
                t = Timer(2.0, lambda: self._check_order_status(order_status.order_id))
                t.start()

            new_trade = Trade(
                {
                    "time": int(time.time() * 1000),
                    "entry_price": avg_fill_price,
                    "contract": self.contract,
                    "strategy": self.strat_name,
                    "side": position_side,
                    "status": "open",
                    "pnl": 0,
                    "quantity": order_status.executed_qty,
                    "entry_id": order_status.order_id,
                }
            )
            self.trades.append(new_trade)

    def _check_tp_sl(self, trade: Trade):
        pass  # To be implemented in the subclass

    def _check_signal(self) -> int:
        pass  # To be implemented in the subclass

    def check_trade(self, tick_type: str):
        if tick_type == "new_candle" and not self.ongoing_position:
            signal_result = self._check_signal()
            if signal_result in [-1, 1]:
                self._open_position(signal_result)


class DummyStrategy(Strategy):
    def __init__(
        self,
        client,
        contract: Contract,
        exchange: str,
        timeframe: str,
        other_params: Dict,
    ):
        super().__init__(client, contract, exchange, timeframe, "Dummy")
        self.balance_pct = other_params["balance_pct"]

    def get_trade_size(self, price: float) -> float:
        """
        Compute the trade size for the Dummy strategy.
        :param price: The current price of the asset
        :return: The computed trade size
        """
        balance = self.client.get_balances()
        if balance is not None:
            if self.contract.quote_asset in balance:
                balance = (
                    balance[self.contract.quote_asset].wallet_balance
                    if self.client.futures
                    else balance[self.contract.quote_asset].free
                )
            else:
                return None
        else:
            return None

        trade_size = (balance * self.balance_pct / 100) / price
        trade_size = round(
            round(trade_size / self.contract.lot_size) * self.contract.lot_size, 8
        )
        return trade_size

    def _check_signal(self) -> int:
        # Always return 1 to trigger a buy signal
        return 1

    def _open_position(self, signal_result: int):
        trade_size = self.get_trade_size(self.candles[-1].close)
        if trade_size is None:
            return
        stop_loss = 0  # No stop loss for dummy strategy
        take_profit = 0  # No take profit for dummy strategy
        super()._open_position(signal_result, trade_size, stop_loss, take_profit)

    def _check_tp_sl(self, trade: Trade):
        # No take profit or stop loss for dummy strategy
        pass


class FractalStrategy(Strategy):
    def __init__(
        self,
        client,
        contract: Contract,
        exchange: str,
        timeframe: str,
        other_params: Dict,
    ):
        super().__init__(client, contract, exchange, timeframe, "Fractals")
        self._ema_fast = other_params["ema_fast"]
        self._ema_slow = other_params["ema_slow"]
        self._ema_very_slow = other_params["ema_very_slow"]
        self._rsi_length = other_params["rsi_length"]
        self.risk_pct = other_params["risk_pct"]
        self.stop_list_long = []
        self.stop_list_short = []

    def _rsi(self) -> float:
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)
        delta = closes.diff().dropna()
        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0
        avg_gain = up.ewm(
            com=(self._rsi_length - 1), min_periods=self._rsi_length
        ).mean()
        avg_loss = (
            down.abs()
            .ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length)
            .mean()
        )
        rs = avg_gain / avg_loss
        rsi = 100 - 100 / (1 + rs)
        return rsi.round(2).iloc[-2]

    def get_trade_size(self, price: float, stop_loss: float) -> float:
        """
        Compute the trade size based on the stop loss level and the percentage of the balance to risk.
        :param price: The current price of the asset
        :param stop_loss: The stop loss price level
        :return: The computed trade size
        """
        balance = self.client.get_balances()
        if balance is not None:
            if self.contract.quote_asset in balance:
                balance = (
                    balance[self.contract.quote_asset].wallet_balance
                    if self.client.futures
                    else balance[self.contract.quote_asset].free
                )
            else:
                return None
        else:
            return None

        risk_amount = balance * self.risk_pct / 100
        trade_size = risk_amount / abs(price - stop_loss)
        trade_size = round(
            round(trade_size / self.contract.lot_size) * self.contract.lot_size, 8
        )
        return trade_size

    def _open_position(self, signal_result: int):
        stop_loss = (
            self.stop_list_long[-1] if signal_result == 1 else self.stop_list_short[-1]
        )
        trade_size = self.get_trade_size(self.candles[-1].close, stop_loss)
        if trade_size is None:
            return
        super()._open_position(signal_result, trade_size, stop_loss, None)

    def _check_tp_sl(self, trade: Trade):
        tp_triggered = False
        sl_triggered = False
        price = self.candles[-1].close
        if trade.side == "long":
            stop_loss_long = self.stop_list_long[-1]
            take_profit_long = (
                trade.entry_price - stop_loss_long
            ) * 1.7 + trade.entry_price
            if price <= stop_loss_long:
                sl_triggered = True
            if price >= take_profit_long:
                tp_triggered = True
        elif trade.side == "short":
            stop_loss_short = self.stop_list_short[-1]
            take_profit_short = (
                trade.entry_price - stop_loss_short
            ) * 1.7 + trade.entry_price
            if price >= stop_loss_short:
                sl_triggered = True
            if price <= take_profit_short:
                tp_triggered = True

        if tp_triggered or sl_triggered:
            self._add_log(
                f"{'Stop loss' if sl_triggered else 'Take profit'} for {self.contract.symbol} {self.tf} "
                f"| Current Price = {price} (Entry price was {trade.entry_price})"
            )
            order_side = "SELL" if trade.side == "long" else "BUY"
            if not self.client.futures:
                current_balances = self.client.get_balances()
                if current_balances is not None:
                    if (
                        order_side == "SELL"
                        and self.contract.base_asset in current_balances
                    ):
                        trade.quantity = min(
                            current_balances[self.contract.base_asset].free,
                            trade.quantity,
                        )
            order_status = self.client.place_order(
                self.contract, "MARKET", trade.quantity, order_side
            )
            if order_status is not None:
                self._add_log(
                    f"Exit order on {self.contract.symbol} {self.tf} placed successfully"
                )
                trade.status = "closed"
                self.ongoing_position = False

    def fractal_bearish(self) -> float:
        if (
            (self.candles[-2].high > self.candles[-4].high)
            and (self.candles[-2].high > self.candles[-3].high)
            and (self.candles[-2].high > self.candles[-1].high)
        ):
            return self.candles[-2].high * (1 + 0.0002)

    def fractal_bullish(self) -> float:
        if (
            (self.candles[-2].low < self.candles[-4].low)
            and (self.candles[-2].low < self.candles[-3].low)
            and (self.candles[-2].low < self.candles[-1].low)
        ):
            return self.candles[-2].low * (1 - 0.0002)

    def EmaFast(self) -> float:
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)
        return closes.ewm(span=self._ema_fast).mean().iloc[-2]

    def EmaSlow(self) -> float:
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)
        return closes.ewm(span=self._ema_slow).mean().iloc[-2]

    def EmaVerySlow(self) -> float:
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)
        return closes.ewm(span=self._ema_very_slow).mean().iloc[-2]

    def sell_signal(self) -> int:
        rsi = self._rsi()
        ema_fast = self.EmaFast()
        ema_slow = self.EmaSlow()
        ema_very_slow = self.EmaVerySlow()
        last_five_highs = self.candles[-2].high * (1 + 0.0002)
        if (
            rsi < 55
            and last_five_highs < ema_slow
            and last_five_highs > ema_fast
            and last_five_highs < ema_very_slow
        ):
            return -1

    def buy_signal(self) -> int:
        rsi = self._rsi()
        ema_fast = self.EmaFast()
        ema_slow = self.EmaSlow()
        ema_very_slow = self.EmaVerySlow()
        last_five_lows = self.candles[-2].low * (1 - 0.0002)
        if (
            rsi > 45
            and last_five_lows > ema_slow
            and last_five_lows < ema_fast
            and last_five_lows > ema_very_slow
        ):
            return 1

    def stop_list(self, stop_list_long: list, stop_list_short: list) -> float:
        if not self.ongoing_position:
            fractal_up = self.fractal_bullish()
            fractal_down = self.fractal_bearish()
            if fractal_up:
                stop_list_long.append(fractal_up)
                return stop_list_long[-1]
            if fractal_down:
                stop_list_short.append(fractal_down)
                return stop_list_short[-1]

    def _check_signal(self) -> int:
        if self.buy_signal() == 1:
            return 1
        if self.sell_signal() == -1:
            return -1
        return 0


class TechnicalStrategy(Strategy):
    def __init__(
        self,
        client,
        contract: Contract,
        exchange: str,
        timeframe: str,
        other_params: Dict,
    ):
        super().__init__(client, contract, exchange, timeframe, "Technical")
        self._ema_fast = other_params["ema_fast"]
        self._ema_slow = other_params["ema_slow"]
        self._ema_signal = other_params["ema_signal"]
        self._rsi_length = other_params["rsi_length"]
        self.stop_loss_pct = other_params.get("stop_loss_pct", 1.0)  # Default to 1%
        self.take_profit_pct = other_params.get("take_profit_pct", 2.0)  # Default to 2%
        self.balance_pct = other_params["balance_pct"]

    def get_trade_size(self, price: float) -> float:
        """
        Compute the trade size for the Technical strategy.
        :param price: The current price of the asset
        :return: The computed trade size
        """
        balance = self.client.get_balances()
        if balance is not None:
            if self.contract.quote_asset in balance:
                balance = (
                    balance[self.contract.quote_asset].wallet_balance
                    if self.client.futures
                    else balance[self.contract.quote_asset].free
                )
            else:
                return None
        else:
            return None

        trade_size = (balance * self.balance_pct / 100) / price
        trade_size = round(
            round(trade_size / self.contract.lot_size) * self.contract.lot_size, 8
        )
        return trade_size

    def _rsi(self) -> float:
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)
        delta = closes.diff().dropna()
        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0
        avg_gain = up.ewm(
            com=(self._rsi_length - 1), min_periods=self._rsi_length
        ).mean()
        avg_loss = (
            down.abs()
            .ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length)
            .mean()
        )
        rs = avg_gain / avg_loss
        rsi = 100 - 100 / (1 + rs)
        return rsi.round(2).iloc[-2]

    def _macd(self) -> Tuple[float, float]:
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)
        ema_fast = closes.ewm(span=self._ema_fast).mean()
        ema_slow = closes.ewm(span=self._ema_slow).mean()
        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=self._ema_signal).mean()
        return macd_line.iloc[-2], macd_signal.iloc[-2]

    def _check_signal(self):
        macd_line, macd_signal = self._macd()
        rsi = self._rsi()
        if rsi < 30 and macd_line > macd_signal:
            return 1
        elif rsi > 70 and macd_line < macd_signal:
            return -1
        return 0

    def _open_position(self, signal_result: int):
        trade_size = self.client.get_trade_size(
            self.contract, self.candles[-1].close, self.balance_pct
        )
        if trade_size is None:
            return
        stop_loss = (
            self.candles[-1].close * (1 - self.stop_loss_pct / 100)
            if signal_result == 1
            else self.candles[-1].close * (1 + self.stop_loss_pct / 100)
        )
        take_profit = (
            self.candles[-1].close * (1 + self.take_profit_pct / 100)
            if signal_result == 1
            else self.candles[-1].close * (1 - self.take_profit_pct / 100)
        )
        super()._open_position(signal_result, trade_size, stop_loss, take_profit)

    def _check_tp_sl(self, trade: Trade):
        price = self.candles[-1].close
        if trade.side == "long":
            if price <= trade.entry_price * (1 - self.stop_loss_pct / 100):
                self._add_log(
                    f"Stop loss triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)
            elif price >= trade.entry_price * (1 + self.take_profit_pct / 100):
                self._add_log(
                    f"Take profit triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)
        elif trade.side == "short":
            if price >= trade.entry_price * (1 + self.stop_loss_pct / 100):
                self._add_log(
                    f"Stop loss triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)
            elif price <= trade.entry_price * (1 - self.take_profit_pct / 100):
                self._add_log(
                    f"Take profit triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)

    def _close_position(self, trade: Trade):
        order_side = "SELL" if trade.side == "long" else "BUY"
        if not self.client.futures:
            current_balances = self.client.get_balances()
            if current_balances is not None:
                if (
                    order_side == "SELL"
                    and self.contract.base_asset in current_balances
                ):
                    trade.quantity = min(
                        current_balances[self.contract.base_asset].free, trade.quantity
                    )
        order_status = self.client.place_order(
            self.contract, "MARKET", trade.quantity, order_side
        )
        if order_status is not None:
            self._add_log(
                f"Exit order on {self.contract.symbol} {self.tf} placed successfully"
            )
            trade.status = "closed"
            self.ongoing_position = False


class BreakoutStrategy(Strategy):
    def __init__(
        self,
        client,
        contract: Contract,
        exchange: str,
        timeframe: str,
        other_params: Dict,
    ):
        super().__init__(client, contract, exchange, timeframe, "Breakout")
        self._min_volume = other_params["min_volume"]
        self.stop_loss_pct = other_params.get("stop_loss_pct", 1.0)  # Default to 1%
        self.take_profit_pct = other_params.get("take_profit_pct", 2.0)  # Default to 2%
        self.balance_pct = other_params["balance_pct"]

    def get_trade_size(self, price: float) -> float:
        """
        Compute the trade size for the Breakout strategy.
        :param price: The current price of the asset
        :return: The computed trade size
        """
        balance = self.client.get_balances()
        if balance is not None:
            if self.contract.quote_asset in balance:
                balance = (
                    balance[self.contract.quote_asset].wallet_balance
                    if self.client.futures
                    else balance[self.contract.quote_asset].free
                )
            else:
                return None
        else:
            return None

        trade_size = (balance * self.balance_pct / 100) / price
        trade_size = round(
            round(trade_size / self.contract.lot_size) * self.contract.lot_size, 8
        )
        return trade_size

    def _check_signal(self) -> int:
        if (
            self.candles[-1].close > self.candles[-2].high
            and self.candles[-1].volume > self._min_volume
        ):
            self._add_log(f"Valid long signal on {self.contract.symbol} {self.tf}")
            return 1
        elif (
            self.candles[-1].close < self.candles[-2].low
            and self.candles[-1].volume > self._min_volume
        ):
            self._add_log(f"Valid short signal on {self.contract.symbol} {self.tf}")
            return -1
        return 0

    def _open_position(self, signal_result: int):
        trade_size = self.client.get_trade_size(
            self.contract, self.candles[-1].close, self.balance_pct
        )
        if trade_size is None:
            return
        stop_loss = (
            self.candles[-1].close * (1 - self.stop_loss_pct / 100)
            if signal_result == 1
            else self.candles[-1].close * (1 + self.stop_loss_pct / 100)
        )
        take_profit = (
            self.candles[-1].close * (1 + self.take_profit_pct / 100)
            if signal_result == 1
            else self.candles[-1].close * (1 - self.take_profit_pct / 100)
        )
        super()._open_position(signal_result, trade_size, stop_loss, take_profit)

    def _check_tp_sl(self, trade: Trade):
        price = self.candles[-1].close
        if trade.side == "long":
            if price <= trade.entry_price * (1 - self.stop_loss_pct / 100):
                self._add_log(
                    f"Stop loss triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)
            elif price >= trade.entry_price * (1 + self.take_profit_pct / 100):
                self._add_log(
                    f"Take profit triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)
        elif trade.side == "short":
            if price >= trade.entry_price * (1 + self.stop_loss_pct / 100):
                self._add_log(
                    f"Stop loss triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)
            elif price <= trade.entry_price * (1 - self.take_profit_pct / 100):
                self._add_log(
                    f"Take profit triggered for {self.contract.symbol} {self.tf}"
                )
                self._close_position(trade)

    def _close_position(self, trade: Trade):
        order_side = "SELL" if trade.side == "long" else "BUY"
        if not self.client.futures:
            current_balances = self.client.get_balances()
            if current_balances is not None:
                if (
                    order_side == "SELL"
                    and self.contract.base_asset in current_balances
                ):
                    trade.quantity = min(
                        current_balances[self.contract.base_asset].free, trade.quantity
                    )
        order_status = self.client.place_order(
            self.contract, "MARKET", trade.quantity, order_side
        )
        if order_status is not None:
            self._add_log(
                f"Exit order on {self.contract.symbol} {self.tf} placed successfully"
            )
            trade.status = "closed"
            self.ongoing_position = False
