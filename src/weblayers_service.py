import base64


class WeblayersService:
    """WeblayersService class

    Collect metadata for WMS layers.
    """

    def __init__(self, logger):
        """Constructor

        :param Logger logger: Application logger
        """
        self.logger = logger

    def weblayers(self, handler, identity, dataproduct_id):
        """Retrieve web display information for one layer

        :param str identity: User name or Identity dict
        :param str dataproduct_id: Dataproduct ID
        """
        permitted_resources = handler.permissions_handler.resource_permissions(
            'dataproducts', identity
        )
        if dataproduct_id not in permitted_resources:
            return []

        metadata = []
        resource = handler.weblayers.get(dataproduct_id)
        if resource and dataproduct_id not in handler.facade_sublayers:
            # NOTE: requested dataproduct is always visible
            entry, _ = self._build_tree(
                resource, True, handler.weblayers, permitted_resources)
            if entry:
                metadata.append(entry)

        return metadata

    def _build_tree(self, resource, visible, all_resources, permissions):
        """Recursively collect metadata of a dataproduct.
        """
        searchterms = []
        sublayers = []

        if 'wms_datasource' not in resource:
            # skip dataproduct if not in WMS
            return ([], [])

        for sublayer in resource.get('sublayers', []):
            if sublayer.get('identifier') in permissions:
                subresource = all_resources.get(sublayer.get('identifier'))
                # NOTE: no sublayers visible if parent is not visible
                subvisible = visible and sublayer.get('visibility', True)
                submetadata, subsearchterms = self._build_tree(
                        subresource, subvisible, all_resources, permissions)
                if submetadata:
                    if resource.get('type') != 'facadelayer':
                        sublayers.append(submetadata)
                    searchterms += subsearchterms

        abstract = None
        if resource.get('description'):
            abstract = resource.get('description')
        elif resource.get('description_base64'):
            try:
                base64_value = resource.get('description_base64')
                abstract = base64.b64decode(base64_value).decode('utf-8')
            except Exception as e:
                self.logger.error(
                    "Could not decode Base64 encoded value for description "
                    "of '%s':\n%s\n%s"
                    % (resource.get('identifier'), e, base64_value)
                )
                abstract = base64_value

        metadata = {
            'name': resource.get('identifier'),
            'title': resource.get('display'),
            'abstract': abstract,
            'visibility': visible,
            'queryable': resource.get('queryable'),
            'displayField': resource.get('displayField'),
            'searchterms': resource.get('searchterms'),
            'opacity': resource.get('opacity'),
            'bbox': {
                'bounds': resource.get('bbox'),
                'crs': resource.get('crs')
            }
        }
        if resource.get('external_layer'):
            metadata['externalLayer'] = resource.get('external_layer')
            # Overwrite missing BBOX for external WMS/WMTS
            metadata['bbox'] = {
                'bounds': [5.70211, 45.7392, 10.6432, 47.8505],
                'crs': 'EPSG:4326'
            }
            if metadata['externalLayer'].get('type', '') == 'wmts':
                metadata['queryable'] = False
        if sublayers:
            metadata['sublayers'] = sublayers

        # metadata from MetaDB
        if 'metadata' in resource:
            metadata['metadata'] = resource['metadata']

        # Filter null entries
        metadata = {
            k: v for k, v in metadata.items() if v is not None
        }
        return (metadata, searchterms)
