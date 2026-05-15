/* ============================================================
   LoL Manual Starters History Table

   Purpose:
     Preserve the manual starters used for each slate.

   Daily workflow stays the same:
     data/manual_starters.csv

   This table stores a historical snapshot by:
     slate_date + slate_name + teamname + position + playername

   Grain:
     one row per slate / team / position / player
   ============================================================ */

IF OBJECT_ID('dbo.lol_manual_starters_history', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.lol_manual_starters_history
    (
        starter_history_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,

        slate_date DATE NOT NULL,
        slate_name VARCHAR(100) NOT NULL,

        teamname VARCHAR(100) NOT NULL,
        position VARCHAR(20) NOT NULL,
        playername VARCHAR(150) NOT NULL,

        is_starter BIT NOT NULL DEFAULT 1,

        source_file VARCHAR(300) NULL,
        source_type VARCHAR(50) NOT NULL DEFAULT 'manual_csv',

        loaded_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NULL
    );
END;
GO


/* ============================================================
   Add unique key so the same starter is not duplicated
   if we rerun the save script for the same slate.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ux_lol_manual_starters_history_slate_player'
      AND object_id = OBJECT_ID('dbo.lol_manual_starters_history')
)
BEGIN
    CREATE UNIQUE INDEX ux_lol_manual_starters_history_slate_player
    ON dbo.lol_manual_starters_history
    (
        slate_date,
        slate_name,
        teamname,
        position,
        playername
    );
END;
GO


/* ============================================================
   Helpful lookup index for loading starters by slate.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ix_lol_manual_starters_history_slate'
      AND object_id = OBJECT_ID('dbo.lol_manual_starters_history')
)
BEGIN
    CREATE INDEX ix_lol_manual_starters_history_slate
    ON dbo.lol_manual_starters_history
    (
        slate_date,
        slate_name,
        teamname,
        position
    );
END;
GO