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

        ows_layer = handler.resources(dataproduct_id)
        # TODO: embed child layers + collect searchterms

        return ows_layer

    def _dataproduct_metadata(self, ows_layer, permissions, session):
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
