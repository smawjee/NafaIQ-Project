"""PSX market-data service package.

This package groups all PSX DPS / TradingView / AhleTrade client code
under one namespace so that user-portfolio code never imports
market-data fetchers directly.

Modules:
- dps: PSX DPS portal client (market-watch, symbols, historical, company,
  payouts, announcements, KSE100 EOD)
- tradingview: TradingView Pakistan scanner
- prices: unified latest-price + previous-close resolver
- sector_map: symbol->sector lookup
- benchmark: KSE-100 EOD wrapper
"""
