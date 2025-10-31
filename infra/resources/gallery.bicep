param name string
param location string = resourceGroup().location
param tags object = {}

resource computeGallery 'Microsoft.Compute/galleries@2023-07-03' = {
  name: replace(name, '-', '')
  location: location
  tags: tags
  properties: {
    identifier: {}
  }
}

output name string = computeGallery.name
