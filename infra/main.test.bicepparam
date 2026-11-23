// Test environment: its own resource group, database, storage and secrets (BASE-10).
// Values that depend on pending decisions come from the environment and have no defaults.
using './main.bicep'

param environmentName = 'test'
param namePrefix = 'deliveryhub'
param location = 'spaincentral'

param deploymentStage = readEnvironmentVariable('DEPLOYMENT_STAGE', 'infrastructure')
param imageTag = readEnvironmentVariable('IMAGE_TAG', 'latest')

// Set EASY_AUTH_ENABLED=true once the Google client exists (P-07) and the Key Vault secret
// `google-client-secret` has been created.
param easyAuthEnabled = toLower(readEnvironmentVariable('EASY_AUTH_ENABLED', 'false')) == 'true'
param googleClientId = readEnvironmentVariable('GOOGLE_CLIENT_ID', '')

// P-07: stable identifier and initial administrator, supplied by the operator.
param allowlistIdentifier = readEnvironmentVariable('ALLOWLIST_IDENTIFIER', '')
param initialAdminEmail = readEnvironmentVariable('INITIAL_ADMIN_EMAIL', '')
param initialAdminSubject = readEnvironmentVariable('INITIAL_ADMIN_SUBJECT', '')
param branchCatalog = readEnvironmentVariable('BRANCH_CATALOG', '')
param importsEnabled = readEnvironmentVariable('IMPORTS_ENABLED', 'false') == 'true'
param testRecipientEmail = readEnvironmentVariable('TEST_RECIPIENT_EMAIL', '')
param alertEmail = readEnvironmentVariable('ALERT_EMAIL', '')

// Provisional sizing (P-05 pending).
param postgresSkuName = 'Standard_B1ms'
param postgresSkuTier = 'Burstable'
param postgresStorageGb = 32
param postgresBackupRetentionDays = 7
param storageSkuName = 'Standard_LRS'
param enableKeyVaultPurgeProtection = false
