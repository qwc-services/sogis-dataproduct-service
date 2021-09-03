import base64


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

        description = None
        if resource.get('description'):
            description = resource.get('description')
        elif resource.get('description_base64'):
            description = self.b64decode(
                resource.get('description_base64'),
                "description of '%s'" % resource.get('identifier')
            )

        qml = None
        if resource.get('qml'):
            qml = resource.get('qml')
        elif resource.get('qml_base64'):
            qml = self.b64decode(
                resource.get('qml_base64'),
                "qml of '%s'" % resource.get('identifier')
            )

        # embed any QML assets
        for asset in resource.get('qml_assets', []):
            # replace symbol paths in QML with embedded asset as base64
            pattern = "v=\"%s\"" % asset.get('path')
            replacement = "v=\"base64:%s\"" % asset.get('base64')
            qml = qml.replace(pattern, replacement)

        metadata = {
            k: v for k, v in resource.items() if k not in IGNORE_KEYS}
        metadata.update({
            'description': description,
            'sublayers': sublayers
        })
        if len(searchterms) > 0:
            metadata.update({
                'searchterms': searchterms
            })
        if qml:
            metadata.update({
                'qml': qml
            })
        return (metadata, searchterms)

    def b64decode(self, base64_value, description=""):
        """Return decoded Base64 encoded value or raw value on error.

        :param str base64_value: Base64 encoded value
        :param str description: Description included in error message
        """
        value = base64_value
        try:
            value = base64.b64decode(base64_value).decode('utf-8')
        except Exception as e:
            self.logger.error(
                "Could not decode Base64 encoded value for %s:"
                "\n%s\n%s" % (description, e, base64_value)
            )
            value = base64_value
        return value


IGNORE_KEYS = [
    'queryable', 'displayField', 'opacity', 'description_base64', 'qml_base64',
    'qml_assets'
]
