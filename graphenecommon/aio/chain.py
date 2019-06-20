# -*- coding: utf-8 -*-
import logging

from ..chain import AbstractGrapheneChain as SyncAbstractGrapheneChain

log = logging.getLogger(__name__)


class AbstractGrapheneChain(SyncAbstractGrapheneChain):
    def __init__(self, *args, **kwargs):
        # Initialize parent without connecting and wallet init to avoid calling async methods
        super().__init__(skip_wallet_init=True, offline=True, *args, **kwargs)

        # Remember passed node and credentials for later use to not force user to pass these
        # to conncet() again
        self._node = kwargs.get("node")
        self._rpcuser = kwargs.get("rpcuser")
        self._rpcpassword = kwargs.get("rpcpassword")
        self._num_retries = kwargs.get("num_retries")

    async def connect(self, node="", rpcuser="", rpcpassword="", **kwargs):
        """ Connect to blockchain network (internal use only)

            Async version does wallet initialization after connect because
            wallet depends on prefix which is available after connection only,
            and we want to keep __init__() synchronous, thus we're not
            performing connection there.
        """
        if not self._node:
            if "node" in self.config:
                self._node = self.config["node"]
            else:
                raise ValueError("A Blockchain node needs to be provided!")

        if not self._rpcuser and "rpcuser" in self.config:
            self._rpcuser = self.config["rpcuser"]

        if not self._rpcpassword and "rpcpassword" in self.config:
            self._rpcpassword = self.config["rpcpassword"]

        num_retries = kwargs.pop("num_retries", self._num_retries)

        self.rpc = self.rpc_class(
            self._node,
            self._rpcuser,
            self._rpcpassword,
            num_retries=num_retries,
            **kwargs
        )
        await self.rpc.connect()

        self.wallet = kwargs.get(
            "wallet", self.wallet_class(blockchain_instance=self, **kwargs)
        )

    async def info(self):
        """ Returns the global properties
        """
        return await self.rpc.get_dynamic_global_properties()

    async def finalizeOp(self, ops, account, permission, **kwargs):
        """ This method obtains the required private keys if present in
            the wallet, finalizes the transaction, signs it and
            broadacasts it

            :param operation ops: The operation (or list of operaions) to
                broadcast
            :param operation account: The account that authorizes the
                operation
            :param string permission: The required permission for
                signing (active, owner, posting)
            :param object append_to: This allows to provide an instance of
                ProposalsBuilder (see :func:`new_proposal`) or
                TransactionBuilder (see :func:`new_tx()`) to specify
                where to put a specific operation.

            ... note:: ``append_to`` is exposed to every method used in the
                this class

            ... note::

                If ``ops`` is a list of operation, they all need to be
                signable by the same key! Thus, you cannot combine ops
                that require active permission with ops that require
                posting permission. Neither can you use different
                accounts for different operations!

            ... note:: This uses ``txbuffer`` as instance of
                :class:`transactionbuilder.TransactionBuilder`.
                You may want to use your own txbuffer
        """
        if "append_to" in kwargs and kwargs["append_to"]:
            if self.proposer:
                log.warning(
                    "You may not use append_to and self.proposer at "
                    "the same time. Append new_proposal(..) instead"
                )
            # Append to the append_to and return
            append_to = kwargs["append_to"]
            parent = append_to.get_parent()
            assert isinstance(
                append_to, (self.transactionbuilder_class, self.proposalbuilder_class)
            )
            append_to.appendOps(ops)
            # Add the signer to the buffer so we sign the tx properly
            if isinstance(append_to, self.proposalbuilder_class):
                parent.appendSigner(append_to.proposer, permission)
            else:
                parent.appendSigner(account, permission)
            # This returns as we used append_to, it does NOT broadcast, or sign
            return append_to.get_parent()
        elif self.proposer:
            # Legacy proposer mode!
            proposal = self.proposal()
            proposal.set_proposer(self.proposer)
            proposal.set_expiration(self.proposal_expiration)
            proposal.set_review(self.proposal_review)
            proposal.appendOps(ops)
            # Go forward to see what the other options do ...
        else:
            # Append tot he default buffer
            self.txbuffer.appendOps(ops)

        # The API that obtains the fee only allows to specify one particular
        # fee asset for all operations in that transaction even though the
        # blockchain itself could allow to pay multiple operations with
        # different fee assets.
        if "fee_asset" in kwargs and kwargs["fee_asset"]:
            self.txbuffer.set_fee_asset(kwargs["fee_asset"])

        # Add signing information, signer, sign and optionally broadcast
        if self.unsigned:
            # In case we don't want to sign anything
            self.txbuffer.addSigningInformation(account, permission)
            return self.txbuffer
        elif self.bundle:
            # In case we want to add more ops to the tx (bundle)
            self.txbuffer.appendSigner(account, permission)
            return self.txbuffer.json()
        else:
            # default behavior: sign + broadcast
            self.txbuffer.appendSigner(account, permission)
            self.txbuffer.sign()
            return await self.txbuffer.broadcast()

    async def broadcast(self, tx=None):
        """ Broadcast a transaction to the Blockchain

            :param tx tx: Signed transaction to broadcast
        """
        if tx:
            # If tx is provided, we broadcast the tx
            return await self.transactionbuilder_class(
                tx, blockchain_instance=self
            ).broadcast()
        else:
            return await self.txbuffer.broadcast()