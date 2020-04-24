from qwc_services_core.database import DatabaseEngine
from flask import json
from importlib import import_module
import base64
import os
import re
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql import text as sql_text
from xml.etree import ElementTree


DEFAULT_EXTENT_CFG = os.environ.get(
    'DEFAULT_EXTENT', '2590983.47500000009313226, 1212806.11562500009313226,\
                       2646267.02499999990686774, 1262755.00937499990686774')
DEFAULT_EXTENT = [float(x) for x in DEFAULT_EXTENT_CFG.split(',')]
WMS_SERVICE_URL = os.environ.get('WMS_SERVICE_URL', '')
RASTER_DATASOURCE_PATTERN = os.environ.get('RASTER_DATASOURCE_PATTERN', '')
RASTER_DATASOURCE_REPL = os.environ.get('RASTER_DATASOURCE_REPL', '')
QGS_RESOURCES_DIR = os.environ.get('QGS_RESOURCES_DIR', '')


class DataproductService:
    """DataproductService class

    Collect dataproduct metadata.
    """

    def __init__(self, logger):
        """Constructor

        :param Logger logger: Application logger
        """
        self.logger = logger
        self.db_engine = DatabaseEngine()
        # self.config_models = ConfigModels(self.db_engine)
        # self.permission = PermissionClient()

    def dataproduct(self, identity, dataproduct_id):
        """Return collected metadata of a dataproduct.

        :param str identity: User name or Identity dict
        :param str dataproduct_id: Dataproduct ID
        """
        metadata = {}

        permissions = self.permission.dataproduct_permissions(
            dataproduct_id, identity
        ) or {}

        session = self.config_models.session()

        # find Group or Data layer object
        OWSLayer = self.config_models.model('ows_layer')
        query = session.query(OWSLayer).filter_by(name=dataproduct_id)
        ows_layer = query.first()
        if ows_layer is not None:
            metadata, searchterms = self.dataproduct_metadata(
                ows_layer, permissions, session
            )
        else:
            # find DataSetView for basic DataSet
            DataSetView = self.config_models.model('data_set_view')
            query = session.query(DataSetView).filter_by(name=dataproduct_id)
            data_set_view = query.first()
            if data_set_view is not None:
                if data_set_view.name in permissions.get('basic_datasets', []):
                    # basic DataSet permitted
                    metadata = self.basic_dataset_metadata(
                        data_set_view, session
                    )

        session.close()

        return metadata

    def dataproduct_metadata(self, ows_layer, permissions, session):
        """Recursively collect metadata of a dataproduct.

        :param obj ows_layer: Group or Data layer object
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

            if ows_layer.facade:
                dataproduct_type = 'facadelayer'
            else:
                dataproduct_type = 'layergroup'

            # collect sub layers
            sublayers = []
            for group_layer in ows_layer.sub_layers:
                sub_layer = group_layer.sub_layer
                submetadata, subsearchterms = self.dataproduct_metadata(
                    sub_layer, permissions, session
                )
                if submetadata:
                    sublayers.append(submetadata)
                    searchterms += subsearchterms

            if not sublayers:
                # sub layers not permitted, remove empty group
                return (metadata, searchterms)
        else:
            if ows_layer.name not in permissions.get('data_layers', []):
                # data layer not permitted
                return (metadata, searchterms)

            dataproduct_type = 'datasetview'
            # find matching DataSetView
            DataSetView = self.config_models.model('data_set_view')
            query = session.query(DataSetView).filter_by(name=ows_layer.name)
            data_set_view = query.first()

        contacts = self.dataproduct_contacts(ows_layer, session)
        datasource = self.dataproduct_datasource(ows_layer, session)
        wms_datasource = self.dataproduct_wms(ows_layer, session)
        ows_metadata = self.ows_metadata(ows_layer)
        description = ows_metadata.get('abstract')

        # qml
        qml = None
        if ows_layer.type == 'data':
            qml = ows_layer.client_qgs_style or ows_layer.qgs_style
            # embed any uploaded symbols in QML
            qml = self.update_qml(qml)

        metadata = {
            'identifier': ows_layer.name,
            'display': ows_layer.title,
            'type': dataproduct_type,
            'synonyms': self.split_values(ows_layer.synonyms),
            'keywords': self.split_values(ows_layer.keywords),
            'description': description,
            'contacts': contacts,
            'wms_datasource': wms_datasource,
            'qml': qml,
            'sublayers': sublayers
        }
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
        metadata.update(datasource)

        return (metadata, searchterms)

    def basic_dataset_metadata(self, data_set_view, session):
        """Collect metadata of a basic DataSet dataproduct.

        :param obj data_set_view: DataSetView object
        :param Session session: DB session
        """
        metadata = {}

        contacts = self.basic_dataset_contacts(data_set_view, session)

        metadata = {
            'identifier': data_set_view.name,
            'display': data_set_view.data_set.data_set_name,
            'type': 'datasetview',
            'description': data_set_view.description,
            'contacts': contacts,
            'datatype': 'table'
        }

        if data_set_view.facet:
            metadata.update({
                'searchterms': [data_set_view.facet]
            })

        return metadata

    def dataproduct_contacts(self, ows_layer, session):
        """Return contacts metadata for a dataproduct.

        :param obj ows_layer: Group or Data layer object
        :param Session session: DB session
        """
        # collect contacts for layer and related GDI resources
        gdi_oids = [ows_layer.gdi_oid]
        if ows_layer.type == 'data':
            # include data source
            gdi_oids.append(
                ows_layer.data_set_view.data_set.gdi_oid_data_source
            )

        return self.contacts(gdi_oids, session)

    def basic_dataset_contacts(self, data_set_view, session):
        """Return contacts metadata for a basic DataSet dataproduct.

        :param obj data_set_view: DataSetView object
        :param Session session: DB session
        """
        # collect contacts for basic DataSet and related GDI resources
        gdi_oids = [
            data_set_view.gdi_oid, data_set_view.data_set.gdi_oid_data_source
        ]
        return self.contacts(gdi_oids, session)

    def contacts(self, gdi_oids, session):
        """Return contacts metadata for a list of resource IDs.

        :param list[int] gdi_oids: List of GDI resource IDs
        :param Session session: DB session
        """
        contacts = []

        ResourceContact = self.config_models.model('resource_contact')
        Contact = self.config_models.model('contact')
        query = session.query(ResourceContact) \
            .filter(ResourceContact.gdi_oid_resource.in_(gdi_oids)) \
            .order_by(ResourceContact.id_contact_role)
        # eager load relations
        query = query.options(
            joinedload(ResourceContact.contact)
            .joinedload(Contact.organisation)
        )
        for res_contact in query.all():
            person = res_contact.contact
            person_data = {
                'id': person.id,
                'name': person.name,
                'function': person.function,
                'email': person.email,
                'phone': person.phone,
                'street': person.street,
                'house_no': person.house_no,
                'zip': person.zip,
                'city': person.city,
                'country_code': person.country_code
            }

            organisation_data = None
            organisation = person.organisation
            if organisation is not None:
                organisation_data = {
                    'id': organisation.id,
                    'name': organisation.name,
                    'unit': organisation.unit,
                    'abbreviation': organisation.abbreviation,
                    'street': organisation.street,
                    'house_no': organisation.house_no,
                    'zip': organisation.zip,
                    'city': organisation.city,
                    'country_code': organisation.country_code
                }

            contacts.append({
                'person': person_data,
                'organisation': organisation_data
            })

        return contacts

    def dataproduct_datasource(self, ows_layer, session):
        """Return datasource metadata for a dataproduct.

        :param obj ows_layer: Group or Data layer object
        :param Session session: DB session
        """
        metadata = {}

        if ows_layer.type == 'group':
            # group layer
            return metadata

        data_set = ows_layer.data_set_view.data_set
        data_source = data_set.data_source
        if data_source.connection_type == 'database':
            # vector DataSet

            # get table metadata
            postgis_datasource = None
            pg_metadata = self.dataset_info(
                data_source.gdi_oid, data_set.data_set_name
            )
            if 'error' not in pg_metadata:
                data_set_name = "%s.%s" % (
                    pg_metadata.get('schema'), pg_metadata.get('table')
                )

                primary_key = pg_metadata.get('primary_key')
                if primary_key is None:
                    # get primary key if view
                    primary_key = data_set.primary_key

                geom = {}
                if len(pg_metadata.get('geometry_columns')) > 1:
                    used_col = ows_layer.data_set_view.geometry_column
                    for geom_col in pg_metadata.get('geometry_columns'):
                        # get used geometry column if multiple
                        if geom_col.get('geometry_column') == used_col:
                            geom = geom_col
                        break
                elif len(pg_metadata.get('geometry_columns')) == 1:
                    # use sole geometry column
                    geom = pg_metadata.get('geometry_columns')[0]

                postgis_datasource = {
                    'dbconnection': data_source.connection,
                    'data_set_name': data_set_name,
                    'primary_key': primary_key,
                    'geometry_field': geom.get('geometry_column'),
                    'geometry_type': geom.get('geometry_type'),
                    'srid': geom.get('srid')
                }
            else:
                # show error message
                postgis_datasource = {
                    'error': pg_metadata.get('error')
                }

            metadata = {
                'bbox': DEFAULT_EXTENT,
                'crs': 'EPSG:2056',
                'datatype': 'vector',
                'postgis_datasource': postgis_datasource
            }
        else:
            # raster DataSet

            # modify connection dir
            connection = re.sub(
                RASTER_DATASOURCE_PATTERN, RASTER_DATASOURCE_REPL,
                data_source.connection
            )
            # TODO: get srid
            srid = 'EPSG:2056'
            metadata = {
                'datatype': 'raster',
                'raster_datasource': {
                    'datasource': connection + data_set.data_set_name,
                    'srid': srid
                }
            }

        return metadata

    def dataset_info(self, data_source_id, table_name):
        """Return table metadata for a data_set.

        :param int data_source_id: data_source ID
        :param str table_name: Table name as "<schema>.<table>"
        """
        # NOTE: form field returns 'None' as string if not set
        if not table_name or table_name == 'None':
            # empty table name
            return None

        # parse schema and table name
        parts = table_name.split('.')
        if len(parts) > 1:
            schema = parts[0]
            table_name = parts[1]
        else:
            schema = 'public'

        return self.postgis_metadata(data_source_id, schema, table_name)

    def postgis_metadata(self, data_source_id, schema, table_name):
        """Return primary key, geometry columns, types and srids
        from a PostGIS table.

        :param int data_source_id: data_source ID
        :param str schema: DB schema name
        :param str table_name: DB table name
        """
        metadata = {}

        try:
            engine = self.engine_for_data_source(data_source_id)
            if engine is None:
                return {
                    'error': "FEHLER: DataSource nicht gefunden"
                }

            # connect to data_source
            conn = engine.connect()

            # get primary key

            # build query SQL
            sql = sql_text("""
                SELECT a.attname
                FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid
                        AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = '{schema}.{table}'::regclass
                    AND i.indisprimary;
            """.format(schema=schema, table=table_name))

            # execute query
            primary_key = None
            result = conn.execute(sql)
            for row in result:
                primary_key = row['attname']

            # get geometry column and srid

            # build query SQL
            sql = sql_text("""
                SELECT f_geometry_column, srid, type
                FROM geometry_columns
                WHERE f_table_schema = '{schema}' AND f_table_name = '{table}';
            """.format(schema=schema, table=table_name))

            # execute query
            geometry_columns = []
            result = conn.execute(sql)
            for row in result:
                geometry_columns.append({
                    'geometry_column': row['f_geometry_column'],
                    'geometry_type': row['type'],
                    'srid': row['srid']
                })

            # close database connection
            conn.close()

            metadata = {
                'schema': schema,
                'table': table_name,
                'primary_key': primary_key,
                'geometry_columns': geometry_columns
            }
        except OperationalError as e:
            self.logger.error(e.orig)
            return {
                'error': "OperationalError: %s" % e.orig
            }
        except ProgrammingError as e:
            self.logger.error(e.orig)
            return {
                'error': "ProgrammingError: %s" % e.orig
            }

        return metadata

    def engine_for_data_source(self, data_source_id):
        """Return SQLAlchemy engine for a data_source.

        :param int data_source_id: data_source ID
        """
        engine = None

        # find data_source
        DataSource = self.config_models.model('data_source')
        session = self.config_models.session()
        query = session.query(DataSource) \
            .filter_by(gdi_oid=data_source_id)
        data_source = query.first()
        session.close()

        if data_source is not None:
            engine = self.db_engine.db_engine(data_source.connection)

        return engine

    def dataproduct_wms(self, ows_layer, session):
        """Return any WMS datasource for a dataproduct.

        :param obj ows_layer: Group or Data layer object
        :param Session session: DB session
        """
        wms_datasource = None

        # get WMS root layer
        root_layer = None
        WmsWfs = self.config_models.model('wms_wfs')
        query = session.query(WmsWfs).filter_by(ows_type='WMS')
        # eager load relation
        query = query.options(
            joinedload(WmsWfs.root_layer)
        )
        wms_wfs = query.first()
        if wms_wfs is not None:
            root_layer = wms_wfs.root_layer

        if self.layer_in_ows(ows_layer, root_layer):
            wms_datasource = {
                'service_url': WMS_SERVICE_URL,
                'name': ows_layer.name
            }

        return wms_datasource

    def layer_in_ows(self, ows_layer, root_layer):
        """Recursively check if layer is a WMS layer.

        :param obj ows_layer: Group or Data layer object
        :param obj root_layer: WMS root layer
        """
        if root_layer is None:
            # no WMS root layer
            return False

        in_wms = False
        # get parent groups
        parents = [p.group for p in ows_layer.parents]
        for parent in parents:
            if parent.gdi_oid == root_layer.gdi_oid:
                # parent is WMS root layer
                in_wms = True
            else:
                # check if parent group is a WMS layer
                in_wms = in_wms or self.layer_in_ows(parent, root_layer)
            if in_wms:
                break

        return in_wms

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

    def split_values(self, value):
        """Split comma separated values into list.

        :param str value: Comma separated values
        """
        if value:
            return [s.strip() for s in value.split(',')]
        else:
            return []

    def update_qml(self, qml):
        """Update QML with embedded symbols.

        param str qml: QML XML string
        """
        if qml is None:
            return qml

        try:
            # parse XML
            root = ElementTree.fromstring(qml)

            # embed symbols
            self.embed_qml_symbols(root, 'SvgMarker', 'name')
            self.embed_qml_symbols(root, 'SVGFill', 'svgFile')
            self.embed_qml_symbols(root, 'RasterFill', 'imageFile')

            # return updated QML
            qml = ElementTree.tostring(
                root, encoding='utf-8', method='xml'
            )
            return qml.decode()
        except Exception as e:
            self.logger.warning(
                "Could not embed QML symbols:\n%s" % e
            )
            return qml

    def embed_qml_symbols(self, root, layer_class, prop_key):
        """Embed symbol resources as base64 in QML.

        :param xml.etree.ElementTree.Element root: XML root node
        :param str layer_class: Symbol layer class
        :param str prop_key: Symbol layer prop key for symbol path
        """
        for svgprop in root.findall(".//layer[@class='%s']/prop[@k='%s']" %
                                    (layer_class, prop_key)):
            symbol_path = svgprop.get('v')
            path = os.path.abspath(
                os.path.join(QGS_RESOURCES_DIR, symbol_path)
            )

            # NOTE: assume symbols not included in ZIP are default symbols
            if os.path.exists(path):
                try:
                    # read symbol data and convert to base64
                    with open(path, 'rb') as f:
                        symbol_data = base64.b64encode(f.read())

                    # embed symbol in QML
                    svgprop.set('v', "base64:%s" % symbol_data.decode())
                    self.logger.info("Embed symbol in QML: %s" % symbol_path)
                except Exception as e:
                    self.logger.warning(
                        "Could not embed QML symbol %s:\n%s" % (symbol_path, e)
                    )
