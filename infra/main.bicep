/*
  LecturaFácil — infraestructura Azure.

  Usa una cuenta de Blob Storage YA existente (creada manualmente en el
  portal) y crea el resto de recursos: Azure AI Vision (OCR), Azure AI Speech
  (voz), Key Vault, App Service con Managed Identity y los roles RBAC.

  IMPORTANTE: no crea la cuenta de almacenamiento; solo añade el contenedor
  `fichas-lectura` a la cuenta indicada en el parámetro `blobAccountName`.
  Para crear una cuenta desde cero, ver infra/storage-account.bicep.

  Uso:
    az deployment group create -g LeadUTPProject \
      --template-file infra/main.bicep \
      --parameters blobAccountName="leadutpproject" location="westus2"
*/

@description('Nombre de la cuenta de Blob Storage existente donde se guardan las fichas.')
param blobAccountName string

@description('Nombre base de los recursos de IA.')
param projectName string = 'lecturafacil'

@description('Sufijo corto y único para los nombres globales (recursos de IA).')
param uniqueSuffix string

@description('Región de los recursos.')
param location string = 'westus2'

@description('Región de Azure AI Speech.')
param speechRegion string = 'westus2'

@description('SKU del plan de App Service.')
param appServicePlanSku string = 'B1'

@description('Runtime de Python del App Service.')
param pythonVersion string = '3.12'

@description('Nombre del contenedor donde se guardan las fichas.')
param containerName string = 'fichas-lectura'

var suffix = toLower(uniqueSuffix)
var visionName = 'cog-${projectName}-vision-${suffix}'
var speechName = 'cog-${projectName}-speech-${suffix}'
var keyVaultName = 'kv-${projectName}-${suffix}'
var appName = 'app-${projectName}-${suffix}'
var planName = 'plan-${projectName}-${suffix}'
var managedIdentityName = 'id-${projectName}-${suffix}'

/* ------------------------------------------------------------ almacenamiento */

@description('Cuenta de Blob Storage existente.')
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: blobAccountName
}

@description('Contenedor privado de fichas (no se crea la cuenta, solo este hijo).')
resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: storage
  name: 'blobServices/default/${containerName}'
  properties: {
    publicAccess: 'None'
  }
}

/* ------------------------------------------------------------------ identidad */

@description('Identidad administrada que usa la aplicación para acceder a Azure.')
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
}

/* -------------------------------------------------------- servicios de IA (IA) */

@description('Azure AI Vision: OCR de las fotos de las fichas.')
resource vision 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: visionName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: visionName
    publicNetworkAccess: 'Enabled'
  }
}

@description('Azure AI Speech: síntesis de voz y reconocimiento.')
resource speech 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: speechName
  location: location
  kind: 'Speech'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: speechName
    publicNetworkAccess: 'Enabled'
  }
}

@description('Key Vault para claves que se necesiten fuera de Azure.')
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableSoftDelete: true
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

/* ------------------------------------------------------------------ aplicación */

@description('Plan de App Service para el backend FastAPI.')
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: { name: appServicePlanSku }
  kind: 'linux'
  properties: { reserved: true }
}

@description('App Service (Linux, Python) con identidad administrada.')
resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|${pythonVersion}'
      alwaysOn: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      http20Enabled: true
    }
  }
}

@description('Configuración de la aplicación (prefijo LECTURA_).')
resource appSettings 'Microsoft.Web/sites/config@2023-12-01' = {
  parent: app
  name: 'appsettings'
  properties: {
    LECTURA_ENVIRONMENT: 'prod'
    LECTURA_LOG_LEVEL: 'INFO'
    LECTURA_OCR_PROVIDER: 'vision'
    LECTURA_VISION_ENDPOINT: 'https://${visionName}.cognitiveservices.azure.com/'
    LECTURA_BLOB_SERVICE_URL: 'https://${blobAccountName}.blob.core.windows.net/'
    LECTURA_BLOB_CONTAINER: containerName
    LECTURA_SPEECH_REGION: speechRegion
    LECTURA_DEFAULT_LANGUAGE: 'es'
    LECTURA_DEFAULT_MAX_WORDS: '12'
    LECTURA_MAX_UPLOAD_MB: '12'
    LECTURA_MATCH_THRESHOLD: '0.8'
    AZURE_CLIENT_ID: identity.properties.clientId
  }
}

/* -------------------------------------------------------------------- permisos */

@description('Rol de Cognitive Services sobre todo el grupo de recursos (Vision y Speech).')
resource cognitiveRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vision.id, identity.id, 'Cognitive Services User')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'a97b65f3-24c7-4388-baec-2e87135dc908'
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('Rol de escritura en el almacenamiento de fichas.')
resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, 'Storage Blob Data Contributor')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('Rol de lectura de secretos en Key Vault.')
resource keyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identity.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

/* -------------------------------------------------------------------- salidas */

@description('Endpoint de Azure AI Vision (LECTURA_VISION_ENDPOINT).')
output visionEndpoint string = 'https://${visionName}.cognitiveservices.azure.com/'

@description('Región de Speech (LECTURA_SPEECH_REGION).')
output speechRegionOut string = speechRegion

@description('URL del almacenamiento usado por la aplicación.')
output blobServiceUrl string = 'https://${blobAccountName}.blob.core.windows.net/'

@description('Nombre del App Service desplegado.')
output appNameOut string = app.name

@description('Nombre del contenedor de fichas.')
output containerNameOut string = container.name