from qwc_services_core.database import DatabaseEngine
from flask import json
from importlib import import_module
import os
import re
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql import text as sql_text


DEFAULT_EXTENT_CFG = os.environ.get(
    'DEFAULT_EXTENT', '2590983.47500000009313226, 1212806.11562500009313226,\
                       2646267.02499999990686774, 1262755.00937499990686774')
DEFAULT_EXTENT = [float(x) for x in DEFAULT_EXTENT_CFG.split(',')]
DEFAULT_SEARCH_WMS_NAME = os.environ.get('DEFAULT_SEARCH_WMS_NAME', 'somap')


class WeblayersService:
    """WeblayersService class

    Collect metadata for WMS layers.
    """

    def __init__(self, logger):
        """Constructor

        :param Logger logger: Application logger
        """
        self.logger = logger
        self.db_engine = DatabaseEngine()
        # self.config_models = ConfigModels(self.db_engine)
        # self.permission = PermissionClient()

    def weblayers(self, identity, dataproduct_id):
        """Retrieve web display information for one layer

        :param str identity: User name or Identity dict
        :param str dataproduct_id: Dataproduct ID
        """
        metadata = {}

        permissions = self.permission.dataproduct_permissions(
            dataproduct_id, identity
        ) or {}
        wms_permissions = self.permission.ogc_permissions(
            DEFAULT_SEARCH_WMS_NAME, 'WMS', identity
        ) or {}
        permissions.update(wms_permissions)

        session = self.config_models.session()

        # find Group or Data layer object
        OWSLayer = self.config_models.model('ows_layer')
        query = session.query(OWSLayer).filter_by(name=dataproduct_id)
        ows_layer = query.first()
        if ows_layer is not None:
            metadata, searchterms = self.weblayer_metadata(
                ows_layer, True, permissions, session
            )

        session.close()

        return metadata

    def weblayer_metadata(self, ows_layer, visible, permissions, session):
        """Recursively collect metadata of a dataproduct.

        :param obj ows_layer: Group or Data layer object
        :param bool visible: True if layer is active
        :param obj permission: Dataproduct service permission
        :param Session session: DB session
        """
        metadata = {}

        # type
        sublayers = None
        data_set_view = None
        searchterms = []
        if ows_layer.type == 'group':
            if ows_layer.name not in permissions.get('group_layers', []):
                # group layer not permitted
                return (metadata, searchterms)
            # collect sub layers
            sublayers = []
            for group_layer in ows_layer.sub_layers:
                sub_layer = group_layer.sub_layer
                submetadata, subsearchterms = self.weblayer_metadata(
                    sub_layer, visible and group_layer.layer_active,
                    permissions, session
                )
                if submetadata:
                    if not ows_layer.facade:
                        sublayers.append(submetadata)
                    searchterms += subsearchterms

            if not sublayers and not ows_layer.facade:
                # sub layers not permitted, remove empty group
                return (metadata, searchterms)
        else:
            if ows_layer.name not in permissions.get('data_layers', []):
                # data layer not permitted
                return (metadata, searchterms)

            # find matching DataSetView
            DataSetView = self.config_models.model('data_set_view')
            query = session.query(DataSetView).filter_by(name=ows_layer.name)
            data_set_view = query.first()

        queryable = ows_layer.name in permissions['queryable_layers']
        displayField = ""
        if ows_layer.name in permissions['displayfields']:
            displayField = permissions['displayfields'][ows_layer.name]
        ows_metadata = self.ows_metadata(ows_layer)
        abstract = ows_metadata.get('abstract')
        metadata = {
            'name': ows_layer.name,
            'title': ows_layer.title,
            'abstract': abstract,
            'visibility': visible,
            'queryable': queryable,
            'displayField': displayField,
            'opacity': round(
                (100.0 - ows_layer.layer_transparency)/100.0 * 255
            ),
            'bbox': {
                'crs': 'EPSG:2056',
                'bounds': DEFAULT_EXTENT
            }
        }
        if sublayers:
            metadata.update({
                'sublayers': sublayers
            })
        if data_set_view:
            if data_set_view.facet:
                metadata.update({
                    'searchterms': [data_set_view.facet]
                    })
                searchterms.append(data_set_view.facet)
        elif len(searchterms) > 0:
            metadata.update({
                'searchterms': searchterms
            })

        return (metadata, searchterms)

    def ows_metadata(self, layer):
        """Return ows_metadata for a layer.

        :param obj layer: Group or Data layer object
        """
        ows_metadata = {}

        if layer.ows_metadata:
            try:
                # load JSON from ows_metadata
                ows_metadata = json.loads(layer.ows_metadata)
            except ValueError as e:
                self.logger.warning(
                    "Invalid JSON in ows_metadata of layer %s: %s" %
                    (layer.name, e)
                )

        return ows_metadata
