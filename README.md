SO!GIS Dataproduct service
==========================


Configuration
-------------

Environment variables:

| Variable                    | Description                                       | Default value                |
|-----------------------------|---------------------------------------------------|------------------------------|
| `DEFAULT_EXTENT`            | Default extent                                    | `2590983.47500000009313226, 1212806.11562500009313226, 2646267.02499999990686774, 1262755.00937499990686774` |
| `DEFAULT_SEARCH_WMS_NAME`   | Default WMS name                                  | `somap`                      |
| `WMS_SERVICE_URL`           | WMS service URL override                          | `<empty>`                    |
| `RASTER_DATASOURCE_PATTERN` | Regex pattern for modifying raster data sources   | `<empty>`                    |
| `RASTER_DATASOURCE_REPL`    | Substitution for modifying raster data sources    | `<empty>`                    |
| `QGS_RESOURCES_DIR`         | Path to QGIS resources for embedding QML symbols  | `<empty>`                    |

The connection dir for raster data sources returned in `raster_datasource` is modified by `re.sub(RASTER_DATASOURCE_PATTERN, RASTER_DATASOURCE_REPL, data_source.connection)`.

Run locally
-----------

Install dependencies and run:

    export CONFIG_PATH=<CONFIG_PATH>
    uv run src/server.py

To use configs from a `qwc-docker` setup, set `CONFIG_PATH=<...>/qwc-docker/volumes/config`.

Set `FLASK_DEBUG=1` for additional debug output.

Set `FLASK_RUN_PORT=<port>` to change the default port (default: `5000`).

API documentation:

    http://localhost:5000/api/

Examples:

    http://localhost:5000/ch.so.afu.fliessgewaesser.netz

    http://localhost:5000/weblayers?filter=afu_altlasten_pub,ch.so.afu.fliessgewaesser.netz

Docker usage
------------

The Docker image is published on [Dockerhub](https://hub.docker.com/r/sourcepole/sogis-dataproduct-service).

See sample [docker-compose.yml](https://github.com/qwc-services/qwc-docker/blob/master/docker-compose-example.yml) of [qwc-docker](https://github.com/qwc-services/qwc-docker).
