class SharedInstance:
    """ This class merely offers a singelton for the Blockchain Instance
    """

    instance = None
    config = {}


class BlockchainInstance:
    """ This is a class that allows compatibility with previous
        naming conventions. It will extract 'blockchain_instance'
        from the key word arguments and ensure that self.blockchain
        contains an instance of the main chain instance
    """

    def get_instance_class(self):
        """ Should return the Chain instance class, e.g. `bitshares.BitShares`
        """
        raise NotImplementedError

    def clear_cache(self):
        raise NotImplementedError

    def __init__(self, *args, **kwargs):
        if "blockchain_instance" in kwargs and kwargs["blockchain_instance"]:
            SharedInstance.instance = kwargs["blockchain_instance"]

    @property
    def blockchain(self):
        return self.shared_blockchain_instance()

    @property
    def chain(self):
        """ Short form for blockchain (for the lazy)
        """
        return self.blockchain

    def shared_blockchain_instance(self):
        """ This method will initialize ``SharedInstance.instance`` and return it.
            The purpose of this method is to have offer single default
            instance that can be reused by multiple classes.
        """
        if not SharedInstance.instance:
            klass = self.get_instance_class()
            SharedInstance.instance = klass(**SharedInstance.config)
        return SharedInstance.instance

    @staticmethod
    def set_shared_blockchain_instance(instance):
        """ This method allows us to override default instance for all
            users of ``SharedInstance.instance``.

            :param chaininstance instance: Chain instance
        """
        SharedInstance.instance = instance

    def set_shared_config(self, config):
        """ This allows to set a config that will be used when calling
            ``shared_blockchain_instance`` and allows to define the configuration
            without requiring to actually create an instance
        """
        assert isinstance(config, dict)
        SharedInstance.config.update(config)
        # if one is already set, delete
        if SharedInstance.instance:
            self.shared_blockchain_instance().clear_cache()
            SharedInstance.instance = None
