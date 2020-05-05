import os
import sys

from flask import Flask, request, jsonify
from flask_restplus import Resource, fields, reqparse

from qwc_services_core.api import Api
from qwc_services_core.api import CaseInsensitiveArgument
from qwc_services_core.app import app_nocache
from qwc_services_core.auth import auth_manager, optional_auth, get_auth_user
from qwc_services_core.tenant_handler import TenantHandler
from qwc_services_core.permissions_reader import PermissionsReader
from qwc_services_core.runtime_config import RuntimeConfig
from dataproduct_service import DataproductService
from weblayers_service import WeblayersService


# Flask application
app = Flask(__name__)
app_nocache(app)

api = Api(app, version='1.0', title='Dataproduct service API',
          description="""API for SO!MAP dataproduct service.



**Structure of weblayers query response:**

    {
      "results": [
        {
          "title": "<title>",                                 /* Display text */
          "id": "<dataproduct_id>",                           /* Identifier */
          "layer": {                                          /* Layer definition */
            "name": "<wms_layer_name>",                       /* WMS name of the root layer */
            "sublayers": [                                    /* List of WMS sublayers */
              {
                "name": "<wms_layer_name>",                   /* WMS name of sublayer */
                "title": "<title>",                           /* Display name of layer */
                "bbox": {                                     /* Layer bounding box */
                  "crs": "EPSG:<srid>",
                  "bounds": [<xmin>, <ymin>, <xmax>, <ymax>]
                },
                "abstract": "<abstract_text>",                /* Layer description (optional) */
                "displayField": "<field_name>",               /* Field name to use as feature title in identify results */
                "opacity": <opacity>,                         /* Default layer opacity, 0-255 */
                "visibility": <bool>,                         /* Default layer visibility */
                "queryable": <bool>,                          /* Whether the layer is identifyable */
                "searchterms": ["<dataproduct_id>",...]       /* List of searchable DataProduct identifiers */
              }
            ]
          }
        },
        {
          "title": "<title>",
          "id": "<dataproduct_id>",
          "layer": {
            "name": "<wms_layer_name>",
            "sublayers": [
              {
                "name": "<wms_group_name>",                   /* WMS group of sublayer */
                "title": "<title>",                           /* Display name of group */
                "sublayers": [
                  {...}                                       /* List children groups or layers
                ]
              }
            ]
          }
        }
      ]
    }

Notes:
 * A single-layer result will have one sublayer in the `sublayers` list of the root layer
 * A group-layer result will have have a group in the `sublayers` list of the root layer, and the contained sublayers inside the `sublayers` list of the group
 * A facade-layer will appear as a single-layer

          """,
          default_label='Dataproduct operations', doc='/api/'
          )
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
# disable verbose 404 error message
app.config['ERROR_404_HELP'] = False

auth = auth_manager(app, api)

tenant_handler = TenantHandler(app.logger)

# create dataproduct service
dataproduct_service = DataproductService(app.logger)
weblayers_service = WeblayersService(app.logger)


person = api.create_model('Person', [
    ['id', fields.Integer(required=True, description='Person ID',
                          example=123)],
    ['name', fields.String(required=True, description='Name')],
    ['street', fields.String(required=False, description='Street name')],
    ['house_no', fields.String(required=False, description='House number')],
    ['zip', fields.String(required=False, description='ZIP number')],
    ['city', fields.String(required=False, description='City')],
    ['country_code', fields.String(required=False, description='Country code ISO 3')],
    ['function', fields.String(required=True, description='Function')],
    ['email', fields.String(required=False, description='EMail')],
    ['phone', fields.String(required=False, description='Phone number')]
])

organisation = api.create_model('Organisation', [
    ['id', fields.Integer(required=True, description='Organization ID',
                          example=123)],
    ['name', fields.String(required=True, description='Name')],
    ['street', fields.String(required=False, description='Street name')],
    ['house_no', fields.String(required=False, description='House number')],
    ['zip', fields.String(required=False, description='ZIP number')],
    ['city', fields.String(required=False, description='City')],
    ['country_code', fields.String(required=False, description='Country code ISO 3')],
    ['unit', fields.String(required=False, description='Unit')],
    ['abbreviation', fields.String(required=False, description='Abbreviation')]
])

contact = api.create_model('Contact', [
    ['person', fields.Nested(person, required=False, description='Person')],
    ['organisation', fields.Nested(organisation, required=True, description='Organisation')]
])

postgis_datasource = api.create_model('Postgis_datasource', [
    ['dbconnection', fields.String(required=True, description='e.g. service=sogis_webmapping')],
    ['geometry_type', fields.String(required=True, description=' e.g. MULTIPOLYGON')],
    ['srid', fields.Integer(required=True, description='<srid>')],
    ['data_set_name', fields.String(required=True, description='Fully qualified DB table name')],
    ['geometry_field', fields.String(required=True, description='Fieldname')],
    ['primary_key', fields.String(required=True, description='Fieldname')]
])

raster_datasource = api.create_model('Raster_datasource', [
    ['datasource', fields.String(required=True, description='File path')],
    ['srid', fields.Integer(required=True, description='<srid>')]
])

wms_datasource = api.create_model('Wms_datasource', [
    ['service_url', fields.String(required=True, description='Base URL of server')],
    ['name', fields.String(required=True, description='WMS name of layer')]
])


dataproduct_info_result = api.create_model('DataproductInfoResult', [
    ['identifier', fields.String(required=True, description='Dataproduct ID')],
    ['display', fields.String(required=True, description='Display name')],
    ['type', fields.String(required=True, description='Type of dataprodct: "datasetview", "layergroup", "facadelayer"')],
    ['synonyms', fields.List(fields.String, required=True,
                             description='Die Synonyme zum Namen als Suchbegriffe (0-n)')],
    ['keywords', fields.List(fields.String, required=True,
                             description='Die Stichworte zum Datenprodukt als Suchbegriffe (0-n)')],
    ['description', fields.String(required=True, description='Die Beschreibung des Dataproducts')],
    ['searchterms', fields.List(fields.String, required=False,
                                description='Searchable Dataproducts (0-n)')],
    ['contacts', fields.List(fields.Nested(contact), required=True,
                             description='Die 1-n zuständigen Körperschaften des Dataproducts')],
    ['bbox', fields.List(fields.Float, required=False,
                         description='Layer bounding box',
                         example=[2605354.75, 1227225.125,
                                  2608612.25, 1229926.625])],
    ['crs', fields.String(required=False,
                          description='Coordinate reference system',
                          example='EPSG:2056')],
    ['datatype', fields.String(required=False, description='"vector": Vectorlayer, "raster": Rasterlayer, "table": Table without geometry')],
    ['postgis_datasource', fields.List(fields.Nested(postgis_datasource), required=False,
                             description='')],
    ['raster_datasource', fields.List(fields.Nested(raster_datasource), required=False,
                             description='')],
    ['wms_datasource', fields.List(fields.Nested(wms_datasource), required=False,
                             description='')],
    ['qml', fields.String(required=False, description='QGIS Style XML (escaped)')],
    ['sublayers', fields.List(
        fields.Raw, required=False,
        description='Recursive list of sublayer dataproduct info'
    )]
])


class TenantConfigHandler:
    def __init__(self, tenant, logger):
        self.logger = logger
        self.tenant = tenant

        config_handler = RuntimeConfig("dataproduct", logger)
        config = config_handler.tenant_config(tenant)

        dataproducts = config.resources().get('dataproducts', [])
        self.all_resources = dataproducts
        self.weblayers = {
            entry.get("identifier"): entry for entry in dataproducts if entry.get("datatype") != 'table'
        }
        self.permissions_handler = PermissionsReader(tenant, logger)

    def resources(self, dataproduct_id):
        """Matching dataproducts.

        :param str dataproduct_id: Dataproduct ID
        """
        entries = list(filter(
            lambda entry: entry.get("identifier") == dataproduct_id,
            self.all_resources))
        return entries


def handler():
    tenant = tenant_handler.tenant()
    handler = tenant_handler.handler('dataproduct', 'handler', tenant)
    if handler is None:
        handler = tenant_handler.register_handler(
            'handler', tenant, TenantConfigHandler(tenant, app.logger))
    return handler


@api.route('/', endpoint='root')
class Dataproducts(Resource):
    @api.doc('dataproducts')
    @optional_auth
    def get(self):
        return None


@api.route('/<string:dataproduct_id>')
class Dataproduct(Resource):
    @api.doc('dataproduct')
    @api.response(404, 'Dataproduct not found or permission error')
    @api.marshal_with(dataproduct_info_result, skip_none=True)
    @optional_auth
    def get(self, dataproduct_id):
        """ Metadata of dataproduct

        """
        result = dataproduct_service.dataproduct(
            handler(), get_auth_user(), dataproduct_id
        )
        if result:
            return result
        else:
            api.abort(404, "Dataproduct not found or permission error")


@api.route('/weblayers')
class Weblayers(Resource):
    @api.doc('weblayers')
    @api.param('filter', 'Comma separated list of dataproduct identifiers')
    @optional_auth
    def get(self):
        """ List of selected dataproducts with web display information

        Retrieves the layers with names exactly matching those in the specified list, in that order.
        """
        layers = request.args.get('filter', "")

        return_layers = {}
        for layer in layers.split(","):
            results = weblayers_service.weblayers(
                handler(), get_auth_user(), layer)
            try:
                return_layers[layer] = results
            except:
                pass

        return return_layers


""" readyness probe endpoint """
@app.route("/ready", methods=['GET'])
def ready():
    return jsonify({"status": "OK"})


""" liveness probe endpoint """
@app.route("/healthz", methods=['GET'])
def healthz():
    return jsonify({"status": "OK"})


# local webserver
if __name__ == '__main__':
    print("Starting GetDataproduct service...")
    app.run(host='localhost', port=5023, debug=True)
