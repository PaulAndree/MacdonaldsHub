// Reusable Container App, used 3x: frontend, api, worker (ADR-03, ADR-08).
// ingressMode: 'external' (internet), 'internal' (inside the Container Apps environment only),
// or 'none' (no ingress at all, as for the worker).
param location string
param name string
param environmentId string
param image string
param identityId string
param registryServer string
@allowed(['external', 'internal', 'none'])
param ingressMode string
param targetPort int = 8000
param env array = []
param secrets array = []
param probes array = []
param command array = []
param minReplicas int = 1
param maxReplicas int = 1
param cpu string = '0.5'
param memory string = '1Gi'
param tags object

var hasIngress = ingressMode != 'none'

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: hasIngress
        ? {
            external: ingressMode == 'external'
            targetPort: targetPort
            transport: 'auto'
            allowInsecure: false
          }
        : null
      registries: [
        {
          server: registryServer
          identity: identityId
        }
      ]
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: name
          image: image
          command: empty(command) ? null : command
          env: env
          probes: probes
          resources: {
            cpu: json(cpu)
            memory: memory
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = hasIngress ? app.properties.configuration.ingress.fqdn : ''
