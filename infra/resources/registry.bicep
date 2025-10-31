param name string
param location string = resourceGroup().location
param tags object = {}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: replace(name, '-', '')
  location: location
  tags: tags
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: true
    anonymousPullEnabled: false
    dataEndpointEnabled: false
    encryption: {
      status: 'disabled'
    }
    networkRuleBypassOptions: 'AzureServices'
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
  }
}

output name string = containerRegistry.name
output loginServer string = containerRegistry.properties.loginServer
