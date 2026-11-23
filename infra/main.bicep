// Delivery Hub platform. One resource group per environment (test, production) with its own
// database, storage and secrets: nothing is shared between environments (BASE-10).
// Parameters per environment: main.test.bicepparam / main.prod.bicepparam
targetScope = 'resourceGroup'

@allowed(['test', 'production'])
param environmentName string
param location string = resourceGroup().location
param namePrefix string = 'deliveryhub'

@description('infrastructure: shared resources only. jobs: adds the migration job (needs images in the registry). applications: adds frontend, API, worker and alerts. Each stage includes the previous one.')
@allowed(['infrastructure', 'jobs', 'applications'])
param deploymentStage string = 'infrastructure'
param imageTag string = 'latest'

@description('Easy Auth with Google on the frontend. Needs the Google client (decision P-07) and the secret google-client-secret in Key Vault.')
param easyAuthEnabled bool = false
param googleClientId string = ''

@description('Stable identifier the allowlist matches on: decision P-07, no default.')
@allowed(['', 'sub', 'email'])
param allowlistIdentifier string = ''
param initialAdminEmail string = ''
param initialAdminSubject string = ''

@description('Comma-separated branch names loaded by the seed job (P-01). Imports stay off until it is set.')
param branchCatalog string = ''
@description('Enables importing XLSX files; the processes refuse to start if the branch catalog is empty.')
param importsEnabled bool = false
param alertEmail string = ''

// Sizing and redundancy are provisional until P-05 sets availability and backup objectives.
param postgresSkuName string = 'Standard_B1ms'
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param postgresSkuTier string = 'Burstable'
param postgresStorageGb int = 32
param postgresBackupRetentionDays int = 7
param storageSkuName string = 'Standard_LRS'
param enableKeyVaultPurgeProtection bool = false

var envShort = environmentName == 'production' ? 'prd' : 'tst'
var prefix = '${namePrefix}-${environmentName}'
var unique = uniqueString(resourceGroup().id)
var tags = {
  application: 'delivery-hub'
  environment: environmentName
  'managed-by': 'bicep'
}
var deployJobs = deploymentStage != 'infrastructure'
var deployApps = deploymentStage == 'applications'

var frontendAppName = '${prefix}-frontend'
var apiAppName = '${prefix}-api'
var workerAppName = '${prefix}-worker'
var databaseName = 'deliveryhub'

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    namePrefix: prefix
    tags: tags
  }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  params: {
    location: location
    registryName: take('${replace(namePrefix, '-', '')}${envShort}${unique}', 50)
    pullPrincipalIds: [
      identity.outputs.frontendPrincipalId
      identity.outputs.backendPrincipalId
    ]
    tags: tags
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    namePrefix: prefix
    alertEmail: alertEmail
    tags: tags
  }
}

module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    vaultName: take('kv-${namePrefix}-${envShort}-${unique}', 24)
    tenantId: subscription().tenantId
    enablePurgeProtection: enableKeyVaultPurgeProtection
    secretReaderPrincipalIds: [
      identity.outputs.frontendPrincipalId
      identity.outputs.backendPrincipalId
    ]
    appInsightsName: monitoring.outputs.appInsightsName
    tags: tags
  }
}

module environment 'modules/container-env.bicep' = {
  name: 'container-env'
  params: {
    location: location
    environmentName: '${prefix}-env'
    workspaceName: monitoring.outputs.workspaceName
    tags: tags
  }
}

var frontendOrigin = 'https://${frontendAppName}.${environment.outputs.defaultDomain}'

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageName: take('${replace(namePrefix, '-', '')}${envShort}${unique}', 24)
    skuName: storageSkuName
    frontendOrigin: frontendOrigin
    backendPrincipalId: identity.outputs.backendPrincipalId
    tags: tags
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    serverName: '${prefix}-pg-${take(unique, 6)}'
    tenantId: subscription().tenantId
    skuName: postgresSkuName
    skuTier: postgresSkuTier
    storageGb: postgresStorageGb
    backupRetentionDays: postgresBackupRetentionDays
    databaseName: databaseName
    adminPrincipalId: identity.outputs.backendPrincipalId
    adminPrincipalName: identity.outputs.backendName
    tags: tags
  }
}

var backendImage = '${registry.outputs.loginServer}/delivery-hub-backend:${imageTag}'
var frontendImage = '${registry.outputs.loginServer}/delivery-hub-frontend:${imageTag}'

var backendSecrets = [
  {
    name: 'appinsights-connection-string'
    keyVaultUrl: '${keyvault.outputs.vaultUri}secrets/appinsights-connection-string'
    identity: identity.outputs.backendId
  }
]

// No DEV_IDENTITY_* variable is ever set here: the development identity cannot run in Azure.
// The database URL carries no password; the managed identity supplies a token (ADR-15).
var backendEnv = concat(
  [
    { name: 'APP_ENV', value: environmentName }
    { name: 'IDENTITY_PROVIDER', value: 'easy_auth' }
    {
      name: 'DATABASE_URL'
      value: 'postgresql+psycopg://${identity.outputs.backendName}@${postgres.outputs.fqdn}:5432/${postgres.outputs.databaseName}?sslmode=require'
    }
    { name: 'DATABASE_AUTH', value: 'managed_identity' }
    { name: 'AZURE_CLIENT_ID', value: identity.outputs.backendClientId }
    { name: 'STORAGE_BACKEND', value: 'azure_blob' }
    { name: 'STORAGE_ACCOUNT_URL', value: storage.outputs.blobEndpoint }
    { name: 'MAIL_TRANSPORT', value: 'smtp' }
    { name: 'TELEMETRY_EXPORTER', value: 'azure_monitor' }
    { name: 'FRONTEND_ORIGIN', value: frontendOrigin }
    { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
  ],
  empty(allowlistIdentifier) ? [] : [{ name: 'ALLOWLIST_IDENTIFIER', value: allowlistIdentifier }],
  empty(initialAdminEmail) ? [] : [{ name: 'INITIAL_ADMIN_EMAIL', value: initialAdminEmail }],
  empty(initialAdminSubject) ? [] : [{ name: 'INITIAL_ADMIN_SUBJECT', value: initialAdminSubject }],
  empty(branchCatalog) ? [] : [{ name: 'BRANCH_CATALOG', value: branchCatalog }],
  importsEnabled ? [{ name: 'IMPORTS_ENABLED', value: 'true' }] : []
)

module migrateJob 'modules/container-job.bicep' = if (deployJobs) {
  name: 'migrate-job'
  params: {
    location: location
    name: '${prefix}-migrate'
    environmentId: environment.outputs.id
    image: backendImage
    identityId: identity.outputs.backendId
    registryServer: registry.outputs.loginServer
    env: backendEnv
    secrets: backendSecrets
    command: ['python', '-m', 'app.migrate', 'upgrade']
    tags: tags
  }
}

// Ensures the initial administrator (P-07) is on the allowlist and the branch catalog (P-01) is
// loaded, both from configuration. Idempotent.
module seedJob 'modules/container-job.bicep' = if (deployJobs) {
  name: 'seed-job'
  params: {
    location: location
    name: '${prefix}-seed'
    environmentId: environment.outputs.id
    image: backendImage
    identityId: identity.outputs.backendId
    registryServer: registry.outputs.loginServer
    env: backendEnv
    secrets: backendSecrets
    command: ['python', '-m', 'app.seed']
    tags: tags
  }
}

module api 'modules/container-app.bicep' = if (deployApps) {
  name: 'api'
  params: {
    location: location
    name: apiAppName
    environmentId: environment.outputs.id
    image: backendImage
    identityId: identity.outputs.backendId
    registryServer: registry.outputs.loginServer
    // Internal ingress: reachable only from inside the Container Apps environment (ADR-12).
    ingressMode: 'internal'
    targetPort: 8000
    env: backendEnv
    secrets: backendSecrets
    probes: [
      { type: 'Liveness', httpGet: { path: '/healthz', port: 8000 }, initialDelaySeconds: 10, periodSeconds: 10, failureThreshold: 3 }
      { type: 'Readiness', httpGet: { path: '/readyz', port: 8000 }, periodSeconds: 10, failureThreshold: 3 }
    ]
    minReplicas: 1
    maxReplicas: 3
    tags: tags
  }
}

module worker 'modules/container-app.bicep' = if (deployApps) {
  name: 'worker'
  params: {
    location: location
    name: workerAppName
    environmentId: environment.outputs.id
    image: backendImage
    identityId: identity.outputs.backendId
    registryServer: registry.outputs.loginServer
    // No ingress: the worker is never reachable. The probe port serves the platform's probes only.
    ingressMode: 'none'
    command: ['python', '-m', 'app.worker.main']
    env: backendEnv
    secrets: backendSecrets
    probes: [
      { type: 'Liveness', httpGet: { path: '/healthz', port: 8081 }, initialDelaySeconds: 15, periodSeconds: 15, failureThreshold: 4 }
    ]
    // One permanent replica. Overlapping revisions are made safe by the PostgreSQL advisory lock.
    minReplicas: 1
    maxReplicas: 1
    tags: tags
  }
}

module frontend 'modules/container-app.bicep' = if (deployApps) {
  name: 'frontend'
  params: {
    location: location
    name: frontendAppName
    environmentId: environment.outputs.id
    image: frontendImage
    identityId: identity.outputs.frontendId
    registryServer: registry.outputs.loginServer
    ingressMode: 'external'
    targetPort: 3000
    env: [
      { name: 'API_UPSTREAM', value: 'https://${api!.outputs.fqdn}' }
      // Identity headers are only trusted when Easy Auth is in front, since Easy Auth overwrites them.
      { name: 'TRUST_EASY_AUTH_HEADERS', value: toLower(string(easyAuthEnabled)) }
    ]
    secrets: easyAuthEnabled
      ? [
          {
            name: 'google-client-secret'
            keyVaultUrl: '${keyvault.outputs.vaultUri}secrets/google-client-secret'
            identity: identity.outputs.frontendId
          }
        ]
      : []
    probes: [
      { type: 'Liveness', httpGet: { path: '/healthz', port: 3000 }, initialDelaySeconds: 5, periodSeconds: 15, failureThreshold: 3 }
    ]
    minReplicas: 1
    maxReplicas: 2
    cpu: '0.25'
    memory: '0.5Gi'
    tags: tags
  }
}

module auth 'modules/auth.bicep' = if (deployApps && easyAuthEnabled) {
  name: 'easy-auth'
  params: {
    frontendAppName: frontendAppName
    googleClientId: googleClientId
  }
  dependsOn: [
    frontend
  ]
}

module alerts 'modules/alerts.bicep' = if (deployApps) {
  name: 'alerts'
  params: {
    namePrefix: prefix
    apiAppId: api!.outputs.id
    workerAppId: worker!.outputs.id
    postgresServerId: postgres.outputs.serverId
    actionGroupId: monitoring.outputs.actionGroupId
    tags: tags
  }
}

output registryName string = registry.outputs.name
output registryLoginServer string = registry.outputs.loginServer
output keyVaultName string = keyvault.outputs.vaultName
output frontendUrl string = frontendOrigin
output migrateJobName string = '${prefix}-migrate'
output seedJobName string = '${prefix}-seed'
output postgresServerName string = postgres.outputs.serverName
output storageAccountName string = storage.outputs.accountName
output backendIdentityName string = identity.outputs.backendName
