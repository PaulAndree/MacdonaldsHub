// Storage account with the `uploads` and `confirmed` containers and CORS (ADR-14).
// No shared keys and no public access: the API signs user-delegation SAS with its managed
// identity. `confirmed` is created with version-level immutability enabled so a retention policy
// can be applied once P-05 fixes the period; no retention period is invented here, and no
// application identity is granted delete or write on `confirmed` in this change.
param location string
param storageName string
param skuName string
param frontendOrigin string
param backendPrincipalId string
param tags object

var blobDelegatorRoleId = 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'
var blobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var blobDataReaderRoleId = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: skuName
  }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    immutableStorageWithVersioning: {
      enabled: true
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: account
  name: 'default'
  properties: {
    isVersioningEnabled: true
    cors: {
      corsRules: [
        {
          allowedOrigins: [
            frontendOrigin
          ]
          allowedMethods: [
            'PUT'
            'OPTIONS'
          ]
          allowedHeaders: [
            '*'
          ]
          exposedHeaders: [
            '*'
          ]
          maxAgeInSeconds: 600
        }
      ]
    }
  }
}

resource uploads 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'uploads'
  properties: {
    publicAccess: 'None'
  }
}

resource confirmed 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'confirmed'
  properties: {
    publicAccess: 'None'
    immutableStorageWithVersioning: {
      enabled: true
    }
  }
}

resource delegator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, backendPrincipalId, blobDelegatorRoleId)
  scope: account
  properties: {
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDelegatorRoleId)
  }
}

resource uploadsContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(uploads.id, backendPrincipalId, blobDataContributorRoleId)
  scope: uploads
  properties: {
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleId)
  }
}

resource confirmedReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(confirmed.id, backendPrincipalId, blobDataReaderRoleId)
  scope: confirmed
  properties: {
    principalId: backendPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataReaderRoleId)
  }
}

output accountName string = account.name
output blobEndpoint string = account.properties.primaryEndpoints.blob
