// User-assigned managed identities (ADR-15). One for the frontend (registry pull and its Easy Auth
// secret) and one shared by the API, worker and jobs, which run the same backend code and image.
param location string
param namePrefix string
param tags object

resource frontend 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-id-frontend'
  location: location
  tags: tags
}

resource backend 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-id-backend'
  location: location
  tags: tags
}

output frontendId string = frontend.id
output frontendPrincipalId string = frontend.properties.principalId
output frontendClientId string = frontend.properties.clientId
output backendId string = backend.id
output backendName string = backend.name
output backendPrincipalId string = backend.properties.principalId
output backendClientId string = backend.properties.clientId
