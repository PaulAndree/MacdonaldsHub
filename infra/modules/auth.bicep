// Easy Auth with Google on the FRONTEND app only (ADR-05, ADR-12). The API has no authentication
// configuration: it is internal-only and trusts the identity forwarded by the frontend proxy.
param frontendAppName string
param googleClientId string
@description('Name of the Container App secret that holds the Google client secret (a Key Vault reference).')
param googleClientSecretName string = 'google-client-secret'

resource frontend 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: frontendAppName
}

resource authConfig 'Microsoft.App/containerApps/authConfigs@2024-03-01' = {
  parent: frontend
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'google'
      excludedPaths: [
        '/healthz'
      ]
    }
    identityProviders: {
      google: {
        enabled: true
        registration: {
          clientId: googleClientId
          clientSecretSettingName: googleClientSecretName
        }
        login: {
          scopes: [
            'openid'
            'profile'
            'email'
          ]
        }
      }
    }
    login: {
      preserveUrlFragmentsForLogins: false
    }
  }
}
