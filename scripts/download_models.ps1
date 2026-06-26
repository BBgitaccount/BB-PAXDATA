# =============================================================================
# download_models.ps1
# =============================================================================
# Downloads spaCy model .whl files into docker/models/ for offline Docker builds.
# Run this script once before building the Docker image, or whenever models are updated.
#
# Usage:
#   .\scripts\download_models.ps1
# =============================================================================

$modelsDir = Join-Path $PSScriptRoot "..\docker\models"
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null

$models = @(
    @{
        Name = "en_core_web_lg"
        Url  = "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl"
        File = "en_core_web_lg-3.8.0-py3-none-any.whl"
    },
    @{
        Name = "tr_core_news_md"
        Url  = "https://huggingface.co/turkish-nlp-suite/tr_core_news_md/resolve/main/tr_core_news_md-1.0-py3-none-any.whl"
        File = "tr_core_news_md-1.0-py3-none-any.whl"
    }
)

foreach ($model in $models) {
    $outPath = Join-Path $modelsDir $model.File
    if (Test-Path $outPath) {
        Write-Host "[$($model.Name)] Already exists, skipping: $($model.File)" -ForegroundColor Yellow
    } else {
        Write-Host "[$($model.Name)] Downloading..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $model.Url -OutFile $outPath -UseBasicParsing
        Write-Host "[$($model.Name)] Done: $outPath" -ForegroundColor Green
    }
}

Write-Host "`nAll models ready in: $modelsDir" -ForegroundColor Green
