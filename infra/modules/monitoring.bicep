// Log Analytics, Application Insights and an optional alert action group (ADR-07, RNF-10).
param location string
param namePrefix string
param alertEmail string
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-appi'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    DisableLocalAuth: true
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (!empty(alertEmail)) {
  name: '${namePrefix}-alerts'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'dh-alerts'
    enabled: true
    emailReceivers: [
      {
        name: 'operations'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

output workspaceName string = workspace.name
output appInsightsName string = appInsights.name
output actionGroupId string = !empty(alertEmail) ? actionGroup.id : ''
