class DataproductService:
    """DataproductService class

    Collect dataproduct metadata.
    """

    def __init__(self, logger):
        """Constructor

        :param Logger logger: Application logger
        """
        self.logger = logger

    def dataproduct(self, handler, identity, dataproduct_id):
        """Return collected metadata of a dataproduct.

        :param str identity: User name or Identity dict
        :param str dataproduct_id: Dataproduct ID
        """
        permitted_resources = handler.permissions_handler.resource_permissions(
            'dataproducts', identity
        )
        if dataproduct_id not in permitted_resources:
            return {}

        metadata = []
        selected_resources = handler.resources(dataproduct_id)
        for resource in selected_resources:
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
            k: v for k, v in resource.items() if k not in IGNORE_KEYS}
        metadata.update({'sublayers': sublayers})
        if len(searchterms) > 0:
            metadata.update({
                'searchterms': searchterms
            })
        return (metadata, searchterms)


IGNORE_KEYS = ['visibility', 'queryable', 'displayField', 'opacity']
