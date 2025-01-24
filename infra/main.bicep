targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

param srcExists bool
@secure()
param srcDefinition object

// @description('Id of the user or app to assign application roles')
// param principalId string

var tags = {
  'azd-env-name': environmentName
}

var abbrs = loadJsonContent('./abbreviations.json')

var resourceToken = substring(toLower(uniqueString(subscription().id, environmentName, location)), 0, 4)

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

module monitoring 'resources/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: 'la-${environmentName}${resourceToken}'
    applicationInsightsName: 'ai-${environmentName}${resourceToken}'
    location: location
    tags: tags
  }
  scope: rg
}

// module keyVault 'resources/keyvault.bicep' = {
//   name: 'keyvault'
//   params: {
//     location: location
//     tags: tags
//     name: '${abbrs.keyVaultVaults}${resourceToken}'
//     principalId: principalId
//   }
//   scope: rg
// }

module containerRegistry 'resources/registry.bicep' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${environmentName}${resourceToken}'
    location: location
    tags: tags
  }
  scope: rg
}

module storageAccount 'resources/storage.bicep' = {
  name: 'storageModule'
  params: {
    name: '${abbrs.storageStorageAccounts}${environmentName}'
    location: location
    tags: tags
  }
  scope: rg
}

module gallery 'resources/gallery.bicep' = {
  name: 'gallery'
  params: {
    name: '${abbrs.computeGalleries}${environmentName}'
    location: location
    tags: tags
  }
  scope: rg
}

module appsEnvironment 'resources/appsEnvironment.bicep' = {
  name: 'appsEnvironment'
  params: {
    name: '${abbrs.appManagedEnvironments}${environmentName}'
    location: location
    tags: tags
    logAnalyticsWorkspaceName: monitoring.outputs.logAnalyticsWorkspaceName
    applicationInsightsName: monitoring.outputs.applicationInsightsName
  }
  scope: rg
}

module app 'app/app.bicep' = {
  name: 'app'
  params: {
    name: environmentName
    location: location
    tags: tags
    identityName: '${abbrs.managedIdentityUserAssignedIdentities}${environmentName}-${resourceToken}'
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    containerAppsEnvironmentName: appsEnvironment.outputs.name
    containerRegistryName: containerRegistry.outputs.name
    exists: srcExists
    appDefinition: srcDefinition
    storageAccountName: storageAccount.outputs.storageAccountName
    galleryName: gallery.outputs.name
  }
  scope: rg
}

// `azd deploy` uses this endpoint to push images to the container registry
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_MANAGED_IDENTITY_ID string = app.outputs.identityClientId
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = appsEnvironment.outputs.id

// output AZURE_KEY_VAULT_NAME string = keyVault.outputs.name
// output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.endpoint
