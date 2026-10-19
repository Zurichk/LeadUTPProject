/*
  LecturaFácil — recursos DENTRO del grupo de recursos.

  Este módulo no se despliega solo: lo invoca `main.bicep` con
  `scope: resourceGroup(...)`. Todo lo declarado aquí vive en el grupo de
  recursos y por eso se omiten los `scope` en cada recurso.

  Desplegable en modo "what-if" para revisar sin aplicar:

    az deployment group create \
      --resource-group LeadUTPProject \
      --template-file services.bicep \
      --parameters uniqueSuffix="mika02" \
      --parameters deployStorage=false
*/

// ============================================================================
// Parámetros
// ============================================================================

@description('Sufijo corto y único para los nombres globales de Azure AI Services.')
param uniqueSuffix string = 'mika01'

@description('Región del almacenamiento, del Key Vault y de Azure AI Vision.')
param location string = 'swedencentral'

@description('Región del App Service.')
param appServiceLocation string = 'swedencentral'

@description('SKU del plan de App Service.')
param appServicePlanSku string = 'F1'

@description('Región de Azure AI Speech (solo si enableAzureSpeech o enableSpeechServices es true).')
param speechLocation string = 'swedencentral'

@description('Runtime de Python del App Service.')
param pythonVersion string = '3.12'

@description('Nombre global de la cuenta de Blob Storage.')
param storageAccountName string = 'leadutpproject'

@description('Nombre del contenedor donde se guardan las fichas.')
param containerName string = 'fichas-lectura'

@description('SKU del almacenamiento. Standard_RAGRS replica en dos regiones.')
param storageSkuName string = 'Standard_RAGRS'

@description('Crear la cuenta de almacenamiento. Ponlo en false si ya existe.')
param deployStorage bool = true

@description('Asignar los roles RBAC. Déjalo en true salvo que los roles ya existan con GUIDs aleatorios creados por "az role assignment create": entonces ARM rechaza el despliegue con RoleAssignmentExists.')
param assignRoleAssignments bool = true

@description('Crear Azure AI Speech. En Azure for Students devuelve InvalidApiSetId porque se factura por Marketplace.')
param enableAzureSpeech bool = false

@description('Crear un recurso de voz con kind SpeechServices (la variante que Foundry muestra en el portal). A diferencia de enableAzureSpeech, este es el recurso "Speech Services" moderno. Si tu suscripción lo rechaza por facturación, déjalo en false.')
param enableSpeechServices bool = false

@description('Desplegar un modelo de voz multimodal (gpt-audio-1.5): entrada y salida de audio directamente por el modelo, sin recurso de Speech.')
param enableAudioModel bool = false

@description('Nombre del deployment del modelo de audio.')
param audioModelDeployment string = 'gpt-audio-1-5'

@description('Modelo de voz. gpt-audio-1.5 (GA, voz a voz), gpt-audio o gpt-realtime-2.1 (tiempo real).')
param audioModelName string = 'gpt-audio-1.5'

@description('Versión del modelo de audio. La de gpt-audio-1.5 es 2026-02-23.')
param audioModelVersion string = '2026-02-23'

@description('Capacidad del deployment de audio en miles de tokens por minuto. Azure exige 10 como mínimo para GlobalStandard.')
param audioModelCapacity int = 10

@description('Crear el despliegue del modelo de traducción en Foundry. Sin él, la traducción sigue funcionando con el diccionario propio pero pierde el respaldo para palabras desconocidas.')
param deployTranslationModel bool = true

@description('Nombre del modelo en Foundry. gpt-5-mini con GlobalStandard es la opción activa para nuevas asignaciones.')
param foundryModelName string = 'gpt-5-mini'

@description('Editor del modelo de traducción. Los modelos gpt-* son de OpenAI y los Phi-* de Microsoft: equivocarse da DeploymentModelNotSupported.')
@allowed(['Microsoft', 'OpenAI'])
param foundryModelFormat string = 'OpenAI'

@description('Versión del modelo en Foundry.')
param foundryModelVersion string = '2025-08-07'

@description('Tipo de despliegue. El catálogo de la cuenta es la fuente de verdad: consulta con "az cognitiveservices account list-models".')
@allowed(['GlobalStandard', 'Standard', 'DataZoneStandard'])
param foundryModelSku string = 'GlobalStandard'

@description('Unidades de capacidad (TPM) del despliegue del modelo. El mínimo aceptado por Azure es 1.')
param foundryModelCapacity int = 1

@description('Motor de voz: browser usa la Web Speech API, azure usa Azure AI Speech.')
@allowed(['browser', 'azure'])
param speechBackend string = 'browser'

@description('Activar la traducción con un modelo de Foundry.')
param enableTranslation bool = true

@description('Nombre del deployment del modelo de traducción en Foundry. Es a la vez el nombre del recurso desplegado y el valor de LECTURA_FOUNDRY_DEPLOYMENT, para que nunca puedan divergir.')
param foundryDeployment string = 'gpt-5-mini'

@description('Modo de las letras en las tarjetas.')
@allowed(['upper', 'lower', 'both'])
param letterCase string = 'both'

@description('Similitud mínima (0-1) para dar por buena una pronunciación.')
param matchThreshold string = '0.8'

@description('Número máximo de palabras por ficha.')
param maxWords string = '12'

@description('Tamaño máximo de la foto de la ficha, en MB.')
param maxUploadMb string = '12'

@description('Idioma por defecto de la interfaz: es o ca.')
@allowed(['es', 'ca'])
param defaultLanguage string = 'es'

@description('Ruta de salud que Azure usa para mantener el sitio despierto.')
param healthCheckPath string = '/health'

// ============================================================================
// Nombres derivados
// ============================================================================

var identityName = 'id-lecturafacil-${uniqueSuffix}'
var visionName = 'cog-lecturafacil-vision-${uniqueSuffix}'
var speechName = 'cog-lecturafacil-speech-${uniqueSuffix}'
var speechServicesName = 'sp-lecturafacil-${uniqueSuffix}'
var keyVaultName = 'kv-lecturafacil-${uniqueSuffix}'
var planName = 'plan-lecturafacil-${uniqueSuffix}'
var appName = 'app-lecturafacil-${uniqueSuffix}'

var visionEndpoint = 'https://${visionName}.cognitiveservices.azure.com/'
// Foundry comparte cuenta con Vision; el endpoint de inferencia va en openai.azure.com.
var foundryEndpoint = 'https://${visionName}.openai.azure.com/openai/v1'
// Se usa environment() para no fijar el dominio: así el mismo Bicep funciona
// en AzureGovernment, AzureChina o AzureStack.
var blobUrl = 'https://${storageAccountName}.blob.${environment().suffixes.storage}'

// Identificadores de los roles usados
var cognitiveServicesUserRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)
var storageBlobDataContributorRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var keyVaultSecretsUserRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

var tags = {
  proyecto: 'lectura-facil'
}

// ============================================================================
// Identidad administrada (la usa la app para acceder a Azure sin claves)
// ============================================================================

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

// ============================================================================
// Almacenamiento
// ============================================================================

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = if (deployStorage) {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: storageSkuName }
  tags: tags
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

// El tipo tiene 3 segmentos (storageAccounts/blobServices/containers), así que
// el nombre necesita exactamente 2 barras: cuenta/default/contenedor.
resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${storageAccountName}/default/${containerName}'
  // Si deployStorage=false esta dependencia se ignora y se usa la cuenta que ya
  // existía en el grupo de recursos.
  dependsOn: [
    storage
  ]
  properties: {
    publicAccess: 'None'
  }
}

// ============================================================================
// Servicios de IA
// ============================================================================

@description('Azure AI Vision: OCR de las fotos de las fichas.')
resource vision 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: visionName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  tags: tags
  properties: {
    customSubDomainName: visionName
    publicNetworkAccess: 'Enabled'
  }
}

@description('Despliegue del modelo de lenguaje usado como respaldo de la traducción. Se crea DENTRO de la cuenta de Vision porque Foundry y Vision son la misma cuenta AIServices.')
resource foundryModel 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployTranslationModel) {
  parent: vision
  name: foundryDeployment
  sku: {
    name: foundryModelSku
    capacity: foundryModelCapacity
  }
  properties: {
    model: {
      // Ojo: los modelos Phi-* son del editor Microsoft y los gpt-* de OpenAI.
      // Con el formato equivocado Azure responde DeploymentModelNotSupported.
      format: foundryModelFormat
      name: foundryModelName
      version: foundryModelVersion
    }
  }
}

@description('Recurso de voz "Speech Services" (kind: SpeechServices), la variante que aparece en Foundry. Comparte formato de claves con Speech pero es un kind distinto.')
resource speechServices 'Microsoft.CognitiveServices/accounts@2023-05-01' = if (enableSpeechServices) {
  name: speechServicesName
  location: speechLocation
  kind: 'SpeechServices'
  sku: {
    // S0 y no F0: F0 requiere método de pago y Azure for Students no lo tiene.
    name: 'S0'
  }
  tags: tags
  properties: {
    customSubDomainName: speechServicesName
    publicNetworkAccess: 'Enabled'
  }
}

// Modelo de voz multimodal: recibe audio y devuelve texto y/o audio.
resource audioModel 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (enableAudioModel) {
  parent: vision
  name: audioModelDeployment
  sku: {
    name: 'GlobalStandard'
    capacity: audioModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: audioModelName
      version: audioModelVersion
    }
  }
}

@description('Azure AI Speech: TTS y STT. No disponible en Azure for Students (InvalidApiSetId).')
resource speech 'Microsoft.CognitiveServices/accounts@2023-05-01' = if (enableAzureSpeech) {
  name: speechName
  location: speechLocation
  kind: 'Speech'
  sku: { name: 'S0' }
  tags: tags
  properties: {
    customSubDomainName: speechName
    publicNetworkAccess: 'Enabled'
  }
}

// ============================================================================
// Key Vault
// ============================================================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

// ============================================================================
// App Service
// ============================================================================

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: appServiceLocation
  kind: 'linux'
  sku: { name: appServicePlanSku }
  tags: tags
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: appServiceLocation
  kind: 'app,linux'
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|${pythonVersion}'
      alwaysOn: appServicePlanSku != 'F1'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      http20Enabled: true
      appCommandLine: 'gunicorn -w 1 --timeout 120 -k uvicorn.workers.UvicornWorker app.main:app'
      healthCheckPath: healthCheckPath
    }
  }
}

resource appSettings 'Microsoft.Web/sites/config@2023-12-01' = {
  name: 'appsettings'
  parent: app
  properties: {
    LECTURA_ENVIRONMENT: 'prod'
    LECTURA_LOG_LEVEL: 'INFO'
    LECTURA_DEMO_MODE: 'false'

    // OCR
    LECTURA_OCR_PROVIDER: 'vision'
    LECTURA_VISION_ENDPOINT: visionEndpoint
    LECTURA_MIN_OCR_CONFIDENCE: '0.5'

    // Almacenamiento (sin claves: usa la Managed Identity)
    LECTURA_BLOB_SERVICE_URL: blobUrl
    LECTURA_BLOB_CONTAINER: containerName
    LECTURA_PROFILES_BLOB_NAME: 'perfiles.json'

    // Voz
    LECTURA_SPEECH_BACKEND: speechBackend
    LECTURA_SPEECH_KEY: ''
    LECTURA_SPEECH_VOICES__ES: 'es-ES-ElviraNeural'
    LECTURA_SPEECH_VOICES__CA: 'ca-ES-JoanaNeural'
    LECTURA_SPEECH_REGION: enableAzureSpeech || enableSpeechServices ? speechLocation : ''

    // Voz mediante modelo multimodal (gpt-audio-1.5)
    LECTURA_FOUNDRY_AUDIO_DEPLOYMENT: enableAudioModel ? audioModelDeployment : ''
    LECTURA_FOUNDRY_AUDIO_ENABLED: string(enableAudioModel)

    // Traducción (diccionario propio + modelo de Foundry de respaldo)
    LECTURA_TRANSLATION_ENABLED: string(enableTranslation)
    LECTURA_FOUNDRY_ENDPOINT: foundryEndpoint
    LECTURA_FOUNDRY_DEPLOYMENT: foundryDeployment
    LECTURA_FOUNDRY_API_KEY: ''
    LECTURA_FOUNDRY_TIMEOUT_SECONDS: '12'
    LECTURA_TRANSLATION_CACHE_SIZE: '512'

    // Interfaz
    LECTURA_DEFAULT_LANGUAGE: defaultLanguage
    LECTURA_DEFAULT_MAX_WORDS: maxWords
    LECTURA_MAX_UPLOAD_MB: maxUploadMb
    LECTURA_MATCH_THRESHOLD: matchThreshold
    LECTURA_LETTER_CASE: letterCase

    // Identidad administrada asignada por el usuario
    AZURE_CLIENT_ID: identity.properties.clientId

    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
  }
}

// ============================================================================
// Permisos
// ============================================================================

@description('Cognitive Services User: acceso a Vision (y Foundry).')
resource roleCognitiveServices 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignRoleAssignments) {
  name: guid(resourceGroup().id, identity.id, 'cognitive-services-user')
  properties: {
    roleDefinitionId: cognitiveServicesUserRole
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('Storage Blob Data Contributor: escritura de fichas y perfiles.')
resource roleStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignRoleAssignments) {
  name: guid(resourceGroup().id, identity.id, 'storage-blob-data-contributor')
  properties: {
    roleDefinitionId: storageBlobDataContributorRole
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('Key Vault Secrets User: lectura de secretos si se usan.')
resource roleKeyVault 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignRoleAssignments) {
  name: guid(resourceGroup().id, identity.id, 'key-vault-secrets-user')
  properties: {
    roleDefinitionId: keyVaultSecretsUserRole
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Salidas
// ============================================================================

@description('URL pública de la aplicación.')
output appUrl string = 'https://${app.properties.defaultHostName}/'

@description('Nombre del App Service.')
output appNameOut string = appName

@description('Endpoint de Azure AI Vision (LECTURA_VISION_ENDPOINT).')
output visionEndpointOut string = visionEndpoint

@description('Endpoint de Foundry para la traducción (LECTURA_FOUNDRY_ENDPOINT).')
output foundryEndpointOut string = foundryEndpoint

@description('URL del almacenamiento (LECTURA_BLOB_SERVICE_URL).')
output blobServiceUrlOut string = blobUrl

@description('PrincipalId de la identidad administrada.')
output identityPrincipalId string = identity.properties.principalId

@description('ClientId de la identidad administrada (AZURE_CLIENT_ID).')
output identityClientId string = identity.properties.clientId

@description('Regiones donde quedó cada cosa, por si hay que depurar.')
output locations object = {
  storage: location
  vision: location
  keyVault: location
  appService: appServiceLocation
  speech: enableAzureSpeech ? speechLocation : (enableSpeechServices ? speechLocation : 'no desplegado (usar voz del navegador)')
  audioModel: enableAudioModel ? location : 'no desplegado (usar voz del navegador)'
}