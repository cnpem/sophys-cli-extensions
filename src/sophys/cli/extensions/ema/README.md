# EMA extension for sophys-cli

### Assumptions

We assume that there's a `ema_sophys_cli_config.csv` file in the user's working directory, configured with detectors to use, and metadata to acquire.

The format for this file is as follows:

|type|name|
|----|----|
|detector|abc|
|before|def|
|during|ghi|
|after|jkl|
|detector|mno|
|during|pqr|
|during|stu|
|detector|vwx|

We assume the RunEngine / server can deal with `READ_BEFORE`, `READ_DURING`, and `READ_AFTER` metadata entries properly.

These entries are in the format `detector,detector,detector,...`.
