// Technical alerts (RNF-10): API server errors, worker not running, database pressure.
// Thresholds are technical defaults, not availability objectives (those are pending, P-05).
param namePrefix string
param apiAppId string
param workerAppId string
param postgresServerId string
param actionGroupId string
param tags object

var actions = empty(actionGroupId)
  ? []
  : [
      {
        actionGroupId: actionGroupId
      }
    ]

resource api5xx 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-api-5xx'
  location: 'global'
  tags: tags
  properties: {
    description: 'The API returned server errors.'
    severity: 2
    enabled: true
    scopes: [
      apiAppId
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'server-errors'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'Microsoft.App/containerApps'
          metricName: 'Requests'
          dimensions: [
            {
              name: 'statusCodeCategory'
              operator: 'Include'
              values: [
                '5xx'
              ]
            }
          ]
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Total'
        }
      ]
    }
    actions: actions
  }
}

resource workerDown 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-worker-down'
  location: 'global'
  tags: tags
  properties: {
    description: 'No worker replica is running.'
    severity: 1
    enabled: true
    scopes: [
      workerAppId
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'no-replicas'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'Microsoft.App/containerApps'
          metricName: 'Replicas'
          operator: 'LessThan'
          threshold: 1
          timeAggregation: 'Minimum'
        }
      ]
    }
    actions: actions
  }
}

resource databaseStorage 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-db-storage'
  location: 'global'
  tags: tags
  properties: {
    description: 'PostgreSQL storage is nearly full.'
    severity: 2
    enabled: true
    scopes: [
      postgresServerId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'storage-percent'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          metricName: 'storage_percent'
          operator: 'GreaterThan'
          threshold: 85
          timeAggregation: 'Average'
        }
      ]
    }
    actions: actions
  }
}
