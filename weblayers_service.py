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
            return {}

        metadata = []
        resource = handler.weblayers.get(dataproduct_id)
        if resource:
            visible = resource.get('visibility', True)
            entry, _ = self._build_tree(
                resource, visible, handler.weblayers, permitted_resources)
            metadata.append(entry)

        return metadata

    def _build_tree(self, resource, visible, all_resources, permissions):
        """Recursively collect metadata of a dataproduct.
        """
        searchterms = []
        sublayers = []
        for sublayer in resource.get('sublayers', []):
            if sublayer in permissions:
                subresource = all_resources.get(sublayer)
                subvisible = visible and subresource.get('visibility', True)
                submetadata, subsearchterms = self._build_tree(
                        subresource, subvisible, all_resources, permissions)
                if submetadata:
                    if subresource.get('type') != 'facadelayer':
                        sublayers.append(submetadata)
                    searchterms += subsearchterms

        metadata = {
            'name': resource.get('identifier'),
            'title': resource.get('display'),
            'abstract': resource.get('description'),
            'visibility': visible and resource.get('visibility', True),
            'queryable': resource.get('queryable'),
            'displayField': resource.get('displayField'),
            'searchterms': resource.get('searchterms'),
            'opacity': resource.get('opacity'),
            'bbox': {
                'bounds': resource.get('bbox'),
                'crs': resource.get('crs')
            }
        }
        if sublayers:
            metadata['sublayers'] = sublayers

        # Filter null entries
        metadata = {
            k: v for k, v in metadata.items() if v is not None
        }
        return (metadata, searchterms)
