"""Walk-forward backtest harness for the AlphaFeed XGBoost mispricing model.

Public modules:
  walk_forward — expanding-window fold splitter (pure)
  sim          — Kelly + bet sim + portfolio simulation (pure)
  metrics      — Sharpe, max drawdown, win rate (pure)
  run_backtest — orchestrator that trains real XGBoost per fold and
                 writes report.md + charts/*.png
"""
