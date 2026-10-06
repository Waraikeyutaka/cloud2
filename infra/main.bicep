// =====================================================================
// クラウド利用Ⅱ ベースアプリ（問い合わせ管理アプリ）の構成
//   azd up で、リソースグループと、その中のリソース一式を作る。
//   azd down で、リソースグループごと削除する。
// =====================================================================
targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd の環境名。リソースグループ名などに使う')
param environmentName string

@minLength(1)
@description('Functions・Cosmos DB・Storage を作るリージョン（授業で指定したもの）')
param location string

@description('Static Web Apps を作るリージョン（Static Web Apps は作れるリージョンが限られる）')
@allowed([ 'eastasia', 'eastus2', 'westus2', 'centralus', 'westeurope' ])
param webLocation string = 'eastasia'

@description('Cosmos DB の Free tier を使うか（Free tier は1サブスクリプションに1つだけ）')
param cosmosFreeTier bool = true

// すべてのリソースに付けるタグ（コマ3で学んだタグ）
var tags = {
  'azd-env-name': environmentName
  course: 'cloud2'
  lesson: '04'
}

// リソース名の重複を避けるための短い文字列（同じ環境名・場所なら毎回同じ値になる）
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    webLocation: webLocation
    tags: tags
    resourceToken: resourceToken
    cosmosFreeTier: cosmosFreeTier
  }
}

// azd は output の値を環境変数として保存し、デプロイやフックで使う
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output API_BASE_URL string = resources.outputs.apiBaseUrl
output WEB_URL string = resources.outputs.webUrl
