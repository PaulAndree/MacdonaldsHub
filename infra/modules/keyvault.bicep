// Key Vault for secrets (RNF-04, ADR-15). RBAC only; no access policies. The application
// identities can only read secrets. Secrets that need a human-held value (the Google client
// secret, decision P-07) are created out of band and never pass through this template.
param location string
param vaultName string
param tenantId string
param enablePurgeProtection bool
param secretReaderPrincipalIds array
param appInsightsName string
param tags object

var secretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  tags: tags
  properties: {
    tenantId: tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: enablePurgeProtection ? true : null
    publicNetworkAccess: 'Enabled'
  }
}

resource appInsightsSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'appinsights-connection-string'
  properties: {
    value: appInsights.properties.ConnectionString
  }
}

resource reader 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in secretReaderPrincipalIds: {
    name: guid(vault.id, principalId, secretsUserRoleId)
    scope: vault
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUserRoleId)
    }
  }
]

output vaultUri string = vault.properties.vaultUri
output vaultName string = vault.name
