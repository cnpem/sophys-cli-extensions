# EMA extension for sophys-cli

### Assumptions

##### If using **LocalDataSource**:

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

##### If using **RedisDataSource**:

We assume that there's a Redis instance running remotely, with no authentication or protection, with the following keys as sets of strings:

- `sophys_detectors`
- `sophys_metadata_read_before`
- `sophys_metadata_read_during`
- `sophys_metadata_read_after`

##### General assumptions

We assume the RunEngine / server can deal with `READ_BEFORE`, `READ_DURING`, and `READ_AFTER` metadata entries properly.

These entries are in the format `detector,detector,detector,...`.
