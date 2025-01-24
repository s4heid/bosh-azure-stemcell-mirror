param name string
param location string = resourceGroup().location
param tags object = {}

// param principalId string
// module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
//   name: 'registry'
//   params: {
//     name: name
//     location: location
//     acrAdminUserEnabled: true
//     tags: tags
//     acrSku: 'Standard'
//     publicNetworkAccess: 'Enabled'
//     zoneRedundancy: 'Disabled'
//     roleAssignments: [
//       {
//         principalId: principalId
//         principalType: 'ServicePrincipal'
//         roleDefinitionIdOrName: subscriptionResourceId(
//           'Microsoft.Authorization/roleDefinitions',
//           '7f951dda-4ed3-4680-a7ca-43fe172d538d'
//         )
//       }
//     ]
//   }
// }

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Standard'
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
