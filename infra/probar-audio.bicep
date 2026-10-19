/*
  LecturaFácil — prueba aislada del modelo de voz gpt-4o-audio-preview.

  Solo crea DOS recursos: una cuenta AIServices nueva y el deployment del modelo
  de audio. No toca el grupo LeadUTPProject, ni el Storage, ni Vision, ni la
  web: sirve para responder a una pregunta concreta ("¿mi suscripción puede
  desplegar este modelo?") en un par de minutos y sin riesgo.

  Desplegar:

    az deployment group create \
      --resource-group LeadUTPProject \
      --template-file probar-audio.bicep

  Ver el resultado:

    az cognitiveservices account deployment list \
      -g LeadUTPProject -n cog-prueba-audio-<sfx> -o table

  Limpiar después:

    az cognitiveservices account delete \
      -g LeadUTPProject -n cog-prueba-audio-<sfx>
*/

targetScope = 'resourceGroup'

@description('Sufijo para el nombre de la cuenta de prueba.')
param uniqueSuffix string = 'mika01'

@description('Región. Los modelos de audio (gpt-audio y gpt-realtime) están disponibles en Sweden Central, East US 2 y Central US.')
param location string = 'swedencentral'

@description('Nombre del deployment del modelo de audio.')
param audioModelDeployment string = 'gpt-audio-1-5'

@description('Modelo. Opciones: gpt-audio-1.5 (GA, voz a voz), gpt-audio o gpt-realtime-2.1 (tiempo real). gpt-4o-audio-preview ya no existe: quedó obsoleto el 24/03/2026.')
param audioModelName string = 'gpt-audio-1.5'

@description('Versión del modelo. La de gpt-audio-1.5 es 2026-02-23.')
param audioModelVersion string = '2026-02-23'

@description('Capacidad en miles de tokens por minuto. GlobalStandard exige 10.')
param audioModelCapacity int = 10

var accountName = 'cog-prueba-audio-${uniqueSuffix}'

resource account 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
  }
}

resource audioModel 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
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

@description('Resultado de la prueba, para leerlo sin parsear el JSON de ARM.')
output pruebaOk bool = true

@description('Cuenta creada en la prueba.')
output accountNameOut string = accountName

@description('Deployment del modelo de audio.')
output deploymentName string = audioModelDeployment