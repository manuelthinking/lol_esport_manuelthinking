USE lol_esports;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_lol_pit_backtest_date_league'
      AND object_id = OBJECT_ID('dbo.lol_bayes_lane_power_backtest_pit_snapshot')
)
BEGIN
    CREATE INDEX IX_lol_pit_backtest_date_league
    ON dbo.lol_bayes_lane_power_backtest_pit_snapshot (
        game_date,
        league
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_lol_pit_backtest_alignment'
      AND object_id = OBJECT_ID('dbo.lol_bayes_lane_power_backtest_pit_snapshot')
)
BEGIN
    CREATE INDEX IX_lol_pit_backtest_alignment
    ON dbo.lol_bayes_lane_power_backtest_pit_snapshot (
        bayes_lane_alignment_label
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_lol_pit_backtest_flags'
      AND object_id = OBJECT_ID('dbo.lol_bayes_lane_power_backtest_pit_snapshot')
)
BEGIN
    CREATE INDEX IX_lol_pit_backtest_flags
    ON dbo.lol_bayes_lane_power_backtest_pit_snapshot (
        bayes_overconfidence_warning_flag,
        bayes_possible_upset_signal_flag,
        lane_power_breaks_bayes_tie_flag
    );
END;
GO