param name string
param location string = resourceGroup().location
param tags object = {}

param storageAccountName string
param logAnalyticsWorkspaceName string
param applicationInsightsName string = ''

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    zoneRedundant: false
    workloadProfiles: [
      {
        workloadProfileType: 'Consumption'
        name: 'Consumption'
      }
    ]
  }
}

resource ephemeralVolume 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: containerAppsEnvironment
  name: 'stemcell-ephemeral-volume'
  properties: {
    azureFile: {
      accountName: storageAccount.name
      shareName: 'stemcell-ephemeral-volume'
      accessMode: 'ReadWrite'
    }
  }
}

output name string = containerAppsEnvironment.name
output ephemeralVolumeName string = ephemeralVolume.name
