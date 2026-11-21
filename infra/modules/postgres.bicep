// PostgreSQL Flexible Server, one per environment (ADR-04, ADR-15, BASE-10).
// Microsoft Entra authentication only: there is no database password anywhere. The backend
// managed identity is the database principal (an administrator in v1; a least-privilege split
// is a later hardening). Public access is limited to Azure services and TLS is required; a
// private network is a later hardening. Availability and backup objectives are pending (P-05):
// high availability is off and backup retention is the Azure default, neither a decision.
param location string
param serverName string
param tenantId string
param skuName string
param skuTier string
param storageGb int
param backupRetentionDays int
param databaseName string
param adminPrincipalId string
param adminPrincipalName string
param tags object

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: '17'
    storage: {
      storageSizeGB: storageGb
    }
    backup: {
      backupRetentionDays: backupRetentionDays
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: tenantId
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

// Server child resources are deployed one after another to avoid conflicting operations.
resource allowAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: server
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIPs'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource admin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: server
  name: adminPrincipalId
  properties: {
    principalType: 'ServicePrincipal'
    principalName: adminPrincipalName
    tenantId: tenantId
  }
  dependsOn: [
    allowAzureServices
  ]
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
  dependsOn: [
    admin
  ]
}

output serverName string = server.name
output serverId string = server.id
output fqdn string = server.properties.fullyQualifiedDomainName
output databaseName string = database.name
