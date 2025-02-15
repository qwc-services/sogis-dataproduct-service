SO!GIS Dataproduct service
==========================

**Note:** The schema for sublayer visibilities has changed in `v2.0.5` of `dataproductConfig.json`. Prior service configs must be recreated.


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


Usage/Development
-----------------

Start service:

    python src/server.py

base URL:

    http://localhost:5023/

API:

    http://localhost:5023/api/

Examples:

    curl -s http://localhost:5023/ch.so.afu.fliessgewaesser.netz

    curl -s 'http://localhost:5023/weblayers?filter=afu_altlasten_pub,ch.so.afu.fliessgewaesser.netz'


Development
-----------

Install dependencies and run service:

    uv run src/server.py

With config path:

    CONFIG_PATH=/PATH/TO/CONFIGS/ uv run src/server.py

Testing
-------

Run all tests:

    python test.py
