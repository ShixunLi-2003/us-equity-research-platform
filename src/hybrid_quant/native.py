from __future__ import annotations

import ctypes
import sys
from pathlib import Path


class OrderRejected(RuntimeError):
    CODES = {
        1: "invalid order",
        2: "insufficient cash",
        3: "insufficient position",
        4: "native execution error",
        5: "symbol halted",
    }

    def __init__(self, code):
        self.code = int(code)
        super().__init__(self.CODES.get(self.code, "unknown rejection"))


class ExecutionCore:
    def __init__(self, library_path=None):
        extension = '.dll' if sys.platform == 'win32' else '.dylib' if sys.platform == 'darwin' else '.so'
        path = Path(library_path) if library_path else Path(__file__).with_name("_native") / ('hybrid_quant_core' + extension)
        if not path.exists():
            raise RuntimeError("native core not built: run python scripts/build_native.py")
        self.lib = ctypes.CDLL(str(path))
        self.lib.hq_version.restype = ctypes.c_char_p
        self.lib.hq_order_quantity.argtypes = [ctypes.c_double, ctypes.c_double,
                                                ctypes.c_longlong, ctypes.c_double]
        self.lib.hq_order_quantity.restype = ctypes.c_longlong
        self.lib.hq_round_trip_pnl.argtypes = [ctypes.c_double, ctypes.c_double,
                                               ctypes.c_longlong, ctypes.c_double,
                                               ctypes.c_double, ctypes.c_double,
                                               ctypes.c_double]
        self.lib.hq_round_trip_pnl.restype = ctypes.c_double
        self.lib.hq_pretrade_check.argtypes = [ctypes.c_double, ctypes.c_double,
                                               ctypes.c_longlong, ctypes.c_double,
                                               ctypes.c_double, ctypes.c_double,
                                               ctypes.c_double]
        self.lib.hq_pretrade_check.restype = ctypes.c_int
        self.lib.hq_slipped_price.argtypes = [ctypes.c_double, ctypes.c_int,
                                              ctypes.c_double]
        self.lib.hq_slipped_price.restype = ctypes.c_double
        self.lib.hq_transaction_cost.argtypes = [ctypes.c_double, ctypes.c_int,
                                                  ctypes.c_double, ctypes.c_double,
                                                  ctypes.c_double]
        self.lib.hq_transaction_cost.restype = ctypes.c_double
        self.lib.hq_max_drawdown.argtypes = [ctypes.POINTER(ctypes.c_double),
                                             ctypes.c_size_t]
        self.lib.hq_max_drawdown.restype = ctypes.c_double
        self.lib.hq_account_create.argtypes = [
            ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.c_double, ctypes.c_double]
        self.lib.hq_account_create.restype = ctypes.c_void_p
        self.lib.hq_account_destroy.argtypes = [ctypes.c_void_p]
        self.lib.hq_account_destroy.restype = None
        self.lib.hq_account_execute.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_longlong,
            ctypes.c_double, ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        self.lib.hq_account_execute.restype = ctypes.c_int
        self.lib.hq_account_mark.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                             ctypes.c_double]
        self.lib.hq_account_mark.restype = ctypes.c_int
        self.lib.hq_account_cash.argtypes = [ctypes.c_void_p]
        self.lib.hq_account_cash.restype = ctypes.c_double
        self.lib.hq_account_quantity.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.hq_account_quantity.restype = ctypes.c_longlong
        self.lib.hq_account_average_cost.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.hq_account_average_cost.restype = ctypes.c_double
        for name in ("hq_account_realized_pnl", "hq_account_total_fees",
                     "hq_account_equity", "hq_account_gross_exposure"):
            function = getattr(self.lib, name)
            function.argtypes = [ctypes.c_void_p]
            function.restype = ctypes.c_double
        self.lib.hq_account_set_tradable.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.hq_account_set_tradable.restype = ctypes.c_int
        self.lib.hq_account_submit_limit.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.c_longlong, ctypes.c_double]
        self.lib.hq_account_submit_limit.restype = ctypes.c_longlong
        self.lib.hq_account_cancel.argtypes = [
            ctypes.c_void_p, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong)]
        self.lib.hq_account_cancel.restype = ctypes.c_int
        self.lib.hq_account_order_remaining.argtypes = [
            ctypes.c_void_p, ctypes.c_longlong]
        self.lib.hq_account_order_remaining.restype = ctypes.c_longlong
        self.lib.hq_account_process_bar.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double, ctypes.c_double,
            ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        self.lib.hq_account_process_bar.restype = ctypes.c_int
        self.lib.hq_account_last_fill_count.argtypes = [ctypes.c_void_p]
        self.lib.hq_account_last_fill_count.restype = ctypes.c_size_t
        self.lib.hq_account_last_fill.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_longlong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_longlong),
            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double)]
        self.lib.hq_account_last_fill.restype = ctypes.c_int
        self.lib.hq_account_apply_split.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double)]
        self.lib.hq_account_apply_split.restype = ctypes.c_int
        self.lib.hq_account_apply_dividend.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double)]
        self.lib.hq_account_apply_dividend.restype = ctypes.c_int
        self.lib.hq_account_credit_income.argtypes = [ctypes.c_void_p, ctypes.c_double]
        self.lib.hq_account_credit_income.restype = ctypes.c_int
        self.lib.hq_account_credit_shares.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_longlong, ctypes.c_double]
        self.lib.hq_account_credit_shares.restype = ctypes.c_int

    @property
    def version(self):
        return self.lib.hq_version().decode("ascii")

    def order_quantity(self, cash, price, lot_size=1, max_cash_fraction=1.0):
        return int(self.lib.hq_order_quantity(cash, price, lot_size, max_cash_fraction))

    def round_trip_pnl(self, entry, exit_price, quantity, commission_bps=1.0,
                       minimum_commission=0.0, sell_tax_bps=0.0, slippage_bps=2.0):
        return float(self.lib.hq_round_trip_pnl(
            entry, exit_price, quantity, commission_bps, minimum_commission,
            sell_tax_bps, slippage_bps))

    def pretrade_check(self, cash, price, quantity, current_gross, nav,
                       max_order_notional, max_gross_leverage=1.0):
        return int(self.lib.hq_pretrade_check(
            cash, price, quantity, current_gross, nav,
            max_order_notional, max_gross_leverage))

    def slipped_price(self, price, side, slippage_bps=2.0):
        return float(self.lib.hq_slipped_price(price, side, slippage_bps))

    def transaction_cost(self, notional, side, commission_bps=1.0,
                         minimum_commission=0.0, sell_tax_bps=0.0):
        return float(self.lib.hq_transaction_cost(
            notional, side, commission_bps, minimum_commission, sell_tax_bps))

    def max_drawdown(self, nav):
        values = [float(value) for value in nav]
        if not values:
            return 0.0
        array = (ctypes.c_double * len(values))(*values)
        return float(self.lib.hq_max_drawdown(array, len(values)))

    def account(self, initial_cash, commission_bps=1.0, minimum_commission=0.0,
                sell_tax_bps=0.0, slippage_bps=2.0):
        return TradingAccount(self, initial_cash, commission_bps,
                              minimum_commission, sell_tax_bps, slippage_bps)


class TradingAccount:
    def __init__(self, core, initial_cash, commission_bps=1.0,
                 minimum_commission=0.0, sell_tax_bps=0.0, slippage_bps=2.0):
        self.core = core
        self._handle = self.core.lib.hq_account_create(
            initial_cash, commission_bps, minimum_commission,
            sell_tax_bps, slippage_bps)
        if not self._handle:
            raise ValueError("invalid account configuration")

    def close(self):
        if self._handle:
            self.core.lib.hq_account_destroy(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def __del__(self):
        self.close()

    @staticmethod
    def _symbol(symbol):
        return str(symbol).upper().encode("ascii")

    def execute(self, symbol, side, quantity, reference_price):
        fill = ctypes.c_double()
        fee = ctypes.c_double()
        realized = ctypes.c_double()
        code = self.core.lib.hq_account_execute(
            self._handle, self._symbol(symbol), int(side), int(quantity),
            float(reference_price), ctypes.byref(fill), ctypes.byref(fee),
            ctypes.byref(realized))
        if code:
            raise OrderRejected(code)
        return {"symbol": str(symbol).upper(), "side": int(side),
                "quantity": int(quantity), "fill_price": float(fill.value),
                "fee": float(fee.value), "realized_pnl": float(realized.value)}

    def mark(self, symbol, price):
        code = self.core.lib.hq_account_mark(
            self._handle, self._symbol(symbol), float(price))
        if code:
            raise OrderRejected(code)

    def set_tradable(self, symbol, tradable=True):
        code = self.core.lib.hq_account_set_tradable(
            self._handle, self._symbol(symbol), int(bool(tradable)))
        if code:
            raise OrderRejected(code)

    def submit_limit(self, symbol, side, quantity, limit_price):
        order_id = int(self.core.lib.hq_account_submit_limit(
            self._handle, self._symbol(symbol), int(side), int(quantity),
            float(limit_price)))
        if order_id < 0:
            raise OrderRejected(-order_id)
        return order_id

    def cancel(self, order_id):
        cancelled = ctypes.c_longlong()
        code = self.core.lib.hq_account_cancel(
            self._handle, int(order_id), ctypes.byref(cancelled))
        if code:
            raise OrderRejected(code)
        return int(cancelled.value)

    def order_remaining(self, order_id):
        value = int(self.core.lib.hq_account_order_remaining(
            self._handle, int(order_id)))
        if value < 0:
            raise OrderRejected(1)
        return value

    def process_bar(self, symbol, open_price, high, low, close, volume,
                    max_participation=0.05):
        code = self.core.lib.hq_account_process_bar(
            self._handle, self._symbol(symbol), float(open_price), float(high),
            float(low), float(close), float(volume), float(max_participation))
        if code:
            raise OrderRejected(code)
        fills = []
        count = int(self.core.lib.hq_account_last_fill_count(self._handle))
        for index in range(count):
            order_id = ctypes.c_longlong()
            side = ctypes.c_int()
            quantity = ctypes.c_longlong()
            fill = ctypes.c_double()
            fee = ctypes.c_double()
            realized = ctypes.c_double()
            code = self.core.lib.hq_account_last_fill(
                self._handle, index, ctypes.byref(order_id), ctypes.byref(side),
                ctypes.byref(quantity), ctypes.byref(fill), ctypes.byref(fee),
                ctypes.byref(realized))
            if code:
                raise OrderRejected(code)
            fills.append({"order_id": int(order_id.value), "symbol": str(symbol).upper(),
                          "side": int(side.value), "quantity": int(quantity.value),
                          "fill_price": float(fill.value), "fee": float(fee.value),
                          "realized_pnl": float(realized.value)})
        return fills

    def apply_split(self, symbol, ratio, cash_in_lieu_price=0.0):
        credit = ctypes.c_double()
        code = self.core.lib.hq_account_apply_split(
            self._handle, self._symbol(symbol), float(ratio),
            float(cash_in_lieu_price), ctypes.byref(credit))
        if code:
            raise OrderRejected(code)
        return float(credit.value)

    def credit_income(self, amount):
        code = self.core.lib.hq_account_credit_income(self._handle, float(amount))
        if code:
            raise OrderRejected(code)

    def credit_shares(self, symbol, quantity, reference_price):
        code = self.core.lib.hq_account_credit_shares(self._handle, symbol.encode('utf-8'), int(quantity), float(reference_price))
        if code:
            raise OrderRejected(code)

    def apply_dividend(self, symbol, amount_per_share, withholding_bps=0.0):
        credit = ctypes.c_double()
        code = self.core.lib.hq_account_apply_dividend(
            self._handle, self._symbol(symbol), float(amount_per_share),
            float(withholding_bps), ctypes.byref(credit))
        if code:
            raise OrderRejected(code)
        return float(credit.value)

    def quantity(self, symbol):
        return int(self.core.lib.hq_account_quantity(
            self._handle, self._symbol(symbol)))

    def average_cost(self, symbol):
        return float(self.core.lib.hq_account_average_cost(
            self._handle, self._symbol(symbol)))

    @property
    def cash(self):
        return float(self.core.lib.hq_account_cash(self._handle))

    @property
    def equity(self):
        return float(self.core.lib.hq_account_equity(self._handle))

    @property
    def gross_exposure(self):
        return float(self.core.lib.hq_account_gross_exposure(self._handle))

    @property
    def realized_pnl(self):
        return float(self.core.lib.hq_account_realized_pnl(self._handle))

    @property
    def total_fees(self):
        return float(self.core.lib.hq_account_total_fees(self._handle))
