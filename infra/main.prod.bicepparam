// Production environment: its own resource group, database, storage and secrets (BASE-10).
// Nothing from the test environment is ever promoted here. Not deployed by the platform-base
// change until P-05 (operating objectives) and P-07 (identities) are resolved.
using './main.bicep'

param environmentName = 'production'
param namePrefix = 'deliveryhub'
param location = 'spaincentral'

param deploymentStage = readEnvironmentVariable('DEPLOYMENT_STAGE', 'infrastructure')
param imageTag = readEnvironmentVariable('IMAGE_TAG', 'latest')

param easyAuthEnabled = toLower(readEnvironmentVariable('EASY_AUTH_ENABLED', 'false')) == 'true'
param googleClientId = readEnvironmentVariable('GOOGLE_CLIENT_ID', '')

param allowlistIdentifier = readEnvironmentVariable('ALLOWLIST_IDENTIFIER', '')
param initialAdminEmail = readEnvironmentVariable('INITIAL_ADMIN_EMAIL', '')
param initialAdminSubject = readEnvironmentVariable('INITIAL_ADMIN_SUBJECT', '')
param branchCatalog = readEnvironmentVariable('BRANCH_CATALOG', '')
param importsEnabled = readEnvironmentVariable('IMPORTS_ENABLED', 'false') == 'true'
param testRecipientEmail = readEnvironmentVariable('TEST_RECIPIENT_EMAIL', '')
param alertEmail = readEnvironmentVariable('ALERT_EMAIL', '')

// Provisional sizing and redundancy (P-05 pending): review before production use.
param postgresSkuName = 'Standard_B1ms'
param postgresSkuTier = 'Burstable'
param postgresStorageGb = 32
param postgresBackupRetentionDays = 7
param storageSkuName = 'Standard_LRS'
param enableKeyVaultPurgeProtection = true
