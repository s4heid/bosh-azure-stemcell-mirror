param name string
param location string = resourceGroup().location
param tags object = {}
param identityName string
param containerRegistryName string
param containerAppsEnvironmentName string
param applicationInsightsName string
param storageAccountName string
param galleryName string
param exists bool
@secure()
param appDefinition object

var appSettingsArray = filter(array(appDefinition.settings), i => i.name != '')
var secrets = map(filter(appSettingsArray, i => i.?secret != null), i => {
  name: i.name
  value: i.value
  secretRef: i.?secretRef ?? take(replace(replace(toLower(i.name), '_', '-'), '.', '-'), 32)
})
var env = map(filter(appSettingsArray, i => i.?secret == null), i => {
  name: i.name
  value: i.value
})

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsEnvironmentName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-05-01' existing = {
  name: storageAccountName
}

resource gallery 'Microsoft.Compute/galleries@2023-07-03' existing = {
  name: galleryName
}

resource contributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: resourceGroup()
  name: guid(subscription().id, resourceGroup().id, identity.id, 'contributorRole')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b24988ac-6180-42a0-ab88-20f7382dd24c'
    )
    principalType: 'ServicePrincipal'
    principalId: identity.properties.principalId
  }
}

resource storageBlobDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, resourceGroup().id, identity.id, 'storageBlobDataContributorRole')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    principalType: 'ServicePrincipal'
    principalId: identity.properties.principalId
  }
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: containerRegistry
  name: guid(subscription().id, resourceGroup().id, identity.id, 'acrPullRole')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
    principalType: 'ServicePrincipal'
    principalId: identity.properties.principalId
  }
}

resource galleryImageContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: gallery
  name: guid(subscription().id, resourceGroup().id, identity.id, 'galleryImageContributorRole')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '85a2d0d9-2eba-4c9c-b355-11c2cc0788ab'
    )
    principalType: 'ServicePrincipal'
    principalId: identity.properties.principalId
  }
}

module fetchLatestImage '../modules/fetch-container-image.bicep' = {
  name: '${name}-fetch-image'
  params: {
    exists: exists
    name: name
  }
}

resource app 'Microsoft.App/jobs@2024-03-01' = {
  name: '${name}-job'
  location: location
  tags: union(tags, { 'azd-service-name': 'bosh-azure-stemcell-mirror-job' })
  dependsOn: [acrPullRole]
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: union(
        [],
        map(secrets, secret => {
          name: secret.secretRef
          value: secret.value
        })
      )
      replicaTimeout: 900 // 15 minutes
      replicaRetryLimit: 1
      manualTriggerConfig: {
        replicaCompletionCount: 1
        parallelism: 1
      }
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: '22 7 * * *'
      }
    }
    template: {
      containers: [
        {
          image: fetchLatestImage.outputs.?containers[?0].?image ?? 'ghcr.io/s4heid/bosh-azure-stemcell-mirror:main'
          name: 'mirror-daily'
          env: union(
            [
              {
                name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
                value: applicationInsights.properties.ConnectionString
              }
              {
                name: 'AZURE_CONTAINER_REGISTRY_MANAGED_IDENTITY_ID'
                value: identity.properties.clientId
              }
              {
                name: 'AZURE_SUBSCRIPTION_ID'
                value: subscription().subscriptionId
              }
              {
                name: 'AZURE_REGION'
                value: location
              }
              {
                name: 'AZURE_RESOURCE_GROUP'
                value: resourceGroup().name
              }
              {
                name: 'BASM_STORAGE_ACCOUNT_NAME'
                value: storageAccount.name
              }
              {
                name: 'BASM_GALLERY_NAME'
                value: gallery.name
              }
              {
                name: 'BASM_GALLERY_IMAGE_NAME'
                value: 'ubuntu-jammy'
              }
              {
                name: 'BASM_STEMCELL_SERIES'
                value: 'bosh-azure-hyperv-ubuntu-jammy-go_agent'
              }
              {
                name: 'BASM_MOUNTED_DIRECTORY'
                value: '/stemcellfiles'
              }
            ],
            env,
            map(secrets, secret => {
              name: secret.name
              secretRef: secret.secretRef
            })
          )
          resources: {
            cpu: json('1.0')
            memory: '2.0Gi'
          }
          volumeMounts: [
            {
              volumeName: 'stemcellvolume'
              mountPath: '/stemcellfiles'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'stemcellvolume'
          storageType: 'EmptyDir'
        }
      ]
    }
  }
}

output name string = app.name
output id string = app.id
output identityClientId string = identity.properties.clientId
