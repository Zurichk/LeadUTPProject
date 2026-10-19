/*
  LecturaFácil — punto de entrada de la infraestructura.

  Ámbito: suscripción. Solo se declara aquí el grupo de recursos; todo lo demás
  vive en `services.bicep`, que se invoca como módulo con `scope`. Esto es
  obligatorio: en un archivo con targetScope='subscription' no se pueden
  declarar recursos de grupo de recursos directamente (error BCP139).

  Crea TODO lo que necesita la aplicación desde cero:

    - Grupo de recursos
    - Managed Identity + 3 roles RBAC
    - Blob Storage + contenedor de fichas
    - Azure AI Vision (OCR) y Azure AI Speech (opcional)
    - Key Vault
    - App Service Plan + Web App Linux con su configuración (LECTURA_*)

  Uso:

    Despliegue completo recomendado:

      az deployment sub create \
        --location westeurope \
        --template-file main.bicep \
        --parameters uniqueSuffix="mika03"
*/

targetScope = 'subscription'

// ============================================================================
// Parámetros
// ============================================================================

@description('Nombre del grupo de recursos.')
param resourceGroupName string = 'LeadUTPProject'

@description('Crear el grupo de recursos. Ponlo en false si YA existe; si no existe, el despliegue falla con ResourceGroupNotFound.')
param createResourceGroup bool = true

@description('Región del grupo de recursos.')
param location string = 'swedencentral'

@description('Sufijo corto y único para los nombres globales de Azure AI Services.')
param uniqueSuffix string = 'mika01'

@description('Región del almacenamiento, del Key Vault y de Azure AI Vision.')
param resourceLocation string = 'swedencentral'

@description('Región del App Service.')
param appServiceLocation string = 'swedencentral'

@description('SKU del plan de App Service.')
param appServicePlanSku string = 'F1'

@description('Región de Azure AI Speech (solo si enableAzureSpeech o enableSpeechServices es true).')
param speechLocation string = 'swedencentral'

@description('Runtime de Python del App Service.')
param pythonVersion string = '3.12'

@description('Nombre global de la cuenta de Blob Storage (3-24 caracteres, minúsculas y números).')
param storageAccountName string = 'leadutpproject'

@description('Nombre del contenedor donde se guardan las fichas.')
param containerName string = 'fichas-lectura'

@description('SKU del almacenamiento. Standard_RAGRS replica en dos regiones.')
@allowed(['Standard_LRS', 'Standard_GRS', 'Standard_RAGRS', 'Standard_ZRS'])
param storageSkuName string = 'Standard_RAGRS'

@description('Crear la cuenta de almacenamiento. Ponlo en false si ya existe.')
param deployStorage bool = true

@description('Asignar los roles RBAC. Ponlo en false si ya existen.')
param assignRoleAssignments bool = true

@description('Crear Azure AI Speech. En Azure for Students devuelve InvalidApiSetId porque se factura por Marketplace.')
param enableAzureSpeech bool = false

@description('Crear un recurso de voz con kind SpeechServices (la variante que Foundry muestra en el portal).')
param enableSpeechServices bool = false

@description('Desplegar un modelo de voz multimodal (gpt-audio-1.5) en lugar de un recurso de Speech.')
param enableAudioModel bool = false

@description('Nombre del deployment del modelo de audio.')
param audioModelDeployment string = 'gpt-audio-1-5'

@description('Modelo de voz. gpt-audio-1.5 (GA, voz a voz), gpt-audio o gpt-realtime-2.1 (tiempo real).')
param audioModelName string = 'gpt-audio-1.5'

@description('Versión del modelo de audio. La de gpt-audio-1.5 es 2026-02-23.')
param audioModelVersion string = '2026-02-23'

@description('Capacidad del deployment de audio en miles de tokens por minuto. Azure exige 10 como mínimo para GlobalStandard.')
param audioModelCapacity int = 10

@description('Crear el despliegue del modelo de traducción en Foundry.')
param deployTranslationModel bool = true

@description('Nombre del modelo en Foundry. gpt-5-mini con GlobalStandard es la opción activa asignable.')
param foundryModelName string = 'gpt-5-mini'

@description('Editor del modelo de traducción. Los modelos gpt-* son de OpenAI y los Phi-* de Microsoft.')
@allowed(['Microsoft', 'OpenAI'])
param foundryModelFormat string = 'OpenAI'

@description('Versión del modelo en Foundry.')
param foundryModelVersion string = '2025-08-07'

@description('Tipo de despliegue del modelo de traducción.')
@allowed(['GlobalStandard', 'Standard', 'DataZoneStandard'])
param foundryModelSku string = 'GlobalStandard'

@description('Unidades de capacidad (TPM) del despliegue del modelo. El mínimo aceptado por Azure es 1.')
param foundryModelCapacity int = 1

@description('Motor de voz: browser usa la Web Speech API, azure usa Azure AI Speech.')
@allowed(['browser', 'azure'])
param speechBackend string = 'browser'

@description('Activar la traducción con un modelo de Foundry.')
param enableTranslation bool = true

@description('Nombre del deployment del modelo de traducción en Foundry.')
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
// Grupo de recursos
// ============================================================================

resource rg 'Microsoft.Resources/resourceGroups@2024-11-01' = if (createResourceGroup) {
  name: resourceGroupName
  location: location
  tags: {
    proyecto: 'lectura-facil'
    uso: 'lectoescritura-infantil'
  }
}

// ============================================================================
// Módulo de recursos (ámbito: grupo de recursos)
// ============================================================================

module services 'services.bicep' = {
  name: 'lecturafacil-servicios'
  scope: resourceGroup(resourceGroupName)
  params: {
    uniqueSuffix: uniqueSuffix
    location: resourceLocation
    appServiceLocation: appServiceLocation
    appServicePlanSku: appServicePlanSku
    speechLocation: speechLocation
    pythonVersion: pythonVersion
    storageAccountName: storageAccountName
    containerName: containerName
    storageSkuName: storageSkuName
    deployStorage: deployStorage
    assignRoleAssignments: assignRoleAssignments
    enableAzureSpeech: enableAzureSpeech
    enableSpeechServices: enableSpeechServices
    enableAudioModel: enableAudioModel
    audioModelDeployment: audioModelDeployment
    audioModelName: audioModelName
    audioModelVersion: audioModelVersion
    audioModelCapacity: audioModelCapacity
    speechBackend: speechBackend
    enableTranslation: enableTranslation
    deployTranslationModel: enableTranslation && deployTranslationModel
    foundryModelName: foundryModelName
    foundryModelFormat: foundryModelFormat
    foundryModelVersion: foundryModelVersion
    foundryModelSku: foundryModelSku
    foundryModelCapacity: foundryModelCapacity
    foundryDeployment: foundryDeployment
    letterCase: letterCase
    matchThreshold: matchThreshold
    maxWords: maxWords
    maxUploadMb: maxUploadMb
    defaultLanguage: defaultLanguage
    healthCheckPath: healthCheckPath
  }
  dependsOn: [
    rg
  ]
}

// ============================================================================
// Salidas
// ============================================================================

@description('URL pública de la aplicación.')
output appUrl string = services.outputs.appUrl

@description('Nombre del App Service.')
output appNameOut string = services.outputs.appNameOut

@description('Endpoint de Azure AI Vision (LECTURA_VISION_ENDPOINT).')
output visionEndpointOut string = services.outputs.visionEndpointOut

@description('Endpoint de Foundry para la traducción (LECTURA_FOUNDRY_ENDPOINT).')
output foundryEndpointOut string = services.outputs.foundryEndpointOut

@description('URL del almacenamiento (LECTURA_BLOB_SERVICE_URL).')
output blobServiceUrlOut string = services.outputs.blobServiceUrlOut

@description('PrincipalId de la identidad administrada.')
output identityPrincipalId string = services.outputs.identityPrincipalId

@description('ClientId de la identidad administrada (AZURE_CLIENT_ID).')
output identityClientId string = services.outputs.identityClientId

@description('Regiones donde quedó cada cosa, por si hay que depurar.')
output locations object = {
  resourceGroup: location
  storage: resourceLocation
  vision: resourceLocation
  appService: appServiceLocation
  speech: enableAzureSpeech || enableSpeechServices ? speechLocation : 'no desplegado (usar voz del navegador)'
  audioModel: enableAudioModel ? resourceLocation : 'no desplegado (usar voz del navegador)'
}