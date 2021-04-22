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

        metadata = {}
        resource = handler.dataproducts.get(dataproduct_id)
        if resource:
            entry, _ = self._build_tree(
                resource, handler.dataproducts, permitted_resources)
            metadata = entry

        return metadata

    def _build_tree(self, resource, all_resources, permissions):
        """Recursively collect metadata of a dataproduct.
        """
        searchterms = []
        sublayers = []
        for sublayer in resource.get('sublayers', []):
            if sublayer.get('identifier') in permissions:
                subresource = all_resources.get(sublayer.get('identifier'))
                submetadata, subsearchterms = self._build_tree(
                        subresource, all_resources, permissions)
                if submetadata:
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
