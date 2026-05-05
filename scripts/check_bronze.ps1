Write-Host "Checking Kaggle raw files..." -ForegroundColor Cyan
gcloud storage ls gs://bigdata-project-495412-bronze/raw_kaggle/ --recursive

Write-Host "`nChecking CoinGecko raw files..." -ForegroundColor Cyan
gcloud storage ls gs://bigdata-project-495412-bronze/raw_api/ --recursive

Write-Host "`nChecking manifests..." -ForegroundColor Cyan
gcloud storage ls gs://bigdata-project-495412-bronze/manifest/ --recursive

Write-Host "`nChecking dead-letter records..." -ForegroundColor Cyan
gcloud storage ls gs://bigdata-project-495412-bronze/dead_letter/ --recursive