from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import math
import backtrader as bt


class PercentSizer100(bt.Sizer):
    """Sizer that uses a percentage of available cash to buy and rounds the
    resulting share count up to the nearest multiple of `rounding` (default 100).

    Params:
      - percents: percent of cash to use for each buy (e.g. 10 means 10%)
      - rounding: round share count to nearest multiple (e.g. 100)
    """
    params = (
        ('percents', 10),
        ('rounding', 100),
    )

    def _getsizing(self, comminfo, cash, data, isbuy):
        # Only handle buys here; sells are done explicitly by the strategy
        if not isbuy:
            return 0

        try:
            price = float(data.close[0])
        except Exception:
            return 0

        if price <= 0.0:
            return 0

        # money we intend to spend (10% of available cash by default)
        money = cash * (self.p.percents / 100.0)

        # raw number of shares afforded by that money
        raw_shares = money / price
        if raw_shares < 1:
            return 0

        rounding = max(1, int(self.p.rounding))

        # round up to nearest multiple of rounding
        size = int(math.ceil(raw_shares / rounding) * rounding)

        # Ensure we don't try to buy more than available cash allows
        max_affordable = comminfo.getsize(price, cash)
        if max_affordable <= 0:
            return 0

        if size > max_affordable:
            # reduce to the largest multiple of rounding we can afford
            size = int((max_affordable // rounding) * rounding)
            if size <= 0:
                return 0

        return int(size)
