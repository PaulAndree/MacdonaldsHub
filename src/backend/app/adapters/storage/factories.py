from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from app.adapters.storage.blob import (
    BlobStorageService,
    account_key_signer,
    user_delegation_signer,
)
from app.services.ports import StorageService
from app.settings import Settings


def azurite_storage(settings: Settings) -> StorageService:
    assert settings.storage_connection_string is not None  # guaranteed by Settings validation
    client = BlobServiceClient.from_connection_string(
        settings.storage_connection_string.get_secret_value()
    )
    key = client.credential.account_key
    service = BlobStorageService(
        client, account_key_signer(client, key), settings.storage_public_endpoint
    )
    service.ensure_containers()
    service.ensure_cors(settings.frontend_origin)
    return service


def azure_blob_storage(settings: Settings) -> StorageService:
    assert settings.storage_account_url is not None  # guaranteed by Settings validation
    client = BlobServiceClient(settings.storage_account_url, credential=DefaultAzureCredential())
    return BlobStorageService(client, user_delegation_signer(client))
