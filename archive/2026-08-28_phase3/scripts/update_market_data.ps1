$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$macroDir = Join-Path $projectRoot 'data/raw/macro'
$bundlePath = Join-Path $macroDir 'fred_bundle.zip'
New-Item -ItemType Directory -Force -Path $macroDir | Out-Null
$fredIds = 'DGS10,DFII10,T10YIE,DFF,DTWEXBGS,DEXCHUS,DCOILBRENTEU,VIXCLS,CPIAUCSL,UNRATE,PAYEMS'
$fredUrl = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=$fredIds"
curl.exe -L --fail --silent --show-error --max-time 60 -o $bundlePath $fredUrl
if ($LASTEXITCODE -ne 0) { throw "FRED download failed with exit code $LASTEXITCODE" }
python (Join-Path $PSScriptRoot 'collect_market_data.py')
if ($LASTEXITCODE -ne 0) { throw "Market collector failed with exit code $LASTEXITCODE" }
